import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set

from app.retrieval.sqlite_retriever import RequirementContext


@dataclass
class CrossDependency:
    """
    Identified dependency relationship between two requirements in a set.
    """
    source_requirement_id: int
    source_srs_id: str
    target_requirement_id: Optional[int]
    target_srs_id: str
    dependency_type: str  # REFERENCE, PRODUCER_CONSUMER, SHARED_STATE, SECTION_PREREQUISITE
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CrossDependency":
        return cls(**data)


@dataclass
class SetAnalysisResult:
    """
    Structured outcome of cross-requirement set-level analysis for batches or target groups.
    """
    requirement_ids: List[int]
    section_clusters: Dict[str, List[int]] = field(default_factory=dict)
    shared_entities: Dict[str, List[int]] = field(default_factory=dict)
    cross_dependencies: List[CrossDependency] = field(default_factory=list)
    shared_predicates: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requirement_ids": self.requirement_ids,
            "section_clusters": self.section_clusters,
            "shared_entities": self.shared_entities,
            "cross_dependencies": [d.to_dict() for d in self.cross_dependencies],
            "shared_predicates": self.shared_predicates,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SetAnalysisResult":
        deps = [
            CrossDependency.from_dict(d) if isinstance(d, dict) else d
            for d in data.get("cross_dependencies", [])
        ]
        return cls(
            requirement_ids=list(data.get("requirement_ids", [])),
            section_clusters=dict(data.get("section_clusters", {})),
            shared_entities=dict(data.get("shared_entities", {})),
            cross_dependencies=deps,
            shared_predicates=list(data.get("shared_predicates", [])),
            summary=str(data.get("summary", "")),
        )


