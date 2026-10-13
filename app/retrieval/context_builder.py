from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.retrieval.obsidian_retriever import (
    ObsidianRetriever,
    RetrievalResult,
)
from app.retrieval.sqlite_retriever import (
    RequirementContext,
    SQLiteRetriever,
)


@dataclass
class ContextPackage:
    """
    Structured data package combining canonical SRS requirements from SQLite
    and engineering/domain/formalization knowledge from Obsidian with explicit provenance.
    """
    requirements: List[RequirementContext]
    identified_patterns: List[str]
    obsidian_knowledge: RetrievalResult
    provenance: Dict[str, Any]
    symbols: List[Any] = field(default_factory=list)
    clarifications: List[Dict[str, Any]] = field(default_factory=list)


class ContextBuilder:
    """
    Orchestration component combining SQLiteRetriever (canonical SRS data),
    ObsidianRetriever (engineering/domain/formalization knowledge), and
    SymbolRetriever (canonical mathematical & temporal symbols) into an inspectable
    ContextPackage while preserving input ordering and source provenance.
    """

    def __init__(
        self,
        sqlite_retriever: Optional[SQLiteRetriever] = None,
        obsidian_retriever: Optional[ObsidianRetriever] = None,
        symbol_retriever: Optional[Any] = None,
    ) -> None:
        """
        Initialize the ContextBuilder orchestrator.

        Args:
            sqlite_retriever: Optional SQLiteRetriever instance. If None, default is instantiated.
            obsidian_retriever: Optional ObsidianRetriever instance. If None, default is instantiated.
            symbol_retriever: Optional SymbolRetriever instance for canonical symbol definitions.
        """
        self.sqlite_retriever = sqlite_retriever or SQLiteRetriever()
        self.obsidian_retriever = obsidian_retriever or ObsidianRetriever()
        self.symbol_retriever = symbol_retriever

    def build(
        self,
        requirement_ids: List[int],
        pattern_names: List[str],
        include_symbols: bool = False,
        clarifications: Optional[List[Dict[str, Any]]] = None,
    ) -> ContextPackage:
        """
        Builds a ContextPackage given requirement IDs and exact Analyst pattern names.

        Args:
            requirement_ids: List of requirement database primary key IDs.
            pattern_names: List of exact Analyst pattern names.

        Returns:
            ContextPackage containing structured requirement contexts, pattern knowledge, and provenance.
        """
        # 1. Retrieve canonical SRS requirement contexts from SQLite (preserves requirement order)
        req_contexts = self.sqlite_retriever.get_requirements_by_ids(requirement_ids)

        # 2. Retrieve engineering/domain/formalization knowledge from Obsidian (preserves pattern order)
        obsidian_result = self.obsidian_retriever.retrieve_patterns(pattern_names)

        # 3. Construct explicit provenance tracking dictionary
        obsidian_files: List[str] = []
        for item in obsidian_result.pattern_items:
            obsidian_files.append(item.pattern_file_path)
            for fn in item.formalization_notes:
                obsidian_files.append(fn.file_path)
            for cn in item.concept_notes:
                obsidian_files.append(cn.file_path)

        provenance: Dict[str, Any] = {
            "sqlite": {
                "source": "SQLite",
                "db_path": str(self.sqlite_retriever.db_path),
                "tables_accessed": ["requirements", "sections", "documents"],
                "requirement_ids": requirement_ids,
            },
            "obsidian": {
                "source": "Obsidian",
                "vault_root": str(self.obsidian_retriever.vault_root),
                "registry_path": str(self.obsidian_retriever.registry_path),
                "requested_patterns": pattern_names,
                "retrieved_file_paths": obsidian_files,
            },
        }

        symbols_list: List[Any] = []
        if include_symbols:
            if self.symbol_retriever is None:
                from app.symbols.symbol_retriever import SymbolRetriever
                self.symbol_retriever = SymbolRetriever()

            seen_ids = set()
            for req in req_contexts:
                retrieval = self.symbol_retriever.get_symbols_for_requirement(req.srs_id)
                for sym in retrieval.symbols:
                    if sym.identifier not in seen_ids:
                        seen_ids.add(sym.identifier)
                        symbols_list.append(sym)

            provenance["symbols"] = {
                "source": "SymbolRegistry",
                "retrieved_count": len(symbols_list),
            }

        return ContextPackage(
            requirements=req_contexts,
            identified_patterns=pattern_names,
            obsidian_knowledge=obsidian_result,
            provenance=provenance,
            symbols=symbols_list,
            clarifications=clarifications or [],
        )
