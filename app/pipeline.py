import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Union

from app.analyst.analyst_model import AnalystModel
from app.analyst.set_analyst import SetAnalysisResult, SetAnalyst
from app.clarification.clarification_manager import ClarificationManager
from app.critic.critic_model import CriticModel
from app.formalization_validator import validate_formalization
from app.reasoning.reasoning_model import ReasoningModel
from app.retrieval.context_builder import ContextBuilder, ContextPackage
from app.retrieval.obsidian_retriever import ObsidianRetriever
from app.retrieval.sqlite_retriever import RequirementContext, SQLiteRetriever
from app.revision.revision_manager import RevisionManager
from app.revision.schemas import RevisionResult
from app.symbols.symbol_retriever import SymbolRetriever
from app.symbols.symbol_validator import SymbolValidator


@dataclass
class PipelineResult:
    """
    Unified end-to-end outcome of the SRS Formalization Agent pipeline.
    Preserves requirement identity, retrieved patterns, symbol and note provenance,
    candidate formalizations, critic findings, revision history, and clarifications.
    """
    # Requirement identity & raw text
    requirement_id: int
    global_number: int
    srs_id: str
    section_number: str
    section_title: str
    raw_text: str

    # Analyst stage
    identified_patterns: List[str] = field(default_factory=list)
    analyst_rationale: str = ""
    analyst_confidence: str = ""

    # Knowledge & Symbol Retrieval
    retrieved_patterns: List[str] = field(default_factory=list)
    retrieved_files: List[str] = field(default_factory=list)
    retrieved_notes: List[Dict[str, str]] = field(default_factory=list)
    symbols: List[Dict[str, Any]] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)

    # Formalization / Reasoning
    formalization: str = ""
    interpretation: str = ""
    entities: List[str] = field(default_factory=list)
    predicates: List[str] = field(default_factory=list)
    conditions: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    temporal_constraints: List[str] = field(default_factory=list)
    mathematical_constraints: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)

    # Verification, Critic & Revision
    status: str = "PENDING"  # "PASS", "BLOCKED", "MAX_ITERATIONS", "NEEDS_REVISION", "FAILED"
    termination_reason: str = ""
    # Deterministic structural validation of the final formula (None = not run, e.g. pipeline failed earlier).
    # Structural only; it does not establish semantic correctness.
    validation_valid: Optional[bool] = None
    validation_findings: List[Dict[str, Any]] = field(default_factory=list)
    critic_summary: str = ""
    critic_findings: List[Dict[str, Any]] = field(default_factory=list)
    iterations_conducted: int = 0
    max_iterations: int = 2
    revision_history: List[Dict[str, Any]] = field(default_factory=list)

    # Assumptions & Clarifications
    assumptions: List[str] = field(default_factory=list)
    unresolved_items: List[str] = field(default_factory=list)
    clarifications: List[Dict[str, Any]] = field(default_factory=list)

    # Provenance, Intermediate Representation & Set Context
    constraint_provenance: List[Dict[str, Any]] = field(default_factory=list)
    intermediate_representation: Optional[Dict[str, Any]] = None
    set_context: Optional[Dict[str, Any]] = None

    # Execution status & error tracking
    success: bool = True
    error_message: Optional[str] = None
    error_stage: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert PipelineResult to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineResult":
        """Construct PipelineResult from dictionary."""
        return cls(**data)

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serialize PipelineResult to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class FormalizationPipeline:
    """
    Master Orchestrator coordinating SQLiteRetriever, AnalystModel, ContextBuilder,
    SymbolRetriever, RevisionManager, and ClarificationManager into an automated,
    traceable end-to-end formalization pipeline.
    """

    def __init__(
        self,
        sqlite_retriever: Optional[SQLiteRetriever] = None,
        analyst_model: Optional[AnalystModel] = None,
        obsidian_retriever: Optional[ObsidianRetriever] = None,
        symbol_retriever: Optional[SymbolRetriever] = None,
        context_builder: Optional[ContextBuilder] = None,
        reasoning_model: Optional[ReasoningModel] = None,
        critic_model: Optional[CriticModel] = None,
        revision_manager: Optional[RevisionManager] = None,
        clarification_manager: Optional[ClarificationManager] = None,
        symbol_validator: Optional[SymbolValidator] = None,
        set_analyst: Optional[SetAnalyst] = None,
    ) -> None:
        self.sqlite_retriever = sqlite_retriever
        self.analyst_model = analyst_model
        self.obsidian_retriever = obsidian_retriever
        self.symbol_retriever = symbol_retriever
        self.context_builder = context_builder
        self.reasoning_model = reasoning_model
        self.critic_model = critic_model
        self.revision_manager = revision_manager
        self.clarification_manager = clarification_manager or ClarificationManager()
        self.symbol_validator = symbol_validator
        self.set_analyst = set_analyst

    def _ensure_components(self, max_iterations: int = 2) -> None:
        """Lazily initialize default components if not injected."""
        if self.sqlite_retriever is None:
            self.sqlite_retriever = SQLiteRetriever()

        if self.analyst_model is None:
            from app.analyst.ollama_analyst import OllamaAnalyst
            self.analyst_model = OllamaAnalyst()

        if self.set_analyst is None:
            self.set_analyst = SetAnalyst()

        if self.obsidian_retriever is None:
            self.obsidian_retriever = ObsidianRetriever()

        if self.symbol_retriever is None:
            self.symbol_retriever = SymbolRetriever()

        if self.symbol_validator is None and self.symbol_retriever is not None:
            self.symbol_validator = SymbolValidator(self.symbol_retriever.registry)

        if self.context_builder is None:
            self.context_builder = ContextBuilder(
                sqlite_retriever=self.sqlite_retriever,
                obsidian_retriever=self.obsidian_retriever,
                symbol_retriever=self.symbol_retriever,
            )

        if self.reasoning_model is None:
            from app.reasoning.ollama_reasoning import OllamaReasoning
            self.reasoning_model = OllamaReasoning()

        if self.critic_model is None:
            from app.critic.ollama_critic import OllamaCritic
            self.critic_model = OllamaCritic()

        if self.revision_manager is None:
            self.revision_manager = RevisionManager(
                reasoning_model=self.reasoning_model,
                critic_model=self.critic_model,
                max_iterations=max_iterations,
                symbol_validator=self.symbol_validator,
            )
        elif getattr(self.revision_manager, "symbol_validator", None) is None and self.symbol_validator is not None:
            self.revision_manager.symbol_validator = self.symbol_validator

    def run(
        self,
        requirement_id: int,
        max_revisions: int = 2,
        clarifications: Optional[List[Dict[str, Any]]] = None,
        set_context: Optional[Dict[str, Any]] = None,
    ) -> PipelineResult:
        """
        Executes the complete formalization pipeline for a target requirement.

        Args:
            requirement_id: Primary key ID of the requirement in SQLite.
            max_revisions: Maximum number of reasoning-critic revision passes.
            clarifications: Optional previously recorded stakeholder clarification resolutions.
            set_context: Optional batch/set-level contextual enrichment dictionary.

        Returns:
            Structured PipelineResult with full stage-by-stage traceability.
        """
        self._ensure_components(max_iterations=max_revisions)

        # 1. Retrieve requirement from SQLite
        try:
            req_context = self.sqlite_retriever.get_requirement_by_id(requirement_id)
        except Exception as e:
            return PipelineResult(
                requirement_id=requirement_id,
                global_number=0,
                srs_id="",
                section_number="",
                section_title="",
                raw_text="",
                set_context=set_context,
                status="FAILED",
                success=False,
                error_stage="SQLITE_RETRIEVAL",
                error_message=f"Failed to retrieve requirement ID {requirement_id} from SQLite: {e}",
            )

        # 2. Run Analyst Model
        try:
            analyst_res = self.analyst_model.analyze(req_context)
            identified_patterns = list(analyst_res.identified_patterns)
            analyst_rationale = getattr(analyst_res, "rationale", "")
            analyst_confidence = getattr(analyst_res, "confidence", "")
        except Exception as e:
            return PipelineResult(
                requirement_id=req_context.requirement_id,
                global_number=req_context.global_number,
                srs_id=req_context.srs_id,
                section_number=req_context.section_number,
                section_title=req_context.section_title or "",
                raw_text=req_context.raw_text,
                set_context=set_context,
                status="FAILED",
                success=False,
                error_stage="ANALYST",
                error_message=f"Analyst pattern identification failed: {e}",
            )

        # 3. Build ContextPackage (Retrieves Obsidian Knowledge + Registered Symbols)
        try:
            context_pkg = self.context_builder.build(
                requirement_ids=[requirement_id],
                pattern_names=identified_patterns,
                include_symbols=True,
                clarifications=clarifications or [],
                set_context=set_context,
            )
        except Exception as e:
            return PipelineResult(
                requirement_id=req_context.requirement_id,
                global_number=req_context.global_number,
                srs_id=req_context.srs_id,
                section_number=req_context.section_number,
                section_title=req_context.section_title or "",
                raw_text=req_context.raw_text,
                identified_patterns=identified_patterns,
                set_context=set_context,
                status="FAILED",
                success=False,
                error_stage="CONTEXT_BUILDER",
                error_message=f"ContextPackage assembly failed: {e}",
            )

        # Extract symbols and file provenance
        obsidian_files: List[str] = []
        retrieved_notes: List[Dict[str, str]] = []
        if context_pkg.obsidian_knowledge and hasattr(context_pkg.obsidian_knowledge, "pattern_items"):
            for item in context_pkg.obsidian_knowledge.pattern_items:
                for note, role in ([(item.pattern_note, "pattern")] +
                                   [(n, "formalization") for n in item.formalization_notes] +
                                   [(n, "concept") for n in item.concept_notes]):
                    obsidian_files.append(note.file_path)
                    retrieved_notes.append({"path": note.file_path, "role": role, "content": note.content})

        symbols_data = [
            s.to_dict() if hasattr(s, "to_dict") else dict(s)
            for s in getattr(context_pkg, "symbols", [])
        ]

        # 4. Run RevisionManager (Reasoning + Critic Bounded Loop)
        try:
            self.revision_manager.max_iterations = max_revisions
            revision_res = self.revision_manager.run_revision_loop(context_pkg)
        except Exception as e:
            return PipelineResult(
                requirement_id=req_context.requirement_id,
                global_number=req_context.global_number,
                srs_id=req_context.srs_id,
                section_number=req_context.section_number,
                section_title=req_context.section_title or "",
                raw_text=req_context.raw_text,
                identified_patterns=identified_patterns,
                retrieved_patterns=identified_patterns,
                retrieved_files=obsidian_files,
                retrieved_notes=retrieved_notes,
                symbols=symbols_data,
                provenance=context_pkg.provenance or {},
                set_context=set_context,
                status="FAILED",
                success=False,
                error_stage="REVISION_LOOP",
                error_message=f"Formalization reasoning/critic loop failed: {e}",
            )

        # 5. Run Clarification Manager
        clarif_res = self.clarification_manager.generate_clarifications(
            requirement_context=req_context,
            revision_result=revision_res,
            existing_clarifications=clarifications,
        )

        final_reasoning = revision_res.final_reasoning_result
        final_critic = revision_res.final_critic_result

        validation = validate_formalization(final_reasoning.formalization if final_reasoning else "")
        symbol_report = None
        if self.symbol_validator and final_reasoning:
            symbol_report = self.symbol_validator.validate_candidate(
                formalization=final_reasoning.formalization,
                predicates=final_reasoning.predicates,
                entities=final_reasoning.identified_entities,
                current_scope=req_context.srs_id,
                intermediate_representation=final_reasoning.intermediate_representation,
                identified_patterns=identified_patterns,
                source_text=req_context.raw_text,
            )
        symbol_is_valid = symbol_report.is_valid if symbol_report else True
        is_overall_valid = validation.is_valid and symbol_is_valid

        combined_findings = list(validation.findings)
        if symbol_report:
            for v in symbol_report.violations:
                if v.severity == "ERROR":
                    combined_findings.append({
                        "category": "SYMBOL_VALIDATION",
                        "severity": v.severity,
                        "rule": v.rule,
                        "description": v.description,
                        "recommendation": f"Ensure symbol '{v.symbol_spelling}' complies with canonical registry definitions and permitted scope.",
                    })

        final_status = revision_res.status
        final_termination = revision_res.termination_reason
        if final_status == "PASS" and not is_overall_valid:
            # Defence in depth: RevisionManager already prevents this, but PASS must never coexist
            # with a deterministic validation failure.
            final_status = "NEEDS_REVISION"
            final_termination = "VALIDATION_FAILED"

        # Register propositions, predicates, and entities from intermediate representation into SymbolRegistry
        if (final_status.startswith("PASS")) and self.symbol_retriever and getattr(self.symbol_retriever, "registry", None) and final_reasoning:
            self._register_intermediate_symbols(req_context, final_reasoning)

        return PipelineResult(
            requirement_id=req_context.requirement_id,
            global_number=req_context.global_number,
            srs_id=req_context.srs_id,
            section_number=req_context.section_number,
            section_title=req_context.section_title or "",
            raw_text=req_context.raw_text,
            identified_patterns=identified_patterns,
            analyst_rationale=analyst_rationale,
            analyst_confidence=analyst_confidence,
            retrieved_patterns=identified_patterns,
            retrieved_files=obsidian_files,
            retrieved_notes=retrieved_notes,
            symbols=symbols_data,
            provenance=context_pkg.provenance or {},
            formalization=final_reasoning.formalization if final_reasoning else "",
            interpretation=final_reasoning.interpretation if final_reasoning else "",
            entities=final_reasoning.identified_entities if final_reasoning else [],
            predicates=final_reasoning.predicates if final_reasoning else [],
            conditions=final_reasoning.conditions if final_reasoning else [],
            actions=final_reasoning.actions if final_reasoning else [],
            temporal_constraints=final_reasoning.temporal_constraints if final_reasoning else [],
            mathematical_constraints=final_reasoning.mathematical_constraints if final_reasoning else [],
            dependencies=final_reasoning.dependencies if final_reasoning else [],
            status=final_status,
            termination_reason=final_termination,
            validation_valid=is_overall_valid,
            validation_findings=combined_findings,
            critic_summary=final_critic.summary if final_critic else "",
            critic_findings=[f.to_dict() for f in final_critic.findings] if final_critic else [],
            iterations_conducted=revision_res.iterations_conducted,
            max_iterations=revision_res.max_iterations,
            revision_history=[h.to_dict() for h in revision_res.history],
            assumptions=final_reasoning.assumptions if final_reasoning else [],
            unresolved_items=final_reasoning.unresolved_items if final_reasoning else [],
            clarifications=[q.to_dict() for q in clarif_res.questions],
            constraint_provenance=getattr(final_reasoning, "constraint_provenance", []) if final_reasoning else [],
            intermediate_representation=getattr(final_reasoning, "intermediate_representation", None) if final_reasoning else None,
            set_context=set_context,
            success=True,
            error_message=None,
            error_stage=None,
        )

    def run_batch(
        self,
        requirement_ids: List[int],
        max_revisions: int = 2,
        clarifications_by_req: Optional[Dict[int, List[Dict[str, Any]]]] = None,
    ) -> List[PipelineResult]:
        """
        Executes batch formalization for a set of requirements.
        Performs set-level dependency analysis first to discover shared section contexts,
        common entities, and cross-requirement dependencies, then executes formalization
        for each requirement with enriched contextual awareness.
        """
        self._ensure_components(max_iterations=max_revisions)
        clarifications_by_req = clarifications_by_req or {}

        # 1. Retrieve all requirement contexts for set analysis
        req_contexts: List[RequirementContext] = []
        failed_results: Dict[int, PipelineResult] = {}

        for rid in requirement_ids:
            try:
                ctx = self.sqlite_retriever.get_requirement_by_id(rid)
                req_contexts.append(ctx)
            except Exception as e:
                failed_results[rid] = PipelineResult(
                    requirement_id=rid,
                    global_number=0,
                    srs_id="",
                    section_number="",
                    section_title="",
                    raw_text="",
                    status="FAILED",
                    success=False,
                    error_stage="SQLITE_RETRIEVAL",
                    error_message=f"Failed to retrieve requirement ID {rid} from SQLite: {e}",
                )

        # 2. Run Set-Level Analysis
        set_analysis_res = None
        if req_contexts and self.set_analyst:
            try:
                set_analysis_res = self.set_analyst.analyze_set(req_contexts)
            except Exception:
                set_analysis_res = None

        # 3. Execute formalization sequentially for each requirement
        results: List[PipelineResult] = []
        for rid in requirement_ids:
            if rid in failed_results:
                results.append(failed_results[rid])
                continue

            req_set_ctx = None
            if set_analysis_res and self.set_analyst:
                req_set_ctx = self.set_analyst.get_requirement_context_for_set(rid, set_analysis_res)

            req_clarifs = clarifications_by_req.get(rid)
            res = self.run(
                requirement_id=rid,
                max_revisions=max_revisions,
                clarifications=req_clarifs,
                set_context=req_set_ctx,
            )
            results.append(res)

        return results

    def _register_intermediate_symbols(self, req_context: RequirementContext, reasoning: Any) -> None:
        """
        Safely registers propositions, predicates, and entities from IntermediateRepresentation
        and reasoning output into the canonical SymbolRegistry without duplicating existing symbols
        or overwriting user-approved definitions. Never modifies frozen SRS-Knowledge vault.
        """
        reg = getattr(self.symbol_retriever, "registry", None)
        if not reg:
            return

        scope = req_context.srs_id

        # 1. Extract intermediate representation (handle dataclass or dict)
        ir = getattr(reasoning, "intermediate_representation", None)
        if hasattr(ir, "to_dict"):
            ir = ir.to_dict()

        if isinstance(ir, dict):
            # Propositions (explicit definitions: P := Definition)
            for prop in ir.get("propositions", []):
                p_sym = prop.get("symbol") if isinstance(prop, dict) else getattr(prop, "symbol", None)
                if p_sym and str(p_sym).strip():
                    clean_sym = str(p_sym).strip()
                    p_def = prop.get("definition", "") if isinstance(prop, dict) else getattr(prop, "definition", "")
                    p_notat = prop.get("notation", "") if isinstance(prop, dict) else getattr(prop, "notation", "")
                    p_prov = prop.get("provenance", "EXPLICIT_SOURCE") if isinstance(prop, dict) else getattr(prop, "provenance", "EXPLICIT_SOURCE")
                    p_appr = prop.get("user_approved", False) if isinstance(prop, dict) else getattr(prop, "user_approved", False)
                    p_sig = str(p_notat or (f"{clean_sym} := {p_def}" if p_def else clean_sym)).strip()
                    full_desc = str(p_def or clean_sym).strip()
                    reg.register_domain_symbol(
                        spelling=clean_sym,
                        category="PROPOSITION",
                        scope=scope,
                        definition=full_desc,
                        signature=p_sig,
                        notes=p_sig,
                        provenance={
                            "source": "IntermediateRepresentation",
                            "requirement_id": req_context.requirement_id,
                            "srs_id": req_context.srs_id,
                            "category": str(p_prov),
                        },
                        user_approved=bool(p_appr),
                    )

            # Predicates from IntermediateRepresentation
            for p in ir.get("predicates", []):
                p_name = p.get("name") if isinstance(p, dict) else getattr(p, "name", None)
                if p_name and str(p_name).strip():
                    clean_name = str(p_name).strip()
                    p_desc = p.get("description", "") if isinstance(p, dict) else getattr(p, "description", "")
                    p_ent = p.get("entity", "") if isinstance(p, dict) else getattr(p, "entity", "")
                    p_cond = p.get("condition_type", "") if isinstance(p, dict) else getattr(p, "condition_type", "")
                    p_sig = p.get("formal_expression") if isinstance(p, dict) else getattr(p, "formal_expression", None)
                    p_notat = p.get("notation", "") if isinstance(p, dict) else getattr(p, "notation", "")
                    p_appr = p.get("user_approved", False) if isinstance(p, dict) else getattr(p, "user_approved", False)
                    p_prov = p.get("provenance", "EXPLICIT_SOURCE") if isinstance(p, dict) else getattr(p, "provenance", "EXPLICIT_SOURCE")
                    full_desc = (p_desc.strip() or f"{p_cond} predicate for {p_ent}".strip() or f"Domain predicate {clean_name}")
                    reg.register_domain_symbol(
                        spelling=clean_name,
                        category="PREDICATE",
                        scope=scope,
                        definition=full_desc,
                        signature=p_sig or p_notat,
                        notes=p_notat or None,
                        provenance={
                            "source": "IntermediateRepresentation",
                            "requirement_id": req_context.requirement_id,
                            "srs_id": req_context.srs_id,
                            "category": str(p_prov),
                        },
                        user_approved=bool(p_appr),
                    )

                    if p_ent and str(p_ent).strip():
                        reg.register_domain_symbol(
                            spelling=str(p_ent).strip(),
                            category="ENTITY",
                            scope=scope,
                            definition=f"System entity '{p_ent}' referenced in predicate for {scope}",
                            provenance={
                                "source": "IntermediateRepresentation",
                                "requirement_id": req_context.requirement_id,
                                "srs_id": req_context.srs_id,
                            },
                            user_approved=False,
                        )

            # Atomic clauses / legacy propositions fallback
            for prop in ir.get("atomic_clauses", []):
                if prop and str(prop).strip():
                    raw_str = str(prop).strip()
                    if ":=" in raw_str:
                        sym, defn = raw_str.split(":=", 1)
                        clean_sym = sym.strip()
                        clean_def = defn.strip()
                        p_sig = raw_str
                    else:
                        clean_sym = raw_str
                        clean_def = f"Propositional clause '{raw_str}' identified for {scope}"
                        p_sig = None
                    reg.register_domain_symbol(
                        spelling=clean_sym,
                        category="PROPOSITION",
                        scope=scope,
                        definition=clean_def,
                        signature=p_sig,
                        notes=p_sig,
                        provenance={
                            "source": "IntermediateRepresentation",
                            "requirement_id": req_context.requirement_id,
                            "srs_id": req_context.srs_id,
                        },
                        user_approved=False,
                    )

            # Entities from IntermediateRepresentation
            for ent in ir.get("entities", []):
                ent_name = ent.get("name") if isinstance(ent, dict) else (ent if isinstance(ent, str) else getattr(ent, "name", None))
                if ent_name and str(ent_name).strip():
                    clean_ent = str(ent_name).strip()
                    ent_desc = ent.get("description", "") if isinstance(ent, dict) else getattr(ent, "description", "")
                    ent_cat = ent.get("category", "ENTITY") if isinstance(ent, dict) else getattr(ent, "category", "ENTITY")
                    reg.register_domain_symbol(
                        spelling=clean_ent,
                        category=ent_cat or "ENTITY",
                        scope=scope,
                        definition=ent_desc.strip() or f"Entity '{clean_ent}' identified in intermediate representation for {scope}",
                        provenance={
                            "source": "IntermediateRepresentation",
                            "requirement_id": req_context.requirement_id,
                            "srs_id": req_context.srs_id,
                        },
                        user_approved=False,
                    )