class SetAnalyst:
    """
    Performs deterministic, set-level pre-analysis for batches of requirements.
    Identifies shared section contexts, common entities/components, cross-references,
    and producer-consumer dependency links before individual formalization passes.
    """

    # Common English stopwords to ignore when extracting entity candidate nouns
    STOPWORDS: Set[str] = {
        "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "with",
        "by", "from", "of", "shall", "will", "must", "should", "is", "are",
        "was", "were", "be", "been", "being", "have", "has", "had", "do",
        "does", "did", "if", "then", "when", "as", "than", "more", "less",
        "each", "all", "any", "both", "not", "no", "this", "that", "these",
        "those", "such", "other", "into", "within", "during", "after", "before",
    }

    def _extract_candidate_entities(self, text: str) -> Set[str]:
        """
        Extracts candidate domain entity nouns and acronyms (e.g. FCP, VMEbus, NE, triplex).
        """
        if not text:
            return set()

        # Match uppercase acronyms (e.g. FCP, NE, VME, SRS)
        acronyms = set(re.findall(r"\b[A-Z]{2,}\b", text))

        # Match hyphenated/underscored terms or technical compounds (e.g. loss_of_comm, fail-safe)
        compounds = set(re.findall(r"\b[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)+\b", text))

        # Match capitalized technical words (excluding sentence starters)
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text)
        candidates = set()
        for w in words:
            w_lower = w.lower()
            if w_lower not in self.STOPWORDS and len(w_lower) > 2:
                candidates.add(w_lower)

        return (acronyms | compounds | candidates)

    def analyze_set(self, requirements: List[RequirementContext]) -> SetAnalysisResult:
        """
        Analyzes a set of requirements to discover section clusters, shared entities,
        cross-references, and causal dependencies.

        Args:
            requirements: List of RequirementContext instances from SQLite.

        Returns:
            Structured SetAnalysisResult.
        """
        if not requirements:
            return SetAnalysisResult(requirement_ids=[], summary="Empty requirement set.")

        req_ids = [r.requirement_id for r in requirements]
        srs_id_map: Dict[str, RequirementContext] = {
            r.srs_id.strip("[]").upper(): r for r in requirements
        }
        req_id_map: Dict[int, RequirementContext] = {
            r.requirement_id: r for r in requirements
        }

        # 1. Section Clustering
        section_clusters: Dict[str, List[int]] = {}
        for r in requirements:
            sec_key = f"{r.section_number} - {r.section_title or 'Untitled'}"
            section_clusters.setdefault(sec_key, []).append(r.requirement_id)

        # 2. Entity Extraction & Co-occurrence
        req_entities: Dict[int, Set[str]] = {}
        entity_cooccur: Dict[str, List[int]] = {}

        for r in requirements:
            ents = self._extract_candidate_entities(r.raw_text)
            req_entities[r.requirement_id] = ents
            for ent in ents:
                entity_cooccur.setdefault(ent, []).append(r.requirement_id)

        # Filter shared entities (must appear in at least 2 requirements)
        shared_entities: Dict[str, List[int]] = {
            ent: ids for ent, ids in entity_cooccur.items()
            if len(set(ids)) > 1 and len(ent) > 2
        }

        # 3. Cross-Requirement References & Causal Dependencies
        cross_dependencies: List[CrossDependency] = []
        for r in requirements:
            text = r.raw_text

            # Check explicit references like [SRS178], SRS178, or Requirement 8
            srs_mentions = re.findall(r"(?:\[SRS|SRS)\s*([0-9]+)\]?", text, re.IGNORECASE)
            for m in srs_mentions:
                target_key = f"SRS{m}".upper()
                target_req = srs_id_map.get(target_key)
                if target_req and target_req.requirement_id != r.requirement_id:
                    cross_dependencies.append(CrossDependency(
                        source_requirement_id=r.requirement_id,
                        source_srs_id=r.srs_id,
                        target_requirement_id=target_req.requirement_id,
                        target_srs_id=target_req.srs_id,
                        dependency_type="REFERENCE",
                        description=f"Requirement {r.srs_id} explicitly references {target_req.srs_id}.",
                    ))

            # Producer-consumer heuristic: if requirement A mentions disabling/setting a state
            # and requirement B mentions checking or depending on that state
            r_lower = text.lower()
            if "disable" in r_lower or "reset" in r_lower or "shutdown" in r_lower:
                for other in requirements:
                    if other.requirement_id != r.requirement_id:
                        other_lower = other.raw_text.lower()
                        if "disabled" in other_lower or "after reset" in other_lower or "safe state" in other_lower:
                            cross_dependencies.append(CrossDependency(
                                source_requirement_id=r.requirement_id,
                                source_srs_id=r.srs_id,
                                target_requirement_id=other.requirement_id,
                                target_srs_id=other.srs_id,
                                dependency_type="PRODUCER_CONSUMER",
                                description=(
                                    f"State action in {r.srs_id} may condition behavior in {other.srs_id}."
                                ),
                            ))

        # 4. Shared Predicate Candidates
        shared_predicates: List[str] = []
        for ent in sorted(shared_entities.keys()):
            if ent.isupper() or "_" in ent:
                shared_predicates.append(f"active({ent})")

        # 5. Build Summary
        summary_lines = [
            f"Batch set analysis for {len(requirements)} requirements across {len(section_clusters)} section clusters.",
        ]
        if cross_dependencies:
            summary_lines.append(f"Identified {len(cross_dependencies)} cross-requirement dependencies.")
        if shared_entities:
            top_shared = sorted(shared_entities.keys(), key=lambda k: len(shared_entities[k]), reverse=True)[:5]
            summary_lines.append(f"Top shared entities: {', '.join(top_shared)}.")

        return SetAnalysisResult(
            requirement_ids=req_ids,
            section_clusters=section_clusters,
            shared_entities=shared_entities,
            cross_dependencies=cross_dependencies,
            shared_predicates=shared_predicates,
            summary=" ".join(summary_lines),
        )

    def get_requirement_context_for_set(
        self,
        requirement_id: int,
        set_result: SetAnalysisResult,
    ) -> Dict[str, Any]:
        """
        Extracts contextual dependencies and shared entities specific to a single requirement
        from a batch SetAnalysisResult.
        """
        # Find related requirements in same section cluster
        related_in_section: List[int] = []
        section_name = ""
        for sec, ids in set_result.section_clusters.items():
            if requirement_id in ids:
                related_in_section = [i for i in ids if i != requirement_id]
                section_name = sec
                break

        # Find dependencies involving this requirement
        relevant_deps = [
            d.to_dict() for d in set_result.cross_dependencies
            if d.source_requirement_id == requirement_id or d.target_requirement_id == requirement_id
        ]

        # Find shared entities present in this requirement
        relevant_shared_entities = [
            ent for ent, ids in set_result.shared_entities.items()
            if requirement_id in ids
        ]

        return {
            "section_clusters": f"{section_name} (sibling req IDs: {related_in_section})" if section_name else "",
            "shared_entities": ", ".join(relevant_shared_entities) if relevant_shared_entities else "None",
            "cross_dependencies": [d["description"] for d in relevant_deps] if relevant_deps else [],
            "summary": set_result.summary,
        }
