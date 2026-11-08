"""Bounded external official-source challenge; no exposure calculation.

This script verifies already acquired official PDFs, classifies publicly exposed
fields without a readiness score, reproduces selected printed arithmetic, and
screens two historical exposure reports for reuse feasibility.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "01_protocol/external_source_challenge_v36.md"


def load_config() -> dict[str, str]:
    config: dict[str, str] = {}
    for line in (ROOT / "00_admin/paths.yaml").read_text().splitlines():
        match = re.match(r'^([a-z_]+):\s*"(.*)"\s*$', line)
        if match:
            config[match.group(1)] = match.group(2)
    assert Path(config["project_root"]).resolve() == ROOT
    return config


CFG = load_config()
OUT = Path(CFG["outputs_root"]) / "manuscript_grilling_v36/external_source_challenge"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def page_count(path: Path) -> int:
    result = subprocess.run(["pdfinfo", str(path)], check=True, capture_output=True, text=True)
    match = re.search(r"^Pages:\s+(\d+)\s*$", result.stdout, flags=re.MULTILINE)
    assert match, f"No page count: {path}"
    return int(match.group(1))


def pdf_envelope(path: Path) -> bool:
    with path.open("rb") as stream:
        head = stream.read(8)
        stream.seek(max(0, path.stat().st_size - 4096))
        tail = stream.read()
    return head.startswith(b"%PDF-") and b"%%EOF" in tail


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    assert rows or fields
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def check_paths() -> str:
    result = subprocess.run(
        [sys.executable, str(ROOT / "05_code/utilities/check_paths.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0 and "PASS overall" in result.stdout, result.stdout + result.stderr
    return result.stdout


def load_receipt_files() -> list[dict]:
    specs = [
        ("Thailand FDA surveillance", "00_admin/thailand_fda_pesticide_surveillance_admission_20261016.json", "files"),
        ("Thailand ACFS GAP/Q-mark", "00_admin/thailand_acfs_gap_qmark_pesticide_monitoring_admission_20261016.json", "files"),
        ("Thailand THRASFF alerts", "00_admin/thailand_thrasff_annual_report_2025_admission_20261016.json", "file"),
        ("Thailand THRASFF system guide", "00_admin/thailand_thrasff_system_guide_2021_admission_20261016.json", "file"),
        ("Israel State Comptroller audit", "00_admin/israel_state_comptroller_pesticide_audit_2023_admission_20261016.json", "files"),
        ("Israel MoH 2012 risk report", "00_admin/israel_moh_risk_analysis_2012_admission_20261016.json", "root"),
    ]
    records: list[dict] = []
    for family, relative, kind in specs:
        receipt_path = ROOT / relative
        payload = json.loads(receipt_path.read_text())
        if kind == "files":
            entries = payload["files"]
        elif kind == "file":
            entries = [payload["file"]]
        else:
            entries = [payload]
        for entry in entries:
            records.append(
                dict(
                    source_family=family,
                    receipt_path=str(receipt_path),
                    raw_path=entry["raw_path"],
                    expected_bytes=int(entry["bytes"]),
                    expected_sha256=entry["sha256"],
                    expected_pages=int(entry["pages"]),
                    source_period=entry.get("period") or entry.get("language") or payload.get("period") or payload.get("result"),
                    official_url=entry.get("official_url") or payload.get("official_url"),
                )
            )

    belgium_receipt = ROOT / "00_admin/zenodo_residue_context_receipt_20261015.json"
    payload = json.loads(belgium_receipt.read_text())
    entry = next(row for row in payload["records"] if row["source_id"] == "BELGIUM_FASFC_EXPOSURE_2008")
    records.append(
        dict(
            source_family="Belgium FASFC 2008 exposure report",
            receipt_path=str(belgium_receipt),
            raw_path=entry["raw_path"],
            expected_bytes=int(entry["bytes"]),
            expected_sha256=entry["sha256"],
            expected_pages=int(entry["pages"]),
            source_period=entry["version"],
            official_url=entry["url"],
        )
    )
    assert len(records) == 19, len(records)
    return records


def read_manifest() -> list[dict[str, str]]:
    with (ROOT / "00_admin/download_manifest.csv").open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def verify_sources() -> list[dict]:
    manifest = read_manifest()
    output: list[dict] = []
    for expected in load_receipt_files():
        path = Path(expected["raw_path"])
        assert path.is_file(), path
        actual_bytes = path.stat().st_size
        actual_sha = sha256(path)
        actual_pages = page_count(path)
        envelope = pdf_envelope(path)
        manifest_matches = [
            row for row in manifest
            if row["local_file_path"] == str(path)
            and row["sha256"] == actual_sha
            and int(row["bytes"]) == actual_bytes
        ]
        checks = {
            "bytes_match_receipt": actual_bytes == expected["expected_bytes"],
            "sha256_match_receipt": actual_sha == expected["expected_sha256"],
            "pages_match_receipt": actual_pages == expected["expected_pages"],
            "pdf_envelope_pass": envelope,
            "manifest_exact_match": bool(manifest_matches),
        }
        assert all(checks.values()), (path, checks)
        output.append(
            {
                "source_family": expected["source_family"],
                "source_period": expected["source_period"],
                "raw_path": str(path),
                "bytes": actual_bytes,
                "sha256": actual_sha,
                "pages": actual_pages,
                "manifest_download_id": manifest_matches[-1]["download_id"],
                "receipt_path": expected["receipt_path"],
                "official_url": expected["official_url"],
                **{key: "PASS" if value else "FAIL" for key, value in checks.items()},
            }
        )
    return output


FIELDS = [
    "sample_id",
    "commodity",
    "pesticide_analyte",
    "quantitative_concentration",
    "non_detect_information",
    "lod_loq",
    "risk_assessment_residue_definition",
    "sampling_year",
    "food_form",
    "country_market_frame",
    "organic_conventional_status",
    "compatible_dietary_linkage",
]


def field_matrix() -> tuple[list[dict], dict]:
    rows = [
        {
            "source_family": "Thailand FDA surveillance",
            "sample_id": "NO",
            "commodity": "PARTIAL_AGGREGATE",
            "pesticide_analyte": "NO",
            "quantitative_concentration": "NO",
            "non_detect_information": "NO",
            "lod_loq": "NO",
            "risk_assessment_residue_definition": "NO",
            "sampling_year": "YES_AGGREGATE_ONLY",
            "food_form": "YES_AGGREGATE_ONLY",
            "country_market_frame": "YES_AGGREGATE_ONLY",
            "organic_conventional_status": "NO",
            "compatible_dietary_linkage": "NO",
            "evidence_level": "LEVEL_D",
            "scientific_role": "aggregate regulatory-compliance context",
            "evidence_locator": "FY2024 imported release p1; domestic FY2023-FY2024 release p1",
            "recommendation": "Do not create exposure units; retain as contextual evidence only.",
        },
        {
            "source_family": "Thailand ACFS GAP/Q-mark",
            "sample_id": "NO",
            "commodity": "PARTIAL_AGGREGATE",
            "pesticide_analyte": "PARTIAL_AGGREGATE",
            "quantitative_concentration": "NO",
            "non_detect_information": "PARTIAL_AGGREGATE",
            "lod_loq": "NO",
            "risk_assessment_residue_definition": "NO",
            "sampling_year": "YES_AGGREGATE_ONLY",
            "food_form": "YES_AGGREGATE_ONLY",
            "country_market_frame": "YES_AGGREGATE_ONLY",
            "organic_conventional_status": "NO",
            "compatible_dietary_linkage": "NO",
            "evidence_level": "LEVEL_D",
            "scientific_role": "aggregate Q-mark/GAP surveillance context",
            "evidence_locator": "FY2019 PDF p54; FY2020 pp74-75; FY2023 p78; FY2024 p57; FY2025 pp84-85",
            "recommendation": "Do not equate GAP/Q-mark with organic; do not calculate exposure from compliance totals.",
        },
        {
            "source_family": "Thailand THRASFF alerts",
            "sample_id": "NO",
            "commodity": "PARTIAL_AGGREGATE",
            "pesticide_analyte": "PARTIAL_AGGREGATE",
            "quantitative_concentration": "NO",
            "non_detect_information": "NO",
            "lod_loq": "NO",
            "risk_assessment_residue_definition": "NO",
            "sampling_year": "YES_AGGREGATE_ONLY",
            "food_form": "PARTIAL_AGGREGATE",
            "country_market_frame": "PARTIAL_AGGREGATE",
            "organic_conventional_status": "NO",
            "compatible_dietary_linkage": "NO",
            "evidence_level": "LEVEL_D",
            "scientific_role": "alert-system context without sampling denominator",
            "evidence_locator": "FY2025 annual report pp11-15, 19-25, 32",
            "recommendation": "Do not treat alerts as prevalence, concentration, or exposure observations.",
        },
        {
            "source_family": "Thailand THRASFF system guide",
            "sample_id": "NO",
            "commodity": "SCHEMA_ONLY",
            "pesticide_analyte": "SCHEMA_ONLY",
            "quantitative_concentration": "NO",
            "non_detect_information": "NO",
            "lod_loq": "NO",
            "risk_assessment_residue_definition": "NO",
            "sampling_year": "SCHEMA_ONLY",
            "food_form": "SCHEMA_ONLY",
            "country_market_frame": "SCHEMA_ONLY",
            "organic_conventional_status": "NO",
            "compatible_dietary_linkage": "NO",
            "evidence_level": "LEVEL_D",
            "scientific_role": "system-method and reporting-bias context",
            "evidence_locator": "2021 guide pp8-12, 24, 26-27",
            "recommendation": "A named template field is not an acquired observation; retain as method context.",
        },
        {
            "source_family": "Israel State Comptroller audit",
            "sample_id": "NO",
            "commodity": "PARTIAL_AGGREGATE",
            "pesticide_analyte": "PARTIAL_AGGREGATE",
            "quantitative_concentration": "NO",
            "non_detect_information": "PARTIAL_AGGREGATE",
            "lod_loq": "NO",
            "risk_assessment_residue_definition": "NO",
            "sampling_year": "YES_AGGREGATE_ONLY",
            "food_form": "PARTIAL_AGGREGATE",
            "country_market_frame": "YES_AGGREGATE_ONLY",
            "organic_conventional_status": "NO",
            "compatible_dietary_linkage": "NO",
            "evidence_level": "LEVEL_D",
            "scientific_role": "regulatory-governance and sampling context",
            "evidence_locator": "2017 Hebrew PDF pp5,34; 2023 English PDF pp4,8",
            "recommendation": "Retain as governance context; no exposure-unit admission.",
        },
        {
            "source_family": "Israel MoH 2012 risk report",
            "sample_id": "NO",
            "commodity": "YES_AGGREGATE_ONLY",
            "pesticide_analyte": "YES_AGGREGATE_ONLY",
            "quantitative_concentration": "YES_AGGREGATE_ONLY",
            "non_detect_information": "REPORT_INTERNAL_ONLY",
            "lod_loq": "REPORT_INTERNAL_ONLY",
            "risk_assessment_residue_definition": "NO",
            "sampling_year": "YES_AGGREGATE_ONLY",
            "food_form": "PARTIAL_AGGREGATE",
            "country_market_frame": "YES_AGGREGATE_ONLY",
            "organic_conventional_status": "NO",
            "compatible_dietary_linkage": "REPORT_INTERNAL_ONLY",
            "evidence_level": "LEVEL_C",
            "scientific_role": "historical official exposure-method comparator",
            "evidence_locator": "2012 report pp7-9 and appendices 2-9; monitoring period 2006-2010",
            "recommendation": "Do not import report aggregates as current parent units; cite only as historical method context.",
        },
        {
            "source_family": "Belgium FASFC 2008 exposure report",
            "sample_id": "NO",
            "commodity": "YES_AGGREGATE_ONLY",
            "pesticide_analyte": "YES_AGGREGATE_ONLY",
            "quantitative_concentration": "YES_AGGREGATE_ONLY",
            "non_detect_information": "REPORT_INTERNAL_ONLY",
            "lod_loq": "REPORT_INTERNAL_ONLY",
            "risk_assessment_residue_definition": "PARTIAL_AGGREGATE",
            "sampling_year": "YES_AGGREGATE_ONLY",
            "food_form": "YES_AGGREGATE_ONLY",
            "country_market_frame": "YES_AGGREGATE_ONLY",
            "organic_conventional_status": "NO",
            "compatible_dietary_linkage": "REPORT_INTERNAL_ONLY",
            "evidence_level": "LEVEL_C",
            "scientific_role": "historical official exposure-method comparator; branch-isolated",
            "evidence_locator": "2010 advice using 2008 monitoring, sections 3.1-3.2",
            "recommendation": "No parent-data admission; preserve plant-trade branch isolation and use as citation-level comparator only.",
        },
    ]
    allowed = {
        "YES_ROW_LEVEL",
        "YES_AGGREGATE_ONLY",
        "PARTIAL_AGGREGATE",
        "SCHEMA_ONLY",
        "REPORT_INTERNAL_ONLY",
        "NO",
    }
    for row in rows:
        assert all(row[field] in allowed for field in FIELDS)
    notes = {
        "no_numeric_score": True,
        "GAP_Q_mark_not_organic": True,
        "compliance_not_concentration_or_exposure": True,
        "alerts_not_sampling_denominators": True,
        "branch_isolation_preserved": True,
        "field_definitions": {
            "YES_ROW_LEVEL": "Reusable row-level observation is exposed.",
            "YES_AGGREGATE_ONLY": "Item is exposed only at an aggregate/report level.",
            "PARTIAL_AGGREGATE": "Incomplete or grouped aggregate is exposed.",
            "SCHEMA_ONLY": "Documentation names a field but supplies no observation.",
            "REPORT_INTERNAL_ONLY": "Supports the report's calculation but is not independently linkable from the public artifact.",
            "NO": "Not exposed in the acquired public artifact.",
        },
    }
    return rows, notes


def check_row(rows: list[dict], *, check_id: str, source: str, locator: str,
              identity: str, left: int | Decimal, right: int | Decimal,
              printed_values: str, interpretation: str) -> None:
    delta = Decimal(str(left)) - Decimal(str(right))
    rows.append(
        {
            "check_id": check_id,
            "source": source,
            "source_locator": locator,
            "identity": identity,
            "left_value": str(left),
            "right_value": str(right),
            "difference_left_minus_right": str(delta),
            "status": "PASS" if delta == 0 else "CONTRADICTION",
            "printed_values": printed_values,
            "interpretation": interpretation,
        }
    )


def arithmetic_checks() -> list[dict]:
    rows: list[dict] = []
    source = "Thailand ACFS Annual Report 2020"

    table72 = [
        ("certified", 70, 42, 17, 59, 11),
        ("non_certified", 16, 9, 3, 12, 4),
        ("imported", 14, 7, 7, 14, 0),
        ("total", 100, 58, 27, 85, 15),
    ]
    for name, samples, nd, within, safe, unsafe in table72:
        printed = f"samples={samples}; not_detected={nd}; within={within}; safe={safe}; unsafe={unsafe}"
        check_row(rows, check_id=f"ACFS2020_P72_{name}_safe_components", source=source,
                  locator="PDF p74 / printed p72", identity="printed safe = not detected + within limit",
                  left=safe, right=nd + within, printed_values=printed,
                  interpretation="Exact additive identity within the printed row.")
        check_row(rows, check_id=f"ACFS2020_P72_{name}_partition", source=source,
                  locator="PDF p74 / printed p72", identity="samples = printed safe + unsafe",
                  left=samples, right=safe + unsafe, printed_values=printed,
                  interpretation="Exact partition identity within the printed row.")

    for index, field in enumerate(["samples", "not_detected", "within", "safe", "unsafe"], start=1):
        subgroup_sum = sum(row[index] for row in table72[:3])
        total = table72[3][index]
        check_row(rows, check_id=f"ACFS2020_P72_subgroup_{field}", source=source,
                  locator="PDF p74 / printed p72", identity=f"printed total {field} = subgroup sum",
                  left=total, right=subgroup_sum, printed_values="certified + non-certified + imported",
                  interpretation="Printed total is checked against the three printed subgroup cells.")

    table73 = [
        ("vegetables", 101, 79, 9, 88, Decimal("87.13"), 13),
        ("fruits", 49, 36, 6, 42, Decimal("85.71"), 7),
        ("total", 150, 115, 15, 120, Decimal("86.67"), 20),
    ]
    for name, samples, nd, within, safe, safe_pct, unsafe in table73:
        printed = (
            f"samples={samples}; not_detected={nd}; within={within}; "
            f"safe={safe}; safe_pct={safe_pct}; unsafe={unsafe}"
        )
        check_row(rows, check_id=f"ACFS2020_P73_{name}_safe_components", source=source,
                  locator="PDF p75 / printed p73", identity="printed safe = not detected + within limit",
                  left=safe, right=nd + within, printed_values=printed,
                  interpretation="A contradiction identifies a printed-cell inconsistency; it is not silently corrected.")
        check_row(rows, check_id=f"ACFS2020_P73_{name}_partition", source=source,
                  locator="PDF p75 / printed p73", identity="samples = printed safe + unsafe",
                  left=samples, right=safe + unsafe, printed_values=printed,
                  interpretation="A contradiction identifies a printed-cell inconsistency; it is not silently corrected.")
        implied = (Decimal(samples) * safe_pct / Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        check_row(rows, check_id=f"ACFS2020_P73_{name}_percent_implied_safe", source=source,
                  locator="PDF p75 / printed p73", identity="printed safe = rounded(samples * printed safe percentage / 100)",
                  left=safe, right=implied, printed_values=printed,
                  interpretation="The printed percentage is converted back to an integer count using half-up rounding.")

    for index, field in [(1, "samples"), (2, "not_detected"), (3, "within"), (4, "safe"), (6, "unsafe")]:
        subgroup_sum = table73[0][index] + table73[1][index]
        total = table73[2][index]
        check_row(rows, check_id=f"ACFS2020_P73_subgroup_{field}", source=source,
                  locator="PDF p75 / printed p73", identity=f"printed total {field} = vegetable + fruit",
                  left=total, right=subgroup_sum, printed_values="vegetables + fruits",
                  interpretation="Printed total is checked against both printed subgroup cells.")

    # Negative controls: visibly transcribed, finite additive identities only.
    controls = [
        ("ACFS2024_P57_vegetables", "Thailand ACFS Annual Report 2024", "PDF/printed p57", 102, 28, 74,
         "samples = pass + not pass", "vegetables: samples=102; pass=28; not_pass=74"),
        ("ACFS2024_P57_fruits", "Thailand ACFS Annual Report 2024", "PDF/printed p57", 48, 26, 22,
         "samples = pass + not pass", "fruits: samples=48; pass=26; not_pass=22"),
        ("ACFS2024_P57_total", "Thailand ACFS Annual Report 2024", "PDF/printed p57", 150, 54, 96,
         "samples = pass + not pass", "total: samples=150; pass=54; not_pass=96"),
        ("ACFS2025_P85_vegetables", "Thailand ACFS Annual Report 2025", "PDF p85 / printed p73", 98, 47, 51,
         "samples = pass + not pass", "vegetables: samples=98; pass=47; not_pass=51"),
        ("ACFS2025_P85_fruits", "Thailand ACFS Annual Report 2025", "PDF p85 / printed p73", 53, 30, 23,
         "samples = pass + not pass", "fruits: samples=53; pass=30; not_pass=23"),
        ("ACFS2025_P85_total", "Thailand ACFS Annual Report 2025", "PDF p85 / printed p73", 151, 77, 74,
         "samples = pass + not pass", "total: samples=151; pass=77; not_pass=74"),
        ("THFDA2024_P1_imported", "Thailand FDA imported surveillance FY2024", "PDF p1", 506, 329, 177,
         "samples = compliant + non-compliant", "samples=506; compliant=329; non_compliant=177"),
    ]
    for check_id, control_source, locator, samples, left_part, right_part, identity, printed in controls:
        check_row(rows, check_id=check_id, source=control_source, locator=locator, identity=identity,
                  left=samples, right=left_part + right_part, printed_values=printed,
                  interpretation="Visually transcribed negative-control identity; no exposure meaning is assigned.")

    # The 2024/2025 reason subpartitions are independently additive.
    check_row(rows, check_id="ACFS2024_P57_default_limit_subgroup", source="Thailand ACFS Annual Report 2024",
              locator="PDF/printed p57", identity="total default-limit cases = vegetable + fruit cases",
              left=54, right=44 + 10, printed_values="total=54; vegetables=44; fruits=10",
              interpretation="Consistent subpartition; default-limit non-compliance is not equated with health risk.")
    check_row(rows, check_id="ACFS2025_P85_MRL_subgroup", source="Thailand ACFS Annual Report 2025",
              locator="PDF p85 / printed p73", identity="total MRL non-pass = vegetable + fruit cases",
              left=26, right=14 + 12, printed_values="total=26; vegetables=14; fruits=12",
              interpretation="Consistent subpartition; compliance is not exposure.")
    check_row(rows, check_id="ACFS2025_P85_default_subgroup", source="Thailand ACFS Annual Report 2025",
              locator="PDF p85 / printed p73", identity="total default-limit non-pass = vegetable + fruit cases",
              left=48, right=37 + 11, printed_values="total=48; vegetables=37; fruits=11",
              interpretation="Consistent subpartition; default-limit non-compliance is not equated with health risk.")
    return rows


def comparator_rows(inventory: list[dict]) -> list[dict]:
    by_family = {}
    for row in inventory:
        by_family.setdefault(row["source_family"], []).append(row)
    israel = by_family["Israel MoH 2012 risk report"][0]
    belgium = by_family["Belgium FASFC 2008 exposure report"][0]
    return [
        {
            "source": "Israel Ministry of Health 2012 risk analysis",
            "period": "2006-2010 monitoring; published 2012",
            "official_report_identity": f"{israel['sha256']} ({israel['bytes']} bytes; {israel['pages']} pages)",
            "occurrence_granularity": "commodity-pesticide report aggregates and appendices; no reusable sample ID",
            "censoring_or_substitution": "report-internal conservative/mean/lenient rules, including LOQ or zero for non-detects",
            "dietary_linkage": "historical marketed-diet table internal to report",
            "current_parent_reuse": "NO",
            "evidence_level": "LEVEL_C",
            "reason": "Historical report-only data, no row-level linkage or current compatible residue-definition/consumption bridge; custom-font extraction is not a validated parser.",
            "permitted_role": "historical official methodological comparator",
        },
        {
            "source": "Belgium FASFC advice 02-2010 using 2008 monitoring",
            "period": "2008 monitoring and Belgian 2006 consumption survey; published 2010",
            "official_report_identity": f"{belgium['sha256']} ({belgium['bytes']} bytes; {belgium['pages']} pages)",
            "occurrence_granularity": "report aggregates for 1,413 samples and selected pesticide-food combinations; no public row data in acquired artifact",
            "censoring_or_substitution": "report-internal lower/upper handling including LOQ/2 scenario",
            "dietary_linkage": "Belgian survey linkage internal to report; underlying microdata not acquired here",
            "current_parent_reuse": "NO",
            "evidence_level": "LEVEL_C",
            "reason": "Report is branch-isolated and does not expose independently reusable occurrence/consumption rows; period and dietary frame are historical.",
            "permitted_role": "citation-level official methodological comparator; no parent data admission",
        },
    ]


def make_figure(matrix: list[dict], checks: list[dict]) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    import numpy as np

    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 8,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })
    status_order = [
        "NO",
        "SCHEMA_ONLY",
        "PARTIAL_AGGREGATE",
        "YES_AGGREGATE_ONLY",
        "REPORT_INTERNAL_ONLY",
        "YES_ROW_LEVEL",
    ]
    colors = ["#E7EAED", "#D7C9E8", "#E8B46A", "#77A9D1", "#62B7A5", "#2E6F57"]
    labels = {
        "NO": "No",
        "SCHEMA_ONLY": "Schema only",
        "PARTIAL_AGGREGATE": "Partial aggregate",
        "YES_AGGREGATE_ONLY": "Aggregate only",
        "REPORT_INTERNAL_ONLY": "Report-internal only",
        "YES_ROW_LEVEL": "Row level",
    }
    short_fields = ["ID", "Commodity", "Analyte", "Conc.", "ND", "LOD/LOQ", "Residue\ndef.", "Year", "Food\nform", "Market", "Organic\nstatus", "Diet link"]
    short_sources = [
        "Thai FDA",
        "Thai ACFS",
        "THRASFF alerts",
        "THRASFF guide",
        "Israel audit",
        "Israel risk 2012",
        "Belgium 2008",
    ]
    values = [[status_order.index(row[field]) for field in FIELDS] for row in matrix]

    fig = plt.figure(figsize=(11.5, 6.6), constrained_layout=True)
    grid = fig.add_gridspec(2, 1, height_ratios=[1.45, 1.0])
    ax1 = fig.add_subplot(grid[0])
    values_array = np.asarray(values)
    ax1.pcolormesh(
        np.arange(values_array.shape[1] + 1) - 0.5,
        np.arange(values_array.shape[0] + 1) - 0.5,
        values_array,
        cmap=ListedColormap(colors),
        vmin=-0.5,
        vmax=len(colors) - 0.5,
        shading="flat",
        rasterized=False,
    )
    ax1.set_xlim(-0.5, values_array.shape[1] - 0.5)
    ax1.set_ylim(values_array.shape[0] - 0.5, -0.5)
    ax1.set_xticks(range(len(FIELDS)), labels=short_fields)
    ax1.set_yticks(range(len(matrix)), labels=short_sources)
    ax1.tick_params(axis="x", rotation=0, length=0)
    ax1.tick_params(axis="y", length=0)
    for x in range(len(FIELDS) + 1):
        ax1.axvline(x - 0.5, color="white", linewidth=1)
    for y in range(len(matrix) + 1):
        ax1.axhline(y - 0.5, color="white", linewidth=1)
    ax1.set_title("A  Publicly exposed fields are mostly aggregate or report-internal", loc="left", weight="bold", fontsize=10)
    legend = [Patch(facecolor=colors[i], edgecolor="none", label=labels[state]) for i, state in enumerate(status_order)]
    ax1.legend(handles=legend, ncol=6, loc="upper center", bbox_to_anchor=(0.5, -0.18), frameon=False, fontsize=7)

    ax2 = fig.add_subplot(grid[1])
    categories = ["p72 total", "p73 vegetables", "p73 fruits", "p73 total"]
    printed = [85, 88, 42, 120]
    reconstructed = [85, 88, 42, 130]
    x = list(range(len(categories)))
    width = 0.35
    bars1 = ax2.bar([v - width / 2 for v in x], printed, width, label="Printed safe count", color="#4E79A7")
    bars2 = ax2.bar([v + width / 2 for v in x], reconstructed, width, label="ND + within-limit", color="#59A14F")
    bars1[-1].set_color("#D55E00")
    for bars in (bars1, bars2):
        for bar in bars:
            ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2, f"{int(bar.get_height())}",
                     ha="center", va="bottom", fontsize=8)
    ax2.plot([x[-1] - width / 2, x[-1] + width / 2], [136, 136], color="#333333", linewidth=0.8)
    ax2.text(x[-1], 138, "10-count contradiction", ha="center", va="bottom", fontsize=8, color="#8B2500")
    ax2.set_xticks(x, categories)
    ax2.set_ylabel("Samples")
    ax2.set_ylim(0, 150)
    ax2.grid(axis="y", color="#D9D9D9", linewidth=0.6)
    ax2.set_axisbelow(True)
    ax2.set_title("B  One ACFS FY2020 printed total conflicts with four independent identities", loc="left", weight="bold", fontsize=10)
    ax2.legend(frameon=False, loc="upper left", ncol=2)
    ax2.text(0.0, -0.34,
             "The printed p73 total is preserved as 120. Components (115 + 15), subgroups (88 + 42), 86.67% of 150, and 150 minus 20 unsafe all imply 130.",
             transform=ax2.transAxes, fontsize=7.5)

    for suffix, kwargs in [("svg", {}), ("pdf", {}), ("png", {"dpi": 300})]:
        fig.savefig(OUT / f"external_source_challenge.{suffix}", bbox_inches="tight", **kwargs)
    plt.close(fig)
    svg_text = (OUT / "external_source_challenge.svg").read_text()
    assert "<text" in svg_text and "<image" not in svg_text


def output_manifest() -> dict:
    files = []
    for path in sorted(OUT.iterdir()):
        if path.name == "output_manifest.json" or path.name.startswith("._") or not path.is_file():
            continue
        files.append({"filename": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)})
    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "files": files,
        "file_count_excluding_manifest": len(files),
    }
    write_json(OUT / "output_manifest.json", payload)
    return payload


def run() -> None:
    paths_log = check_paths()
    assert not OUT.exists(), f"Refuse to replace existing output directory: {OUT}"
    OUT.mkdir(parents=True)
    (OUT / "path_check.txt").write_text(paths_log)

    inventory = verify_sources()
    matrix, matrix_notes = field_matrix()
    checks = arithmetic_checks()
    comparators = comparator_rows(inventory)

    write_csv(OUT / "verified_source_inventory.csv", inventory)
    write_csv(OUT / "source_field_availability_matrix.csv", matrix)
    write_json(OUT / "source_field_state_definitions.json", matrix_notes)
    write_csv(OUT / "official_table_arithmetic_checks.csv", checks)
    write_csv(OUT / "historical_exposure_report_feasibility.csv", comparators)

    acfs_2020 = [row for row in checks if row["check_id"].startswith("ACFS2020")]
    contradictions = [row for row in acfs_2020 if row["status"] == "CONTRADICTION"]
    contradiction_ids = [row["check_id"] for row in contradictions]
    assert contradiction_ids == [
        "ACFS2020_P73_total_safe_components",
        "ACFS2020_P73_total_partition",
        "ACFS2020_P73_total_percent_implied_safe",
        "ACFS2020_P73_subgroup_safe",
    ], contradiction_ids
    assert all(row["status"] == "PASS" for row in checks if not row["check_id"].startswith("ACFS2020_P73_total") and row["check_id"] != "ACFS2020_P73_subgroup_safe")
    assert all(row["evidence_level"] not in {"LEVEL_A", "LEVEL_B"} for row in matrix)

    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_path": str(PROTOCOL),
        "protocol_sha256": sha256(PROTOCOL),
        "script_path": str(Path(__file__)),
        "script_sha256": sha256(Path(__file__)),
        "raw_files_verified": len(inventory),
        "source_families_classified": len(matrix),
        "source_levels": {level: sum(row["evidence_level"] == level for row in matrix) for level in ["LEVEL_A", "LEVEL_B", "LEVEL_C", "LEVEL_D"]},
        "new_level_A_or_B_sources": 0,
        "new_exposure_units": 0,
        "exposure_calculations": 0,
        "acfs_2020_checks": len(acfs_2020),
        "acfs_2020_contradictory_identities": len(contradictions),
        "acfs_2020_underlying_issue": "One printed total safe-count cell is inconsistent with four redundant identities.",
        "acfs_2020_printed_total_safe": 120,
        "acfs_2020_reconstructed_total_safe": 130,
        "acfs_2020_printed_safe_percent": 86.67,
        "acfs_2020_printed_safe_percent_implied_count": 130,
        "interpretive_boundary": [
            "The official value 120 is preserved and labelled contradictory; 130 is an independent reconstruction, not an official correction.",
            "GAP/Q-mark is not organic status.",
            "Compliance and alert counts are not concentration or exposure.",
            "Historical Israel/Belgium reports are methodological comparators, not new parent-analysis units.",
            "The frozen 19-unit empirical exposure subset is unchanged.",
        ],
        "decision": "NO_ADDITIONAL_PUBLICLY_REUSABLE_LEVEL_A_OR_B_SOURCE_IDENTIFIED",
    }
    write_json(OUT / "summary.json", summary)
    make_figure(matrix, checks)
    output_manifest()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def verify() -> None:
    assert OUT.is_dir(), OUT
    manifest = json.loads((OUT / "output_manifest.json").read_text())
    for item in manifest["files"]:
        path = OUT / item["filename"]
        assert path.stat().st_size == item["bytes"], path
        assert sha256(path) == item["sha256"], path
    summary = json.loads((OUT / "summary.json").read_text())
    assert summary["raw_files_verified"] == 19
    assert summary["new_level_A_or_B_sources"] == 0
    assert summary["new_exposure_units"] == 0
    assert summary["acfs_2020_printed_total_safe"] == 120
    assert summary["acfs_2020_reconstructed_total_safe"] == 130
    print(f"PASS: {manifest['file_count_excluding_manifest']} output files verified")


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    run() if args.run else verify()


if __name__ == "__main__":
    main()