def run_formalization_pipeline(
    requirement_id: int,
    max_revisions: int = 2,
    sqlite_retriever: Optional[SQLiteRetriever] = None,
    analyst_model: Optional[AnalystModel] = None,
    obsidian_retriever: Optional[ObsidianRetriever] = None,
    symbol_retriever: Optional[SymbolRetriever] = None,
    context_builder: Optional[ContextBuilder] = None,
    reasoning_model: Optional[ReasoningModel] = None,
    critic_model: Optional[CriticModel] = None,
    revision_manager: Optional[RevisionManager] = None,
    clarification_manager: Optional[ClarificationManager] = None,
    clarifications: Optional[List[Dict[str, Any]]] = None,
    set_context: Optional[Dict[str, Any]] = None,
    set_analyst: Optional[SetAnalyst] = None,
) -> PipelineResult:
    """
    Convenience function to run the formalization pipeline for a requirement ID.
    """
    pipeline = FormalizationPipeline(
        sqlite_retriever=sqlite_retriever,
        analyst_model=analyst_model,
        obsidian_retriever=obsidian_retriever,
        symbol_retriever=symbol_retriever,
        context_builder=context_builder,
        reasoning_model=reasoning_model,
        critic_model=critic_model,
        revision_manager=revision_manager,
        clarification_manager=clarification_manager,
        set_analyst=set_analyst,
    )
    return pipeline.run(
        requirement_id=requirement_id,
        max_revisions=max_revisions,
        clarifications=clarifications,
        set_context=set_context,
    )
