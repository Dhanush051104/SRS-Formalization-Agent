#!/usr/bin/env python3
"""
demo_symbols.py

Standalone demonstration script for the SRS Formalization Agent Symbol Registry & Retrieval.
Demonstrates:
  1. Authoritative Symbol Registry loading and indexing.
  2. Querying globally applicable symbols and requirement-scoped symbols.
  3. Validating candidate formalizations against canonical symbol definitions.
  4. Reporting symbol consistency violations (out-of-scope usage, conflicting definitions, unregistered symbols).
"""

import sys
from pathlib import Path

# Add project root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.symbols.symbol_registry import SymbolRegistry
from app.symbols.symbol_retriever import SymbolRetriever
from app.symbols.symbol_validator import SymbolValidator


def main():
    print("=" * 70)
    print("SRS FORMALIZATION AGENT — SYMBOL REGISTRY & RETRIEVAL DEMO")
    print("=" * 70)

    # 1. Load the Authoritative Registry
    print("\n[1. LOADING AUTHORITATIVE SYMBOL REGISTRY]")
    registry = SymbolRegistry()
    registry.load()
    print(f"Registry Path    : {registry.registry_path}")
    print(f"Registry Version : {registry.version}")
    print(f"Total Symbols    : {len(registry)}")

    # 2. Retrieve Globally Applicable Symbols
    print("\n[2. GLOBAL SYMBOL RETRIEVAL]")
    retriever = SymbolRetriever(registry)
    global_res = retriever.get_global_symbols()
    print(f"Found {len(global_res.symbols)} globally applicable symbols:")
    for sym in global_res.symbols:
        aliases_str = f" (aliases: {sym.aliases})" if sym.aliases else ""
        print(f"  - [{sym.category}] '{sym.spelling}'{aliases_str} -> {sym.definition}")

    # 3. Retrieve Symbols for Target Requirement [SRS178]
    target_requirement = "[SRS178]"
    print(f"\n[3. REQUIREMENT-SPECIFIC SYMBOL RETRIEVAL: {target_requirement}]")
    req_res = retriever.get_symbols_for_requirement(target_requirement)
    print(f"Retrieved {len(req_res.symbols)} symbols relevant to {target_requirement}:")
    for sym in req_res.symbols:
        scope_tag = "GLOBAL" if sym.is_global() else f"SCOPED: {sym.scope}"
        aliases_str = f" (aliases: {sym.aliases})" if sym.aliases else ""
        print(f"  - [{scope_tag}] '{sym.spelling}'{aliases_str} [{sym.identifier}]")
        print(f"      Definition: {sym.definition}")

    # 4. Symbol Consistency Validation: Valid Candidate
    validator = SymbolValidator(registry)
    print("\n[4. VALIDATION CASE 1: Valid Candidate Formalization]")
    valid_formula = "G(loss_of_comm -> F[0, 10ms] outputs_disabled)"
    print(f"Target Scope : {target_requirement}")
    print(f"Formula      : \"{valid_formula}\"")
    report_valid = validator.validate_candidate(
        formalization=valid_formula,
        current_scope=target_requirement,
    )
    print(f"Validation Result : {'PASS (Valid)' if report_valid.is_valid else 'FAIL (Invalid)'}")
    print(f"Summary           : {report_valid.summary}")
    for v in report_valid.violations:
        print(f"  [{v.severity}] {v.rule}: {v.description}")

    # 5. Symbol Consistency Validation: Out-of-Scope Violation
    print("\n[5. VALIDATION CASE 2: Out-of-Scope Symbol Violation]")
    unscoped_target = "[SRS015]"
    print(f"Target Scope : {unscoped_target} (System Initialization)")
    print(f"Formula      : \"{valid_formula}\" (Using SRS178-specific symbols in SRS015)")
    report_out_of_scope = validator.validate_candidate(
        formalization=valid_formula,
        current_scope=unscoped_target,
    )
    print(f"Validation Result : {'PASS (Valid)' if report_out_of_scope.is_valid else 'FAIL (Invalid)'}")
    print(f"Summary           : {report_out_of_scope.summary}")
    for v in report_out_of_scope.violations:
        print(f"  [{v.severity}] {v.rule}: {v.description}")

    # 6. Symbol Consistency Validation: Conflicting Definition
    print("\n[6. VALIDATION CASE 3: Conflicting Symbol Definition]")
    conflict_definitions = {
        "G": "Ground state vehicle orientation indicator",
    }
    print(f"Formula               : \"G(loss_of_comm)\"")
    print(f"Candidate Definitions : {conflict_definitions}")
    report_conflict = validator.validate_candidate(
        formalization="G(loss_of_comm)",
        current_scope=target_requirement,
        candidate_definitions=conflict_definitions,
    )
    print(f"Validation Result : {'PASS (Valid)' if report_conflict.is_valid else 'FAIL (Invalid)'}")
    print(f"Summary           : {report_conflict.summary}")
    for v in report_conflict.violations:
        print(f"  [{v.severity}] {v.rule}: {v.description}")

    print("\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
