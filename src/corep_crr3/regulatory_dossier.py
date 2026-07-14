"""Regulatory readiness dossier gates.

VERSION : 6.10.0
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence, TypedDict

REQUIRED_GATES = (
    "official_taxonomy_package",
    "filing_rules_profile",
    "known_issues_review",
    "dpm_mapping_signed",
    "external_golden_dataset",
    "legal_review_signed",
    "github_live_ci_green",
)

REQUIRED_TRACEABILITY_COLUMNS = (
    "regulatory_reference",
    "template_or_table",
    "engine_module",
    "dpm_datapoint_or_kpi",
    "source_sql_or_input",
    "formula_or_rule",
    "control_or_test",
    "quality_status",
    "activation_status",
    "external_evidence",
    "status",
)

ALLOWED_GATE_STATUSES = {"NOT_EXECUTED", "PENDING", "FAILED", "PASSED"}
ALLOWED_TRACEABILITY_STATUSES = {"PENDING_EXTERNAL_SIGNOFF", "READY_FOR_REVIEW", "SIGNED_OFF"}
ALLOWED_QUALITY_STATUSES = {"OFFICIAL", "ESTIMATED", "PRECALCULATED_SOURCE", "DEMO_ONLY"}
PRODUCTION_BLOCKING_QUALITY_STATUSES = {"ESTIMATED", "PRECALCULATED_SOURCE", "DEMO_ONLY"}
OFFICIAL_SUBMISSION_ALLOWED_QUALITY_STATUSES = {"OFFICIAL"}
PHASE_1_ACTIVE_MODULES = {
    "standard_engine",
    "saccr_engine",
    "liquidity_engine",
    "own_funds_engine",
    "output_floor",
    "operational_risk_engine",
    "large_exposures_engine",
}
ALLOWED_ACTIVATION_STATUSES = {"PHASE_1_ACTIVE", "PHASE_2_CANDIDATE", "PHASE_3_INTERNAL", "NOT_ELIGIBLE"}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ReadinessGate:
    """One supervisor-readiness gate."""

    name: str
    status: str
    evidence: str = ""
    owner: str = ""
    evidence_sha256: str = ""

    @property
    def passed(self) -> bool:
        """Whether the gate is fully evidenced and passed."""
        return self.status.upper() == "PASSED"


def normalize_gates(payload: Mapping[str, object]) -> tuple[ReadinessGate, ...]:
    """Normalize a dossier JSON payload into typed gates."""
    raw = payload.get("gates", [])
    if not isinstance(raw, list):
        raise ValueError("gates must be a list")
    gates = tuple(
        ReadinessGate(
            name=str(item.get("name", "")),
            status=str(item.get("status", "NOT_EXECUTED")),
            evidence=str(item.get("evidence", "")),
            owner=str(item.get("owner", "")),
            evidence_sha256=str(item.get("evidence_sha256", "")),
        )
        for item in raw
        if isinstance(item, dict)
    )
    names = [gate.name for gate in gates]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError("duplicate readiness gates: " + ", ".join(duplicates))
    missing = [name for name in REQUIRED_GATES if name not in set(names)]
    if missing:
        raise ValueError("missing readiness gates: " + ", ".join(missing))
    invalid_statuses = sorted({gate.status for gate in gates if gate.status.upper() not in ALLOWED_GATE_STATUSES})
    if invalid_statuses:
        raise ValueError("invalid readiness gate status: " + ", ".join(invalid_statuses))
    return gates


def readiness_status(gates: Iterable[ReadinessGate]) -> str:
    """Return GO only when every required gate exists and has passed."""
    indexed = {gate.name: gate for gate in gates}
    if set(REQUIRED_GATES).issubset(indexed) and all(indexed[name].passed for name in REQUIRED_GATES):
        return "GO"
    return "NO_GO"


def activation_status_for_module(module: str, quality_status: str) -> str:
    """Classify an engine in the v6.9.0 phased Enterprise activation roadmap."""
    normalized_module = module.strip()
    normalized_quality = quality_status.strip().upper()
    if (
        normalized_module in PHASE_1_ACTIVE_MODULES
        and normalized_quality in OFFICIAL_SUBMISSION_ALLOWED_QUALITY_STATUSES
    ):
        return "PHASE_1_ACTIVE"
    if normalized_quality in PRODUCTION_BLOCKING_QUALITY_STATUSES:
        return "NOT_ELIGIBLE"
    if normalized_module in {"cva_engine", "irb_engine", "securitisation_engine", "stress_testing_engine"}:
        return "PHASE_2_CANDIDATE"
    return "PHASE_3_INTERNAL"


def external_artifact_requirements(*, version: str, edition: str) -> tuple[dict[str, str], ...]:
    """Return the external evidence expected before any official submission."""
    return (
        {
            "name": "official_taxonomy_package",
            "description": "EBA/NCA taxonomy package and checksum for the reporting reference date.",
            "minimum_evidence": "archive hash + source URL + filing date + reviewer sign-off",
        },
        {
            "name": "filing_rules_profile",
            "description": "Supervisor-specific filing rules profile used for the institution.",
            "minimum_evidence": "profile identifier + NCA/BCE applicability note + reviewer sign-off",
        },
        {
            "name": "known_issues_review",
            "description": "Known issues, limitations and residual risks reviewed for the release.",
            "minimum_evidence": "dated review note + issue register hash + release manager sign-off",
        },
        {
            "name": "dpm_mapping_signed",
            "description": f"{edition.upper()} v{version} DPM mapping independently reconciled cell by cell.",
            "minimum_evidence": "mapping workbook hash + maker/checker signatures + exception log",
        },
        {
            "name": "external_golden_dataset",
            "description": "Expected results generated outside this codebase for independent validation.",
            "minimum_evidence": "input hash + expected output hash + methodology note + reviewer sign-off",
        },
        {
            "name": "legal_review_signed",
            "description": "Commercial, EULA, IP, GDPR and liability review before sale or official filing.",
            "minimum_evidence": "legal memo hash + approval date + approver role",
        },
        {
            "name": "github_live_ci_green",
            "description": "Live CI evidence for the exact release commit or tag.",
            "minimum_evidence": "GitHub Actions URL + commit SHA + green check summary + reviewer sign-off",
        },
    )


# Named accountability for each external supervisor gate: (accountable owner,
# required signatory role). The register turns the gate list into an explicit,
# role-based sign-off ledger so that "who must sign what" is recorded rather
# than implicit. No signature is fabricated: the default register is fully
# NOT_SIGNED and therefore keeps the dossier fail-closed (NO_GO).
REQUIRED_SIGNOFF_STATUSES = ("NOT_SIGNED", "SIGNED")
_SIGNOFF_ACCOUNTABILITY: dict[str, tuple[str, str]] = {
    "official_taxonomy_package": ("Regulatory reporting owner", "Head of Regulatory Reporting"),
    "filing_rules_profile": ("Regulatory reporting owner", "Head of Regulatory Reporting"),
    "known_issues_review": ("Release manager", "Release Manager"),
    "dpm_mapping_signed": ("DPM mapping owner", "Independent Reviewer (maker/checker)"),
    "external_golden_dataset": ("Independent validator", "Independent Model Validation"),
    "legal_review_signed": ("Legal owner", "Legal Counsel"),
    "github_live_ci_green": ("Release manager", "Release Manager"),
}
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def signoff_register_template(*, version: str, edition: str) -> tuple[dict[str, str], ...]:
    """Build the role-based regulatory sign-off register (all NOT_SIGNED).

    One entry per required external gate, carrying the accountable owner, the
    required signatory role and an empty signature slot. The register is the
    auditable ledger recommended for production governance: it remains entirely
    unsigned until the responsible parties countersign, which keeps the dossier
    NO_GO via :func:`validate_signoff_register`.
    """
    requirements = {
        item["name"]: item["minimum_evidence"]
        for item in external_artifact_requirements(version=version, edition=edition)
    }
    register: list[dict[str, str]] = []
    for gate in REQUIRED_GATES:
        owner, signatory_role = _SIGNOFF_ACCOUNTABILITY[gate]
        register.append(
            {
                "gate": gate,
                "accountable_owner": owner,
                "required_signatory_role": signatory_role,
                "signature_status": "NOT_SIGNED",
                "signatory": "",
                "signature_date": "",
                "evidence_sha256": "",
                "minimum_evidence": requirements.get(gate, ""),
            }
        )
    return tuple(register)


def validate_signoff_register(payload: Mapping[str, object]) -> tuple[str, ...]:
    """Validate the regulatory sign-off register and enforce the GO coupling.

    Backward compatible: a payload without ``signoff_register`` is accepted
    (returns no error). When present, the register must cover every required
    gate exactly once with a valid status, and the fail-closed coupling is
    enforced both ways:

    * any ``NOT_SIGNED`` entry forbids ``submission_readiness == GO``;
    * a ``GO`` dossier requires every entry ``SIGNED`` with a 64-char
      ``evidence_sha256``, a named ``signatory`` and an ISO ``signature_date``.
    """
    if "signoff_register" not in payload:
        return ()
    register = payload.get("signoff_register")
    if not isinstance(register, list) or not register:
        return ("signoff_register must be a non-empty list",)
    errors: list[str] = []
    seen: list[str] = []
    is_go = str(payload.get("submission_readiness")) == "GO"
    any_unsigned = False
    for index, entry in enumerate(register, start=1):
        if not isinstance(entry, dict):
            errors.append(f"signoff_register row {index}: not an object")
            continue
        gate = str(entry.get("gate", ""))
        seen.append(gate)
        if not str(entry.get("accountable_owner", "")):
            errors.append(f"signoff_register row {index}: missing accountable_owner")
        if not str(entry.get("required_signatory_role", "")):
            errors.append(f"signoff_register row {index}: missing required_signatory_role")
        status = str(entry.get("signature_status", "")).upper()
        if status not in REQUIRED_SIGNOFF_STATUSES:
            errors.append(f"signoff_register row {index}: invalid signature_status {status!r}")
        if status != "SIGNED":
            any_unsigned = True
        else:
            if not _SHA256_RE.fullmatch(str(entry.get("evidence_sha256", ""))):
                errors.append(f"signoff_register row {index}: SIGNED entry requires a 64-char evidence_sha256")
            if not str(entry.get("signatory", "")):
                errors.append(f"signoff_register row {index}: SIGNED entry requires a signatory")
            if not _ISO_DATE_RE.fullmatch(str(entry.get("signature_date", ""))):
                errors.append(f"signoff_register row {index}: SIGNED entry requires an ISO signature_date")
    missing = [gate for gate in REQUIRED_GATES if gate not in seen]
    if missing:
        errors.append("signoff_register missing gate(s): " + ", ".join(missing))
    duplicates = sorted({gate for gate in seen if seen.count(gate) > 1})
    if duplicates:
        errors.append("signoff_register duplicate gate(s): " + ", ".join(duplicates))
    if any_unsigned and is_go:
        errors.append("submission_readiness GO requires every signoff_register entry SIGNED")
    return tuple(errors)


_TraceabilityRow = tuple[str, str, str, str, str, str, str, str]


_BASE_TRACEABILITY_ROWS: tuple[_TraceabilityRow, ...] = (
    (
        "CRR3 Standardised Approach",
        "COREP C 07.00",
        "standard_engine",
        "C07 RW/EAD/RWA",
        "sql/03_mapping/01_mapping_corep_templates.sql",
        "RWA = EAD post-CRM x regulatory risk weight",
        "tests/test_standard_refactor.py",
        "OFFICIAL",
    ),
    (
        "CRR3 SA-CCR",
        "COREP C 34.x",
        "saccr_engine",
        "C34 replacement cost / PFE / EAD",
        "sql/03_mapping/01_mapping_corep_templates.sql",
        "EAD = alpha x (RC + multiplier x AddOn)",
        "tests/test_v5_0_1_coverage.py",
        "OFFICIAL",
    ),
)


_ENTERPRISE_TRACEABILITY_ROWS: tuple[_TraceabilityRow, ...] = (
    (
        "CRR3 Liquidity",
        "LCR C 72-76 / NSFR C 80-84",
        "liquidity_engine",
        "HQLA / outflows / inflows / ASF / RSF",
        "sql/03_mapping/06_mapping_regulatory_bcnf_v5_0_6.sql",
        "LCR and NSFR regulatory aggregation rules",
        "tests/test_v6_3_4_consolidation.py",
        "OFFICIAL",
    ),
    (
        "CRR3 CVA Art.382-386",
        "COREP CVA templates",
        "cva_engine",
        "BA-CVA / SA-CVA / simplified CVA charge",
        "sql/03_mapping/06_mapping_regulatory_bcnf_v5_0_6.sql",
        "CRR3 CVA own-funds requirement by selected approach",
        "tests/test_cva_reference_values.py",
        "OFFICIAL",
    ),
    (
        "CRR3 SFT Art.220-226",
        "COREP counterparty credit risk SFT",
        "sft_engine",
        "SFT EAD / collateral volatility adjustments",
        "sql/03_mapping/06_mapping_regulatory_bcnf_v5_0_6.sql",
        "SFT exposure after collateral, haircuts, netting and maturity "
        "adjustment; official submission requires external reference case",
        "tests/test_v5_0_6_regulatory_completion.py",
        "ESTIMATED",
    ),
    (
        "CRR3 IRB Art.153-181",
        "COREP IRB templates",
        "irb_engine",
        "IRB PD/LGD/EAD/RWA",
        "sql/03_mapping/06_mapping_regulatory_bcnf_v5_0_6.sql",
        "IRB supervisory formula and model parameters",
        "tests/test_irb_final_standard_v4_4_10.py",
        "OFFICIAL",
    ),
    (
        "CRR3 Output Floor Art.92(4)",
        "COREP own funds / TREA",
        "output_floor",
        "TREA post-floor",
        "sql/03_mapping/06_mapping_regulatory_bcnf_v5_0_6.sql",
        "TREA = max(modelled TREA, floor percentage x standardised TREA)",
        "tests/test_v6_0_0_release_industrialisation.py",
        "OFFICIAL",
    ),
    (
        "CRR3 Own Funds",
        "COREP C 01.00 / C 03.00",
        "own_funds_engine",
        "CET1 / Tier1 / Total capital ratios",
        "sql/03_mapping/06_mapping_regulatory_bcnf_v5_0_6.sql",
        "Capital ratios after deductions and TREA selection",
        "tests/test_own_funds_activation.py",
        "OFFICIAL",
    ),
    (
        "CRR3 Operational Risk",
        "COREP operational risk templates",
        "operational_risk_engine",
        "Business indicator / own-funds requirement",
        "sql/03_mapping/06_mapping_regulatory_bcnf_v5_0_6.sql",
        "Standardised business indicator component aggregation",
        "tests/test_operational_risk_activation.py",
        "OFFICIAL",
    ),
    (
        "CRR3 Large Exposures",
        "COREP C 27-C 31",
        "large_exposures_engine",
        "LE exposure values and limit utilisation",
        "sql/03_mapping/06_mapping_regulatory_bcnf_v5_0_6.sql",
        "Large exposure aggregation and limit checks",
        "tests/test_large_exposures_engine.py",
        "OFFICIAL",
    ),
    (
        "CRR3 Securitisation",
        "COREP securitisation templates",
        "securitisation_engine",
        "SEC-SA / SEC-ERBA RWA",
        "sql/03_mapping/06_mapping_regulatory_bcnf_v5_0_6.sql",
        "Securitisation hierarchy and capital floor rules",
        "tests/test_v5_0_6_regulatory_completion.py",
        "OFFICIAL",
    ),
    (
        "CRR3 Crypto-assets",
        "COREP crypto-asset exposure templates",
        "crypto_assets_engine",
        "Crypto exposure classification and capital add-on",
        "sql/03_mapping/06_mapping_regulatory_bcnf_v5_0_6.sql",
        "CRR3 transitional crypto-asset exposure treatment",
        "tests/test_crypto_assets_engine.py",
        "OFFICIAL",
    ),
    (
        "FRTB Standardised Approach",
        "COREP market risk templates",
        "market_risk_engine",
        "Delta / vega / curvature / DRC / RRAO",
        "sql/03_mapping/06_mapping_regulatory_bcnf_v5_0_6.sql",
        "FRTB SA aggregation; curvature, DRC and RRAO require reconciled source or external model evidence",
        "tests/test_market_risk_regulatory_v5_0_3.py",
        "PRECALCULATED_SOURCE",
    ),
    (
        "FRTB Simplified Standardised Approach",
        "COREP market risk simplified templates",
        "mr_ssa_engine",
        "SSA own-funds requirement",
        "sql/03_mapping/06_mapping_regulatory_bcnf_v5_0_6.sql",
        "Simplified small trading book calculation",
        "tests/test_v6_3_2_p1.py",
        "OFFICIAL",
    ),
    (
        "FRTB transitional 2027-2029",
        "Market risk transitional overlay",
        "frtb_transitional",
        "Transitional multiplier / floor overlay",
        "sql/03_mapping/06_mapping_regulatory_bcnf_v5_0_6.sql",
        "CRR3 transitional scaling governance",
        "tests/test_v6_3_2_p1.py",
        "OFFICIAL",
    ),
    (
        "CRR3 Stress Testing",
        "Internal regulatory KPI stress overlay",
        "stress_testing_engine",
        "Scenario-stressed regulatory KPIs",
        "sql/03_mapping/06_mapping_regulatory_bcnf_v5_0_6.sql",
        "Deterministic scenario shocks over signed-off base KPIs",
        "tests/test_stress_testing_engine.py",
        "OFFICIAL",
    ),
    (
        "FINREP management bridge",
        "FINREP templates",
        "finrep_excel_filler",
        "NII / fees / cost-income / impairment bridge",
        "manual FINREP workbook source",
        "Workbook fill rules; estimates are forbidden in official submission profile",
        "tests/test_v6_3_4_consolidation.py",
        "ESTIMATED",
    ),
    (
        "DPM/XBRL internal export",
        "DPM 2.0 / xBRL-CSV internal package",
        "dpm_xbrl_exporter",
        "DPM fact package",
        "sql/03_mapping/12_mapping_dpm_xbrl.sql",
        "Internal taxonomy export; official xBRL-CSV requires external taxonomy validator evidence",
        "tests/test_v5_2_0_dpm_submission.py",
        "DEMO_ONLY",
    ),
)


def _traceability_rows_for_edition(edition: str) -> tuple[_TraceabilityRow, ...]:
    """Return the complete CRR3/DPM coverage inventory for one edition."""
    rows = list(_BASE_TRACEABILITY_ROWS)
    if edition.upper() == "ENTERPRISE":
        rows.extend(_ENTERPRISE_TRACEABILITY_ROWS)
    return tuple(rows)


def traceability_matrix_template(*, edition: str) -> tuple[dict[str, str], ...]:
    """Return a fail-closed CRR/DPM traceability template."""
    rows = _traceability_rows_for_edition(edition)
    return tuple(
        {
            "regulatory_reference": reference,
            "template_or_table": template,
            "engine_module": module,
            "dpm_datapoint_or_kpi": datapoint,
            "source_sql_or_input": source,
            "formula_or_rule": formula,
            "control_or_test": control,
            "quality_status": quality,
            "activation_status": activation_status_for_module(module, quality),
            "external_evidence": "PENDING_EXTERNAL_SIGNOFF",
            "status": "PENDING_EXTERNAL_SIGNOFF",
        }
        for reference, template, module, datapoint, source, formula, control, quality in rows
    )


def quality_status_summary(payload: Mapping[str, object]) -> dict[str, int]:
    """Count traceability rows by KPI quality status."""
    summary = {status: 0 for status in sorted(ALLOWED_QUALITY_STATUSES)}
    matrix = payload.get("traceability_matrix", [])
    if not isinstance(matrix, list):
        return summary
    for row in matrix:
        if not isinstance(row, dict):
            continue
        status = str(row.get("quality_status", "")).upper()
        if status in summary:
            summary[status] += 1
    return {key: value for key, value in summary.items() if value}


class OfficialSubmissionScope(TypedDict):
    """Perimetre de soumission officielle derive de la matrice de tracabilite."""

    scope_name: str
    policy: str
    included_engine_modules: list[str]
    excluded_engine_modules: list[dict[str, str]]


def official_submission_scope_from_matrix(matrix: Sequence[Mapping[str, object]]) -> OfficialSubmissionScope:
    """Split the full Enterprise inventory from the strict official submission scope.

    Enterprise may contain internal/demo calculations.  They are kept in the
    inventory for transparency, but they must be excluded from the official
    submission scope until independently evidenced and reclassified.
    """
    included: list[str] = []
    excluded: list[dict[str, str]] = []
    for row in matrix:
        module = str(row.get("engine_module", "")).strip()
        quality = str(row.get("quality_status", "")).upper()
        if not module:
            continue
        activation = str(row.get("activation_status", "")).upper()
        if quality in OFFICIAL_SUBMISSION_ALLOWED_QUALITY_STATUSES and activation == "PHASE_1_ACTIVE":
            included.append(module)
        else:
            reason = (
                "Excluded from Phase 1 official scope until the activation stage is promoted and externally signed off."
            )
            if quality in PRODUCTION_BLOCKING_QUALITY_STATUSES:
                reason = "Excluded from official submission until external reference evidence is signed off."
            excluded.append(
                {
                    "engine_module": module,
                    "quality_status": quality,
                    "activation_status": activation or activation_status_for_module(module, quality),
                    "reason": reason,
                }
            )
    return {
        "scope_name": "OFFICIAL_SUBMISSION",
        "policy": "Only OFFICIAL traceability rows may enter a regulatory submission profile.",
        "included_engine_modules": sorted(set(included)),
        "excluded_engine_modules": sorted(excluded, key=lambda item: item["engine_module"]),
    }


def validate_official_submission_scope(payload: Mapping[str, object]) -> tuple[str, ...]:
    """Validate the explicit split between official and internal/demo scope."""
    matrix = payload.get("traceability_matrix", [])
    scope = payload.get("official_submission_scope")
    if not isinstance(matrix, list):
        return ("traceability_matrix must be a list before validating official_submission_scope",)
    expected = official_submission_scope_from_matrix([row for row in matrix if isinstance(row, Mapping)])
    if not isinstance(scope, Mapping):
        return ("official_submission_scope must be present",)
    errors: list[str] = []
    included = sorted(str(item) for item in scope.get("included_engine_modules", []))
    expected_included = sorted(str(item) for item in expected["included_engine_modules"])
    if included != expected_included:
        errors.append(
            "official_submission_scope included_engine_modules is not aligned with PHASE_1_ACTIVE OFFICIAL rows"
        )
    raw_excluded = scope.get("excluded_engine_modules", [])
    if not isinstance(raw_excluded, list):
        errors.append("official_submission_scope excluded_engine_modules must be a list")
        raw_excluded = []
    excluded_pairs = sorted(
        (
            str(item.get("engine_module", "")),
            str(item.get("quality_status", "")).upper(),
            str(item.get("activation_status", "")).upper(),
        )
        for item in raw_excluded
        if isinstance(item, Mapping)
    )
    expected_pairs = sorted(
        (
            str(item["engine_module"]),
            str(item["quality_status"]).upper(),
            str(item["activation_status"]).upper(),
        )
        for item in expected["excluded_engine_modules"]
    )
    if excluded_pairs != expected_pairs:
        errors.append("official_submission_scope excluded_engine_modules is not aligned with non-OFFICIAL rows")
    return tuple(errors)


def build_fail_closed_dossier(*, version: str, edition: str) -> dict[str, object]:
    """Create the default fail-closed supervisor dossier."""
    gates = [
        {
            "name": "official_taxonomy_package",
            "status": "NOT_EXECUTED",
            "owner": "Regulatory reporting owner",
            "evidence": "External EBA/NCA package not bundled",
            "evidence_sha256": "",
        },
        {
            "name": "filing_rules_profile",
            "status": "NOT_EXECUTED",
            "owner": "Regulatory reporting owner",
            "evidence": "Supervisor profile must be selected at deployment",
            "evidence_sha256": "",
        },
        {
            "name": "known_issues_review",
            "status": "NOT_EXECUTED",
            "owner": "Release manager",
            "evidence": "Review must be dated and signed",
            "evidence_sha256": "",
        },
        {
            "name": "dpm_mapping_signed",
            "status": "NOT_EXECUTED",
            "owner": "DPM mapping owner",
            "evidence": "Independent DPM sign-off required",
            "evidence_sha256": "",
        },
        {
            "name": "external_golden_dataset",
            "status": "NOT_EXECUTED",
            "owner": "Independent validator",
            "evidence": "Golden dataset must be generated outside this codebase",
            "evidence_sha256": "",
        },
        {
            "name": "legal_review_signed",
            "status": "NOT_EXECUTED",
            "owner": "Legal owner",
            "evidence": "Legal review required before sale or official filing",
            "evidence_sha256": "",
        },
        {
            "name": "github_live_ci_green",
            "status": "NOT_EXECUTED",
            "owner": "Release manager",
            "evidence": "Attach GitHub Actions run URLs for the release tag",
            "evidence_sha256": "",
        },
    ]
    traceability_matrix = list(traceability_matrix_template(edition=edition))
    payload: dict[str, object] = {
        "schema_version": 2,
        "product_version": version,
        "edition": edition.upper(),
        "submission_readiness": "NO_GO",
        "fail_closed": True,
        "gates": gates,
        "external_artifact_requirements": list(external_artifact_requirements(version=version, edition=edition)),
        "signoff_register": list(signoff_register_template(version=version, edition=edition)),
        "traceability_matrix": traceability_matrix,
    }
    payload["quality_status_summary"] = quality_status_summary(payload)
    payload["official_submission_scope"] = official_submission_scope_from_matrix(traceability_matrix)
    return payload


def _validate_passed_gate(gate: ReadinessGate) -> tuple[str, ...]:
    """Validate the evidence payload attached to a PASSED supervisor gate."""
    errors: list[str] = []
    if gate.passed and not _SHA256_RE.fullmatch(gate.evidence_sha256):
        errors.append(f"{gate.name}: PASSED gate requires a lowercase 64-character evidence_sha256")
    if gate.passed and not gate.owner:
        errors.append(f"{gate.name}: PASSED gate requires an owner")
    if gate.passed and not gate.evidence:
        errors.append(f"{gate.name}: PASSED gate requires evidence")
    return tuple(errors)


def validate_traceability_matrix(payload: Mapping[str, object]) -> tuple[str, ...]:
    """Validate the CRR/DPM traceability matrix shape and production eligibility."""
    matrix = payload.get("traceability_matrix", [])
    if not isinstance(matrix, list) or not matrix:
        return ("traceability_matrix must be a non-empty list",)
    errors: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for index, row in enumerate(matrix, start=1):
        if not isinstance(row, dict):
            errors.append(f"traceability_matrix row {index}: not an object")
            continue
        for column in REQUIRED_TRACEABILITY_COLUMNS:
            if not str(row.get(column, "")):
                errors.append(f"traceability_matrix row {index}: missing {column}")
        key = (
            str(row.get("regulatory_reference", "")),
            str(row.get("template_or_table", "")),
            str(row.get("engine_module", "")),
        )
        if key in seen:
            errors.append(f"traceability_matrix row {index}: duplicate regulatory coverage key")
        seen.add(key)
        quality_status = str(row.get("quality_status", "")).upper()
        if quality_status and quality_status not in ALLOWED_QUALITY_STATUSES:
            errors.append(f"traceability_matrix row {index}: invalid quality_status {quality_status}")
        status = str(row.get("status", "")).upper()
        if status and status not in ALLOWED_TRACEABILITY_STATUSES:
            errors.append(f"traceability_matrix row {index}: invalid status {status}")
        activation_status = str(row.get("activation_status", "")).upper()
        if activation_status and activation_status not in ALLOWED_ACTIVATION_STATUSES:
            errors.append(f"traceability_matrix row {index}: invalid activation_status {activation_status}")
    if str(payload.get("submission_readiness")) == "GO":
        for index, row in enumerate(matrix, start=1):
            if not isinstance(row, dict):
                continue
            quality_status = str(row.get("quality_status", "")).upper()
            if quality_status in PRODUCTION_BLOCKING_QUALITY_STATUSES:
                errors.append(
                    f"traceability_matrix row {index}: {quality_status} output cannot be used for official GO"
                )
            if str(row.get("status", "")).upper() != "SIGNED_OFF":
                errors.append(f"traceability_matrix row {index}: official GO requires SIGNED_OFF traceability")
    return tuple(errors)


def validate_external_artifact_requirements(payload: Mapping[str, object]) -> tuple[str, ...]:
    """Validate that every supervisor gate has an explicit evidence requirement."""
    raw = payload.get("external_artifact_requirements", [])
    if not isinstance(raw, list) or not raw:
        return ("external_artifact_requirements must be a non-empty list",)
    names = {str(item.get("name", "")) for item in raw if isinstance(item, dict)}
    missing = [name for name in REQUIRED_GATES if name not in names]
    errors = [f"external_artifact_requirements missing gate: {name}" for name in missing]
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            errors.append(f"external_artifact_requirements row {index}: not an object")
            continue
        for column in ("name", "description", "minimum_evidence"):
            if not str(item.get(column, "")):
                errors.append(f"external_artifact_requirements row {index}: missing {column}")
    return tuple(errors)


def validate_dossier(payload: Mapping[str, object]) -> tuple[str, ...]:
    """Validate a regulatory dossier and return blocking errors."""
    errors: list[str] = []
    try:
        gates = normalize_gates(payload)
    except ValueError as exc:
        return (str(exc),)
    expected = readiness_status(gates)
    if str(payload.get("submission_readiness")) != expected:
        errors.append(f"submission_readiness must be {expected}")
    if expected != "GO" and payload.get("fail_closed") is not True:
        errors.append("fail_closed must be true while supervisor readiness is not GO")
    if expected == "GO" and payload.get("fail_closed") is True:
        errors.append("fail_closed must be false only after all supervisor gates are externally evidenced")
    for gate in gates:
        errors.extend(_validate_passed_gate(gate))
    errors.extend(validate_external_artifact_requirements(payload))
    errors.extend(validate_signoff_register(payload))
    errors.extend(validate_traceability_matrix(payload))
    errors.extend(validate_official_submission_scope(payload))
    return tuple(errors)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI validator/generator for supervisor readiness evidence."""
    parser = argparse.ArgumentParser(description="Validate regulatory readiness dossier")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--generate", type=Path)
    parser.add_argument("--version", default="6.9.0")
    parser.add_argument("--edition", choices=("COMMUNITY", "ENTERPRISE"), default="ENTERPRISE")
    args = parser.parse_args(argv)
    if args.generate:
        payload = build_fail_closed_dossier(version=args.version, edition=args.edition)
        args.generate.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        args.generate.write_text(serialized, encoding="utf-8")
        print(f"Wrote regulatory dossier to {args.generate}")
        return 0
    if not args.input:
        parser.error("--input is required unless --generate is used")
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    errors = validate_dossier(payload)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK regulatory dossier: {payload.get('submission_readiness')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
