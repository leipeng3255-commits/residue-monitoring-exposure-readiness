"""Build the revision-37 external-source challenge figure.

This is a reporting-structure and reproducibility figure, not an exposure
analysis.  It consumes only already-derived, provenance-verified audit tables.
Counts with different observational units are never converted into rates.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_config() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (ROOT / "00_admin/paths.yaml").read_text(encoding="utf-8").splitlines():
        match = re.match(r'^([a-z_]+):\s*"(.*)"\s*$', line)
        if match:
            values[match.group(1)] = match.group(2)
    assert Path(values["project_root"]).resolve() == ROOT
    return values


CFG = load_config()
OUT = Path(CFG["outputs_root"]) / "manuscript_grilling_v37/external_source_challenge"
V36 = Path(CFG["outputs_root"]) / "manuscript_grilling_v36/external_source_challenge"
ISR = Path(CFG["outputs_root"]) / "manuscript_grilling_v37/israel_agriculture_source_audit"
WCA = Path(CFG["outputs_root"]) / "manuscript_grilling_v37/who_california_source_admission"

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

INPUTS = {
    "v36_field_matrix": V36 / "source_field_availability_matrix.csv",
    "v36_arithmetic": V36 / "official_table_arithmetic_checks.csv",
    "israel_field_matrix": ISR / "field_availability.csv",
    "israel_schema": ISR / "annual_schema_and_counts.csv",
    "israel_report_arithmetic": ISR / "report_level_arithmetic.csv",
    "israel_tomato_checks": ISR / "tomato_mean_bound_checks.csv",
    "israel_tomato_summary": ISR / "tomato_reporting_summary.csv",
    "who_completeness": WCA / "who_figure_ready_completeness.csv",
    "who_california_receipt": WCA / "source_admission_receipt.json",
    "california_annual": WCA / "california_figure_ready_annual_structure.csv",
    "california_report_checks": WCA / "california_report_and_sample_type_checks.csv",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    assert rows or fields
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def path_check() -> str:
    result = subprocess.run(
        [sys.executable, str(ROOT / "05_code/utilities/check_paths.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0 and "PASS overall" in result.stdout, result.stdout + result.stderr
    return result.stdout


def normalise_v36_state(value: str) -> str:
    mapping = {
        "NO": "NO",
        "SCHEMA_ONLY": "SCHEMA_ONLY",
        "PARTIAL_AGGREGATE": "PARTIAL_AGGREGATE",
        "YES_AGGREGATE_ONLY": "AGGREGATE_ONLY",
        "REPORT_INTERNAL_ONLY": "REPORT_INTERNAL_ONLY",
        "YES_ROW_LEVEL": "ROW_LEVEL",
    }
    return mapping[value]


def build_field_matrix() -> list[dict]:
    base = read_csv(INPUTS["v36_field_matrix"])
    rows: list[dict] = []
    for row in base:
        rows.append({
            "source_family": row["source_family"],
            "evidence_level": row["evidence_level"].removeprefix("LEVEL_"),
            **{field: normalise_v36_state(row[field]) for field in FIELDS},
        })

    # The annual Israel audit is homogeneous across the seven reports for the
    # fields displayed here; its public unit is a crop x active-substance cell.
    rows.append({
        "source_family": "Israel Agriculture 2019-2025",
        "evidence_level": "C",
        "sample_id": "NO",
        "commodity": "AGGREGATE_ONLY",
        "pesticide_analyte": "AGGREGATE_ONLY",
        "quantitative_concentration": "AGGREGATE_ONLY",
        "non_detect_information": "PARTIAL_AGGREGATE",
        "lod_loq": "PARTIAL_AGGREGATE",
        "risk_assessment_residue_definition": "NO",
        "sampling_year": "AGGREGATE_ONLY",
        "food_form": "AGGREGATE_ONLY",
        "country_market_frame": "AGGREGATE_ONLY",
        "organic_conventional_status": "NO",
        "compatible_dietary_linkage": "NO",
    })
    rows.append({
        "source_family": "WHO GEMS/Food public exports",
        "evidence_level": "C",
        "sample_id": "ROW_LEVEL",
        "commodity": "ROW_LEVEL",
        "pesticide_analyte": "ROW_LEVEL",
        "quantitative_concentration": "ROW_LEVEL",
        "non_detect_information": "ROW_LEVEL",
        "lod_loq": "ROW_LEVEL",
        "risk_assessment_residue_definition": "NO",
        "sampling_year": "ROW_LEVEL",
        "food_form": "ROW_LEVEL",
        "country_market_frame": "PARTIAL_AGGREGATE",
        "organic_conventional_status": "NO",
        "compatible_dietary_linkage": "NO",
    })
    rows.append({
        "source_family": "California DPR 2020-2023",
        "evidence_level": "C",
        "sample_id": "ROW_LEVEL",
        "commodity": "ROW_LEVEL",
        "pesticide_analyte": "PARTIAL_ROW_LEVEL",
        "quantitative_concentration": "PARTIAL_ROW_LEVEL",
        "non_detect_information": "PARTIAL_ROW_LEVEL",
        "lod_loq": "PARTIAL_ROW_LEVEL",
        "risk_assessment_residue_definition": "NO",
        "sampling_year": "ROW_LEVEL",
        "food_form": "NO",
        "country_market_frame": "PARTIAL_ROW_LEVEL",
        "organic_conventional_status": "ROW_LEVEL",
        "compatible_dietary_linkage": "NO",
    })
    assert len(rows) == 10
    assert Counter(row["evidence_level"] for row in rows) == Counter({"C": 5, "D": 5})
    return rows


def first_metric(rows: list[dict[str, str]], group: str, metric: str) -> dict[str, str]:
    hits = [row for row in rows if row["metric_group"] == group and row["metric"] == metric]
    assert len(hits) == 1, (group, metric, len(hits))
    return hits[0]


def build_structure_scale() -> list[dict]:
    who = read_csv(INPUTS["who_completeness"])
    ca = read_csv(INPUTS["california_annual"])
    israel = read_csv(INPUTS["israel_tomato_summary"])
    rows: list[dict] = []
    for metric in ["Individual", "Aggregated", "Blank"]:
        item = first_metric(who, "record_type", metric)
        rows.append({
            "source": "WHO GEMS/Food",
            "structure": f"{metric} record type",
            "count": int(item["numerator"]),
            "unit": "analytical rows",
            "denominator": item["denominator_definition"],
        })
    rows.extend([
        {
            "source": "California DPR",
            "structure": "Unique laboratory IDs",
            "count": sum(int(row["unique_sample_ids"]) for row in ca),
            "unit": "annual laboratory IDs (year-specific sum)",
            "denominator": "four annual workbooks; IDs are not de-duplicated across years",
        },
        {
            "source": "California DPR",
            "structure": "Detected-analyte rows",
            "count": sum(int(row["detected_analyte_rows"]) for row in ca),
            "unit": "detected-analyte rows",
            "denominator": "four annual workbooks",
        },
        {
            "source": "California DPR",
            "structure": "Generic ND placeholders",
            "count": sum(int(row["generic_nd_placeholder_rows"]) for row in ca),
            "unit": "generic placeholder rows",
            "denominator": "four annual workbooks; not analyte-specific negatives",
        },
        {
            "source": "Israel Agriculture",
            "structure": "Annual reports",
            "count": len(israel),
            "unit": "official annual PDF reports",
            "denominator": "2019-2025 report series",
        },
        {
            "source": "Israel Agriculture",
            "structure": "Tomato crop x active-substance rows",
            "count": sum(int(row["reported_crop_analyte_rows"]) for row in israel),
            "unit": "published tomato table rows",
            "denominator": "seven report-specific tomato tables; not sample-level rows",
        },
    ])
    assert sum(row["count"] for row in rows if row["source"] == "WHO GEMS/Food") == 8_168_962
    return rows


def build_california_rows() -> list[dict]:
    source = read_csv(INPUTS["california_annual"])
    rows = []
    for row in source:
        rows.append({
            "year": int(row["year"]),
            "unique_lab_ids": int(row["unique_sample_ids"]),
            "detected_analyte_rows": int(row["detected_analyte_rows"]),
            "generic_nd_placeholder_rows": int(row["generic_nd_placeholder_rows"]),
            "sample_type_field": row["sample_type_field"],
            "analyte_specific_nd_denominator_reconstructable": row["analyte_specific_nd_denominator_reconstructable"],
        })
    assert [row["year"] for row in rows] == [2020, 2021, 2022, 2023]
    assert [row["sample_type_field"] for row in rows] == ["NO", "NO", "NO", "YES"]
    assert all(row["analyte_specific_nd_denominator_reconstructable"] == "NO" for row in rows)
    return rows


def build_arithmetic_rows() -> list[dict]:
    v36 = read_csv(INPUTS["v36_arithmetic"])
    tomato = read_csv(INPUTS["israel_tomato_checks"])
    annual = read_csv(INPUTS["israel_report_arithmetic"])
    contradiction = [row for row in v36 if row["check_id"] == "ACFS2020_P73_total_safe_components"]
    assert len(contradiction) == 1
    acfs = contradiction[0]
    tomato_counts = Counter(row["status"] for row in tomato)
    annual_counts = Counter(row["status"] for row in annual)
    assert tomato_counts == Counter({
        "CONSISTENT_WITHIN_PRECISION_ALLOWANCE": 147,
        "INTERNALLY_INCONSISTENT_AFTER_PRECISION_ALLOWANCE": 7,
        "INCOMPLETE_FOR_CHECK": 4,
    })
    assert annual_counts == Counter({"PASS": 23, "PRINTED_INTERNAL_INCONSISTENCY": 2})
    return [
        {
            "audit": "ACFS FY2020 printed safe count",
            "category": "Printed",
            "count": int(acfs["left_value"]),
            "denominator": "printed safe-count cell",
        },
        {
            "audit": "ACFS FY2020 printed safe count",
            "category": "Arithmetic reconstruction",
            "count": int(acfs["right_value"]),
            "denominator": "four redundant cross-checks imply the same count",
        },
        {
            "audit": "Israel tomato mean-bound rows",
            "category": "Feasible",
            "count": tomato_counts["CONSISTENT_WITHIN_PRECISION_ALLOWANCE"],
            "denominator": "158 crop x active-substance rows, 2021-2025",
        },
        {
            "audit": "Israel tomato mean-bound rows",
            "category": "Inconsistent",
            "count": tomato_counts["INTERNALLY_INCONSISTENT_AFTER_PRECISION_ALLOWANCE"],
            "denominator": "158 crop x active-substance rows, 2021-2025",
        },
        {
            "audit": "Israel tomato mean-bound rows",
            "category": "Incomplete",
            "count": tomato_counts["INCOMPLETE_FOR_CHECK"],
            "denominator": "158 crop x active-substance rows, 2021-2025",
        },
        {
            "audit": "Israel annual identities",
            "category": "Reproduced",
            "count": annual_counts["PASS"],
            "denominator": "25 printed annual identities, 2019-2025",
        },
        {
            "audit": "Israel annual identities",
            "category": "Inconsistent",
            "count": annual_counts["PRINTED_INTERNAL_INCONSISTENCY"],
            "denominator": "25 printed annual identities, 2019-2025",
        },
    ]


def save_input_receipts(field_rows: list[dict], structure_rows: list[dict], california_rows: list[dict], arithmetic_rows: list[dict]) -> None:
    write_csv(OUT / "figure_field_availability.csv", field_rows)
    write_csv(OUT / "panel_b_structure_scale.csv", structure_rows)
    write_csv(OUT / "panel_c_california_annual_structure.csv", california_rows)
    write_csv(OUT / "panel_d_arithmetic_reproducibility.csv", arithmetic_rows)
    receipts = []
    for role, path in INPUTS.items():
        assert path.is_file(), path
        receipts.append({
            "role": role,
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    write_csv(OUT / "source_input_receipts.csv", receipts)


def make_figure(field_rows: list[dict], structure_rows: list[dict], california_rows: list[dict], arithmetic_rows: list[dict]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    from matplotlib.ticker import FuncFormatter, LogLocator
    from PIL import Image

    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 8.2,
        "axes.titlesize": 10.2,
        "axes.titleweight": "bold",
        "axes.labelsize": 8.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.7,
        "xtick.major.width": 0.7,
        "ytick.major.width": 0.7,
        "svg.fonttype": "none",
        "svg.hashsalt": "external-source-challenge-v37",
        "pdf.fonttype": 42,
        "savefig.facecolor": "white",
    })

    fig = plt.figure(figsize=(15.6, 12.4), constrained_layout=True)
    gs = fig.add_gridspec(3, 2, height_ratios=[1.45, 1.0, 1.0], width_ratios=[1.03, 0.97])

    # Panel A — categorical field availability, not a readiness score.
    ax = fig.add_subplot(gs[0, :])
    states = ["NO", "SCHEMA_ONLY", "PARTIAL_AGGREGATE", "AGGREGATE_ONLY", "REPORT_INTERNAL_ONLY", "PARTIAL_ROW_LEVEL", "ROW_LEVEL"]
    state_labels = {
        "NO": "Not exposed",
        "SCHEMA_ONLY": "Schema only",
        "PARTIAL_AGGREGATE": "Partial aggregate",
        "AGGREGATE_ONLY": "Aggregate only",
        "REPORT_INTERNAL_ONLY": "Report-internal",
        "PARTIAL_ROW_LEVEL": "Partial row level",
        "ROW_LEVEL": "Row level",
    }
    colors = ["#E8EBED", "#BFB4D8", "#E4BA67", "#76A7C8", "#8BC7BB", "#E18A72", "#2F7864"]
    matrix = np.asarray([[states.index(row[field]) for field in FIELDS] for row in field_rows])
    ax.pcolormesh(
        np.arange(matrix.shape[1] + 1) - 0.5,
        np.arange(matrix.shape[0] + 1) - 0.5,
        matrix,
        cmap=ListedColormap(colors),
        vmin=-0.5,
        vmax=len(states) - 0.5,
        shading="flat",
        rasterized=False,
    )
    source_short = [
        "Thai FDA [D]", "Thai ACFS [D]", "THRASFF alerts [D]", "THRASFF guide [D]",
        "Israel audit [D]", "Israel MoH 2012 [C]", "Belgium 2008 [C]",
        "Israel Agriculture 2019-25 [C]", "WHO GEMS/Food [C]", "California DPR 2020-23 [C]",
    ]
    field_short = ["Sample\nID", "Commodity", "Analyte", "Concen-\ntration", "ND", "LOD/\nLOQ", "Risk\nresidue def.", "Year", "Food\nform", "Market/\norigin", "Organic\nstatus", "Dietary\nlinkage"]
    ax.set_xticks(range(len(FIELDS)), labels=field_short)
    ax.set_yticks(range(len(field_rows)), labels=source_short)
    ax.tick_params(length=0, labelsize=7.7)
    ax.set_xlim(-0.5, matrix.shape[1] - 0.5)
    ax.set_ylim(matrix.shape[0] - 0.5, -0.5)
    for x in range(matrix.shape[1] + 1):
        ax.axvline(x - 0.5, color="white", linewidth=1)
    for y in range(matrix.shape[0] + 1):
        ax.axhline(y - 0.5, color="white", linewidth=1)
    ax.set_title("A  Field availability differs sharply across ten official-source families", loc="left")
    legend = [Patch(facecolor=colors[i], edgecolor="none", label=state_labels[state]) for i, state in enumerate(states)]
    ax.legend(handles=legend, ncol=7, loc="upper center", bbox_to_anchor=(0.5, -0.13), frameon=False, fontsize=7.1, handlelength=1.4)
    ax.text(1.0, 1.015, "[C]/[D] = source-and-estimand evidence level; colours are categories, not scores",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=7.2, color="#4A4A4A")

    # Panel B — log-scale counts with observation units named explicitly.
    ax = fig.add_subplot(gs[1, 0])
    palette = {"WHO GEMS/Food": "#2F7864", "California DPR": "#33658A", "Israel Agriculture": "#B56534"}
    structure_order = [
        "Individual record type", "Aggregated record type", "Blank record type",
        "Unique laboratory IDs", "Detected-analyte rows", "Generic ND placeholders",
        "Annual reports", "Tomato crop x active-substance rows",
    ]
    rows_by_structure = {row["structure"]: row for row in structure_rows}
    y = np.arange(len(structure_order))[::-1]
    for yy, label in zip(y, structure_order):
        row = rows_by_structure[label]
        value = int(row["count"])
        ax.scatter(value, yy, s=54, color=palette[row["source"]], edgecolor="white", linewidth=0.7, zorder=3)
        ax.hlines(yy, 1, value, color=palette[row["source"]], linewidth=1.15, alpha=0.55)
        ax.text(value * 1.12, yy, f"{value:,}", va="center", fontsize=7.4, color="#222222")
    ax.set_xscale("log")
    ax.set_xlim(1, 2.2e7)
    ax.set_yticks(y, labels=structure_order)
    ax.tick_params(axis="y", length=0, labelsize=7.6)
    ax.xaxis.set_major_locator(LogLocator(base=10, numticks=8))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"$10^{{{int(np.log10(x))}}}$" if x > 0 else ""))
    ax.grid(axis="x", color="#D8DDE1", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.set_xlabel("Count on logarithmic scale")
    ax.set_title("B  Public scale does not resolve the observational unit", loc="left")
    ax.legend(handles=[Patch(facecolor=color, label=label) for label, color in palette.items()],
              frameon=False, loc="lower right", fontsize=7.2)
    ax.text(0.0, -0.24,
            "Denominators are intentionally incomparable: WHO analytical rows; California annual laboratory IDs or result rows; Israel reports or published tomato table rows.",
            transform=ax.transAxes, fontsize=7.1, color="#4A4A4A", wrap=True)

    # Panel C — California structure by year, without calling rows prevalence.
    ax = fig.add_subplot(gs[1, 1])
    years = [row["year"] for row in california_rows]
    x = np.arange(len(years))
    width = 0.24
    series = [
        ("unique_lab_ids", "Unique laboratory IDs", "#7B8B8E"),
        ("detected_analyte_rows", "Detected-analyte rows", "#33658A"),
        ("generic_nd_placeholder_rows", "Generic ND placeholder rows", "#D69A3A"),
    ]
    for offset, (key, label, color) in zip([-width, 0, width], series):
        vals = [row[key] for row in california_rows]
        bars = ax.bar(x + offset, vals, width=width * 0.9, label=label, color=color)
        for bar, value in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width()/2, value + 145, f"{value:,}", ha="center", va="bottom", fontsize=6.3, rotation=90)
    ax.set_xticks(x, labels=[str(year) for year in years])
    ax.set_ylim(0, 8400)
    ax.set_ylabel("Source-specific count")
    ax.grid(axis="y", color="#D8DDE1", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.set_title("C  California workbooks expose positives but not analyte-specific negative denominators", loc="left")
    ax.legend(frameon=False, loc="upper left", ncol=1, fontsize=7.0)
    for i, row in enumerate(california_rows):
        label = "Sample-type field" if row["sample_type_field"] == "YES" else "No sample-type field"
        color = "#2F7864" if row["sample_type_field"] == "YES" else "#8B8B8B"
        ax.scatter(i, 7900, marker="D" if row["sample_type_field"] == "YES" else "x", s=28, color=color, zorder=5)
        if i == 3:
            ax.text(i, 8075, label, ha="center", va="bottom", fontsize=6.6, color=color)
    ax.text(0.0, -0.24,
            "Grouped bars are structure counts, not detection prevalence. Generic placeholders cannot be expanded into analyte-specific non-detects; risk-directed sampling is not population-representative.",
            transform=ax.transAxes, fontsize=7.1, color="#4A4A4A", wrap=True)

    # Panel D — different identity families shown separately and exactly.
    # The panel letter is attached to the first axis so no decorative/empty
    # title axis competes with the three quantitative displays.
    sub = gs[2, :].subgridspec(1, 3, width_ratios=[0.68, 1.2, 1.05], wspace=0.30)
    left = fig.add_subplot(sub[0, 0])
    acfs = [row for row in arithmetic_rows if row["audit"].startswith("ACFS")]
    bars = left.bar([0, 1], [row["count"] for row in acfs], color=["#C85C3A", "#2F7864"], width=0.62)
    for bar, row in zip(bars, acfs):
        left.text(bar.get_x()+bar.get_width()/2, row["count"]+2, str(row["count"]), ha="center", va="bottom", fontsize=9, weight="bold")
    left.set_xticks([0, 1], labels=["Printed\ncell", "Arithmetic\nreconstruction"])
    left.set_ylim(0, 145)
    left.set_ylabel("Safe-count value")
    left.grid(axis="y", color="#D8DDE1", linewidth=0.7)
    left.set_axisbelow(True)
    left.set_title("D  ACFS FY2020 safe-count cell", loc="left", fontsize=9.1)
    left.text(0.5, 137, "difference = 10", ha="center", va="center", fontsize=7.2, color="#7E2F1B")

    middle = fig.add_subplot(sub[0, 1])
    tomato = [row for row in arithmetic_rows if row["audit"] == "Israel tomato mean-bound rows"]
    tomato_colors = {"Feasible": "#2F7864", "Inconsistent": "#C85C3A", "Incomplete": "#B8BEC2"}
    start = 0
    total = sum(row["count"] for row in tomato)
    for row in tomato:
        value = row["count"]
        middle.barh([0], [value], left=[start], color=tomato_colors[row["category"]], height=0.46, label=row["category"])
        middle.text(start + value/2, 0, f"{value}", ha="center", va="center", fontsize=8,
                    color="white" if row["category"] != "Incomplete" else "#333333", weight="bold")
        start += value
    middle.set_xlim(0, total)
    middle.set_yticks([])
    middle.set_xlabel("Tomato crop x active-substance rows")
    middle.set_title("E  Israel precision-aware mean-bound check", loc="left", fontsize=9.1)
    middle.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.0), fontsize=7.0)
    middle.grid(axis="x", color="#D8DDE1", linewidth=0.7)
    middle.set_axisbelow(True)

    right = fig.add_subplot(sub[0, 2])
    annual = [row for row in arithmetic_rows if row["audit"] == "Israel annual identities"]
    annual_colors = {"Reproduced": "#2F7864", "Inconsistent": "#C85C3A"}
    start = 0
    total = sum(row["count"] for row in annual)
    for row in annual:
        value = row["count"]
        right.barh([0], [value], left=[start], color=annual_colors[row["category"]], height=0.46, label=row["category"])
        right.text(start + value/2, 0, f"{value}", ha="center", va="center", fontsize=8, color="white", weight="bold")
        start += value
    right.set_xlim(0, total)
    right.set_yticks([])
    right.set_xlabel("Printed annual identities")
    right.set_title("F  Israel report-level annual identities", loc="left", fontsize=9.1)
    right.legend(frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, 1.0), fontsize=7.0)
    right.grid(axis="x", color="#D8DDE1", linewidth=0.7)
    right.set_axisbelow(True)

    base = OUT / "external_source_challenge_v37"
    common_meta = {"Creator": "Deterministic Python/Matplotlib source-structure figure"}
    fig.savefig(base.with_suffix(".svg"), bbox_inches="tight", metadata={**common_meta, "Date": "2026-10-16"})
    fig.savefig(base.with_suffix(".pdf"), bbox_inches="tight", metadata=common_meta)
    fig.savefig(base.with_suffix(".png"), bbox_inches="tight", dpi=400, metadata={"Software": common_meta["Creator"]})
    plt.close(fig)

    png = Image.open(base.with_suffix(".png")).convert("RGB")
    png.save(base.with_suffix(".tiff"), compression="tiff_lzw", dpi=(400, 400))
    svg = base.with_suffix(".svg").read_text(encoding="utf-8")
    assert "<text" in svg and "<image" not in svg
    assert svg.count("<text") >= 80


def write_manifest() -> dict:
    files = []
    for path in sorted(OUT.iterdir()):
        if not path.is_file() or path.name.startswith("._") or path.name == "verification_manifest.json":
            continue
        files.append({"filename": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)})
    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS_REPRODUCIBLE_SIX_PANEL_SOURCE_CHALLENGE_NO_EXPOSURE",
        "panel_count": 6,
        "source_families": 10,
        "evidence_levels": {"A": 0, "B": 0, "C": 5, "D": 5},
        "new_exposure_units": 0,
        "exposure_calculations": 0,
        "organic_effect_estimates": 0,
        "interpretive_boundary": [
            "Monitoring rows, laboratory IDs, report tables and printed identities have explicitly different denominators.",
            "California bars describe public file structure, not detection prevalence.",
            "Arithmetic inconsistencies are reporting-reproducibility findings, not official corrections or laboratory-error claims.",
            "The frozen 19-unit parent exposure subset is unchanged.",
        ],
        "files": files,
    }
    write_json(OUT / "verification_manifest.json", payload)
    return payload


def run() -> None:
    log = path_check()
    assert not OUT.exists(), f"Refuse to replace existing output directory: {OUT}"
    OUT.mkdir(parents=True)
    (OUT / "path_check.txt").write_text(log, encoding="utf-8")
    field_rows = build_field_matrix()
    structure_rows = build_structure_scale()
    california_rows = build_california_rows()
    arithmetic_rows = build_arithmetic_rows()
    save_input_receipts(field_rows, structure_rows, california_rows, arithmetic_rows)
    make_figure(field_rows, structure_rows, california_rows, arithmetic_rows)
    payload = write_manifest()
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def refresh_receipts() -> None:
    """Refresh derived tables and input hashes without replacing artwork."""
    path_check()
    assert OUT.is_dir(), OUT
    field_rows = build_field_matrix()
    structure_rows = build_structure_scale()
    california_rows = build_california_rows()
    arithmetic_rows = build_arithmetic_rows()
    save_input_receipts(field_rows, structure_rows, california_rows, arithmetic_rows)
    payload = write_manifest()
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def rerender() -> None:
    """Regenerate only the dedicated derived figure directory in place."""
    path_check()
    assert OUT.is_dir(), OUT
    field_rows = build_field_matrix()
    structure_rows = build_structure_scale()
    california_rows = build_california_rows()
    arithmetic_rows = build_arithmetic_rows()
    save_input_receipts(field_rows, structure_rows, california_rows, arithmetic_rows)
    make_figure(field_rows, structure_rows, california_rows, arithmetic_rows)
    payload = write_manifest()
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def verify() -> None:
    manifest = json.loads((OUT / "verification_manifest.json").read_text(encoding="utf-8"))
    assert manifest["panel_count"] == 6
    assert manifest["source_families"] == 10
    assert manifest["new_exposure_units"] == 0
    for item in manifest["files"]:
        path = OUT / item["filename"]
        assert path.stat().st_size == item["bytes"], path
        assert sha256(path) == item["sha256"], path
    receipts = read_csv(OUT / "source_input_receipts.csv")
    for row in receipts:
        path = Path(row["path"])
        assert path.stat().st_size == int(row["bytes"]), path
        assert sha256(path) == row["sha256"], path
    svg = (OUT / "external_source_challenge_v37.svg").read_text(encoding="utf-8")
    assert "<text" in svg and "<image" not in svg
    print(f"PASS: {len(manifest['files'])} files and {len(receipts)} source inputs verified")


def main() -> None:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--run", action="store_true")
    modes.add_argument("--refresh-receipts", action="store_true")
    modes.add_argument("--rerender", action="store_true")
    modes.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.run:
        run()
    elif args.refresh_receipts:
        refresh_receipts()
    elif args.rerender:
        rerender()
    else:
        verify()


if __name__ == "__main__":
    main()
