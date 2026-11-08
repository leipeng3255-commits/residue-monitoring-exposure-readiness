#!/usr/bin/env python3
"""Bounded source-admission audit for WHO GEMS/Food and California DPR.

This script is deliberately non-analytical: it verifies immutable source
identity, describes public field semantics and writes admission summaries.  It
does not calculate dietary exposure and does not merge the branch-isolated
California data into the parent analysis.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from openpyxl import load_workbook
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
ADMIN = ROOT / "00_admin"
PATHS = {
    key: json.loads(value)
    for key, value in re.findall(
        r'^(\w+):\s*(".*")$',
        (ADMIN / "paths.yaml").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
}
RAW = Path(PATHS["raw_data_root"])
WHO_DIR = RAW / "who_gemsfood"
CA_DIR = (
    Path(PATHS["plant_trade_raw_root"])
    / "global_monitoring_expansion_20261016"
    / "CALIFORNIA_DPR"
)
OUT = (
    Path(PATHS["outputs_root"])
    / "manuscript_grilling_v37"
    / "who_california_source_admission"
)

WHO_COLUMNS = [
    "RecordType",
    "RegionCode",
    "RegionName",
    "ContaminantName",
    "FoodCategory",
    "FoodName",
    "FoodCode",
    "LocalFoodName",
    "FoodStateName",
    "ResultText",
    "UnitName",
    "LOD",
    "LOQ",
    "Year",
    "RepresentativenessName",
    "LabNumber",
    "FoodOriginName",
    "AnalyticalQAName",
    "ResultBasisName",
    "PortionTypeName",
    "SerialNumber",
]

# Files excluded from the four-overlap-controlled descriptive denominator. They are still
# identity-checked and structurally audited below.
WHO_REDUNDANT_EXPORTS = {
    "ccne_all_occurrence_records_20260924.csv": "region alias of EMRO",
    "eu_all_occurrence_records_20260924.csv": "regional subset/alias of EURO",
    "euro_2020_all_occurrence_records_20260924.csv": "year subset of EURO",
    "chlorpyrifos_all_regions_20260924.csv": "contaminant-filtered subset",
}

CA_XLSX = {
    2020: "resi2020.xlsx",
    2021: "residue_2021.xlsx",
    2022: "residue_2022.xlsx",
    2023: "annual_residue_data_2023.xlsx",
}
CA_REPORTS = {
    2022: "2022_residue_program_annual_report.pdf",
    2023: "2023_california_pesticide_residue_monitoring_program_report.pdf",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    if not rows and fields is None:
        raise ValueError(f"No rows or fields for {path}")
    if fields is None:
        fields = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def manifest_rows() -> dict[str, dict]:
    with (ADMIN / "download_manifest.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        return {
            row["local_file_path"]: row
            for row in csv.DictReader(handle)
            if row.get("local_file_path")
        }


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_present(value: object) -> bool:
    return clean(value) not in {"", "-", "NA", "N/A", "None", "NONE"}


def number_class(value: object) -> str:
    text = clean(value)
    if not text:
        return "BLANK"
    upper = text.upper()
    if upper in {"ND", "NON DETECTED", "NON-DETECTED", "NOT DETECTED"}:
        return "ND_TEXT"
    try:
        number = float(text)
    except ValueError:
        return "OTHER_TEXT"
    if math.isnan(number):
        return "BLANK"
    if number == 0:
        return "NUMERIC_ZERO"
    if number > 0:
        return "NUMERIC_POSITIVE"
    return "NUMERIC_NEGATIVE"


def positive_numeric(value: object) -> bool:
    try:
        number = float(clean(value))
    except ValueError:
        return False
    return math.isfinite(number) and number > 0


def is_vegetable(row: dict[str, str]) -> bool:
    # The official public food hierarchy supplies this category; no inferred
    # commodity crosswalk is used here.  Exact equality is required so that
    # categories such as vegetable fats or mixed fruit/vegetable juices are
    # not silently counted as the vegetable-food category.
    return clean(row.get("FoodCategory")) == "Vegetables and vegetable products (including fungi)"


def fingerprint(row: dict[str, str], *, ignore_region: bool) -> bytes:
    fields = [c for c in WHO_COLUMNS if not (ignore_region and c in {"RegionCode", "RegionName"})]
    material = "\x1f".join(clean(row.get(c)) for c in fields).encode("utf-8")
    return hashlib.blake2b(material, digest_size=16).digest()


def multiset_subset(
    subset_path: Path, target_paths: Iterable[Path], *, ignore_region: bool
) -> tuple[int, int, int]:
    wanted: Counter[bytes] = Counter()
    with subset_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == WHO_COLUMNS
        for row in reader:
            wanted[fingerprint(row, ignore_region=ignore_region)] += 1
    total = sum(wanted.values())
    unmatched = total
    for target_path in target_paths:
        with target_path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            assert reader.fieldnames == WHO_COLUMNS
            for row in reader:
                key = fingerprint(row, ignore_region=ignore_region)
                if wanted.get(key, 0):
                    wanted[key] -= 1
                    unmatched -= 1
                    if wanted[key] == 0:
                        del wanted[key]
        if not wanted:
            break
    return total, total - unmatched, unmatched


def audit_who() -> tuple[list[dict], list[dict], list[dict], dict]:
    files = sorted(p for p in WHO_DIR.glob("*.csv") if not p.name.startswith("._"))
    assert len(files) == 18, f"Expected 18 WHO CSV exports, found {len(files)}"
    file_rows: list[dict] = []
    global_counts: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    origins: Counter[str] = Counter()
    years: Counter[str] = Counter()

    for path in files:
        local = Counter()
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            assert reader.fieldnames == WHO_COLUMNS, (path.name, reader.fieldnames)
            for row in reader:
                local["rows"] += 1
                record_type = clean(row["RecordType"]) or "BLANK"
                local[f"record_type::{record_type}"] += 1
                vegetable = is_vegetable(row)
                if vegetable:
                    local["vegetable_rows"] += 1
                    local[f"vegetable_type::{record_type}"] += 1
                if path.name not in WHO_REDUNDANT_EXPORTS:
                    global_counts["rows_after_verified_redundancy_exclusions"] += 1
                    global_counts[f"record_type::{record_type}"] += 1
                    categories[clean(row["FoodCategory"]) or "BLANK"] += 1
                    origins[clean(row["FoodOriginName"]) or "BLANK"] += 1
                    years[clean(row["Year"]) or "BLANK"] += 1
                    if vegetable:
                        global_counts["vegetable_rows"] += 1
                        global_counts[f"vegetable_type::{record_type}"] += 1
                        if record_type == "Individual":
                            global_counts["individual_vegetable_rows"] += 1
                            result_class = number_class(row["ResultText"])
                            global_counts[f"result::{result_class}"] += 1
                            for field in ("ResultText", "LOD", "LOQ", "SerialNumber", "LabNumber"):
                                if is_present(row[field]):
                                    global_counts[f"present::{field}"] += 1
                            censored = result_class in {"ND_TEXT", "NUMERIC_ZERO"}
                            if censored:
                                global_counts["censored_nd_or_zero"] += 1
                                if is_present(row["LOD"]):
                                    global_counts["censored_with_lod"] += 1
                                if is_present(row["LOQ"]):
                                    global_counts["censored_with_loq"] += 1
        file_rows.append(
            {
                "file": path.name,
                "rows": local["rows"],
                "record_type_individual": local["record_type::Individual"],
                "record_type_aggregated": local["record_type::Aggregated"],
                "record_type_blank": local["record_type::BLANK"],
                "vegetable_rows": local["vegetable_rows"],
                "included_in_four_relation_denominator": "NO" if path.name in WHO_REDUNDANT_EXPORTS else "YES",
                "exclusion_reason": WHO_REDUNDANT_EXPORTS.get(path.name, ""),
            }
        )

    # Exact multiset relations. Region labels are ignored only for aliases.
    overlap_specs = [
        (
            "ccne_all_occurrence_records_20260924.csv",
            ["emro_all_occurrence_records_20260924.csv"],
            True,
            "CCNE non-region fields duplicate EMRO alias",
        ),
        (
            "eu_all_occurrence_records_20260924.csv",
            ["euro_all_occurrence_records_20260924.csv"],
            True,
            "EU non-region fields are a subset of EURO",
        ),
        (
            "euro_2020_all_occurrence_records_20260924.csv",
            ["euro_all_occurrence_records_20260924.csv"],
            False,
            "EURO 2020 is a year-filtered subset of EURO",
        ),
        (
            "chlorpyrifos_all_regions_20260924.csv",
            [
                "afro_all_occurrence_records_20260924.csv",
                "ccne_all_occurrence_records_20260924.csv",
                "emro_all_occurrence_records_20260924.csv",
                "eu_all_occurrence_records_20260924.csv",
                "euro_all_occurrence_records_20260924.csv",
                "searo_all_occurrence_records_20260924.csv",
                "wpro_all_occurrence_records_20260924.csv",
                *sorted(p.name for p in files if p.name.startswith("paho_")),
            ],
            False,
            "chlorpyrifos file is a contaminant-filtered subset of regional exports",
        ),
    ]
    overlaps = []
    for subset, targets, ignore_region, relation in overlap_specs:
        total, matched, unmatched = multiset_subset(
            WHO_DIR / subset,
            [WHO_DIR / name for name in targets],
            ignore_region=ignore_region,
        )
        overlaps.append(
            {
                "subset_file": subset,
                "target_files": ";".join(targets),
                "comparison": "non-region fields" if ignore_region else "all 21 fields",
                "relation": relation,
                "subset_rows": total,
                "matched_rows": matched,
                "unmatched_rows": unmatched,
                "verified_exact_multiset_subset": "YES" if unmatched == 0 else "NO",
            }
        )
        assert unmatched == 0, overlaps[-1]

    denominator = global_counts["rows_after_verified_redundancy_exclusions"]
    ind_veg = global_counts["individual_vegetable_rows"]
    censored = global_counts["censored_nd_or_zero"]
    metrics: list[dict] = []

    def metric(group: str, name: str, numerator: int, denom: int, definition: str) -> None:
        metrics.append(
            {
                "metric_group": group,
                "metric": name,
                "denominator_definition": definition,
                "numerator": numerator,
                "denominator": denom,
                "percent": "" if denom == 0 else f"{100 * numerator / denom:.6f}",
            }
        )

    metric("record_type", "Individual", global_counts["record_type::Individual"], denominator, "analytical rows after four verified redundant exports excluded")
    metric("record_type", "Aggregated", global_counts["record_type::Aggregated"], denominator, "analytical rows after four verified redundant exports excluded")
    metric("record_type", "Blank", global_counts["record_type::BLANK"], denominator, "analytical rows after four verified redundant exports excluded")
    metric("food_hierarchy", "Vegetable-coded", global_counts["vegetable_rows"], denominator, "analytical rows after four verified redundant exports excluded")
    for record_type in ("Individual", "Aggregated", "BLANK"):
        metric(
            "vegetable_record_type",
            record_type,
            global_counts[f"vegetable_type::{record_type}"],
            global_counts["vegetable_rows"],
            "vegetable-coded rows after four verified redundant exports excluded",
        )
    for field in ("ResultText", "LOD", "LOQ", "SerialNumber", "LabNumber"):
        metric(
            "individual_vegetable_completeness",
            f"{field}_present",
            global_counts[f"present::{field}"],
            ind_veg,
            "explicit Individual vegetable-coded rows after four verified redundant exports excluded",
        )
    for result_class in ("ND_TEXT", "NUMERIC_ZERO", "NUMERIC_POSITIVE", "NUMERIC_NEGATIVE", "OTHER_TEXT", "BLANK"):
        metric(
            "individual_vegetable_result_class",
            result_class,
            global_counts[f"result::{result_class}"],
            ind_veg,
            "explicit Individual vegetable-coded rows after four verified redundant exports excluded",
        )
    metric("censoring", "ND_or_numeric_zero", censored, ind_veg, "explicit Individual vegetable-coded rows after four verified redundant exports excluded")
    metric("censoring", "censored_with_LOD", global_counts["censored_with_lod"], censored, "ND or numeric-zero Individual vegetable rows")
    metric("censoring", "censored_with_LOQ", global_counts["censored_with_loq"], censored, "ND or numeric-zero Individual vegetable rows")

    context = {
        "files_after_verified_redundancy_exclusions": len(files) - len(WHO_REDUNDANT_EXPORTS),
        "analytical_rows_after_verified_redundancy_exclusions": denominator,
        "all_exported_rows_including_overlap": sum(int(row["rows"]) for row in file_rows),
        "food_categories": dict(categories),
        "food_origin_values": dict(origins),
        "year_values": dict(years),
        "schema_columns": WHO_COLUMNS,
        "country_field_exposed": False,
        "region_field_exposed": True,
        "risk_assessment_residue_definition_exposed": False,
        "organic_status_exposed": False,
        "compatible_current_dietary_linkage_verified": False,
        "evidence_level": "LEVEL_C_OVERALL_WITH_LEVEL_B_LIKE_INDIVIDUAL_STRUCTURE_NOT_ADMITTED",
        "new_exposure_units": 0,
    }
    return file_rows, overlaps, metrics, context


def normalize_header(value: object) -> str:
    text = clean(value).upper().replace("-", " ")
    return re.sub(r"\s+", " ", text)


def affirmative_organic(value: object) -> bool:
    text = clean(value).upper()
    return text in {"1", "1.0", "YES", "Y", "TRUE"}


def audit_california() -> tuple[list[dict], list[dict], dict]:
    annual: list[dict] = []
    sample_type_rows: list[dict] = []
    for year, filename in CA_XLSX.items():
        path = CA_DIR / filename
        workbook = load_workbook(path, read_only=True, data_only=True)
        assert len(workbook.worksheets) == 1
        sheet = workbook.worksheets[0]
        iterator = sheet.iter_rows(values_only=True)
        first = next(iterator)
        if year == 2023:
            header = next(iterator)
            assert clean(first[0]) == "Annual Residue Data 2023"
        else:
            header = first
        names = [normalize_header(value) for value in header]
        # Only the first occurrence of duplicate placeholder columns is needed.
        index = {}
        for position, name in enumerate(names):
            index.setdefault(name, position)
        lab_key = "LABORATORY NUMBER"
        pesticide_key = "PESTICIDE RESIDUE"
        amount_key = "RESIDUE AMOUNT (PPM)"
        limit_key = "DETECT_LIMIT" if year == 2023 else "REPORTING LIMIT"
        organic_key = "ORGANIC"
        type_key = "SAMPLE TYPE"
        commodity_key = "COMMODITY"
        origin_key = "STATE OR COUNTRY OF ORIGIN"
        required = {lab_key, pesticide_key, amount_key, limit_key, organic_key, commodity_key, origin_key}
        assert required.issubset(index), (year, required - set(index))

        samples: dict[str, dict] = {}
        detected_rows = placeholder_rows = data_rows = 0
        detected_with_limit = placeholder_with_limit = 0
        analytes: set[str] = set()
        commodities: set[str] = set()
        origins: set[str] = set()
        sample_types: Counter[str] = Counter()
        for values in iterator:
            lab = clean(values[index[lab_key]])
            if not lab:
                continue
            data_rows += 1
            pesticide = clean(values[index[pesticide_key]])
            upper = pesticide.upper()
            placeholder = upper in {"NO DATA", "NON-DETECT", "NON DETECT", "NONDETECT", ""}
            # A generic text placeholder (for example, ``No Data``) is not an
            # analyte-specific reporting limit.  Only positive numeric limits
            # are counted.
            limit_present = positive_numeric(values[index[limit_key]])
            record = samples.setdefault(
                lab,
                {
                    "organic": False,
                    "detected_rows": 0,
                    "placeholder_rows": 0,
                    "sample_type": "",
                },
            )
            record["organic"] = record["organic"] or affirmative_organic(values[index[organic_key]])
            if type_key in index:
                sample_type = clean(values[index[type_key]]) or "BLANK"
                if record["sample_type"] and record["sample_type"] != sample_type:
                    raise AssertionError((year, lab, record["sample_type"], sample_type))
                record["sample_type"] = sample_type
            if placeholder:
                placeholder_rows += 1
                record["placeholder_rows"] += 1
                placeholder_with_limit += int(limit_present)
            else:
                detected_rows += 1
                record["detected_rows"] += 1
                detected_with_limit += int(limit_present)
                analytes.add(pesticide)
            commodities.add(clean(values[index[commodity_key]]) or "BLANK")
            origins.add(clean(values[index[origin_key]]) or "BLANK")
        workbook.close()

        for record in samples.values():
            if type_key in index:
                sample_types[record["sample_type"] or "BLANK"] += 1
        for name, count in sorted(sample_types.items()):
            sample_type_rows.append(
                {
                    "year": year,
                    "sample_type": name,
                    "sample_ids": count,
                    "denominator_sample_ids": len(samples),
                    "percent": f"{100 * count / len(samples):.6f}",
                }
            )

        placeholder_hist = Counter(record["placeholder_rows"] for record in samples.values())
        annual.append(
            {
                "year": year,
                "source_file": filename,
                "data_rows": data_rows,
                "unique_sample_ids": len(samples),
                "detected_analyte_rows": detected_rows,
                "generic_nd_placeholder_rows": placeholder_rows,
                "samples_with_detected_analyte": sum(record["detected_rows"] > 0 for record in samples.values()),
                "samples_with_generic_nd_placeholder": sum(record["placeholder_rows"] > 0 for record in samples.values()),
                "samples_with_both_detected_and_placeholder": sum(
                    record["detected_rows"] > 0 and record["placeholder_rows"] > 0
                    for record in samples.values()
                ),
                "organic_flagged_sample_ids": sum(record["organic"] for record in samples.values()),
                "organic_denominator_sample_ids": len(samples),
                "detected_rows_with_limit": detected_with_limit,
                "detected_rows_limit_denominator": detected_rows,
                "placeholder_rows_with_analyte_specific_limit": placeholder_with_limit,
                "placeholder_rows_limit_denominator": placeholder_rows,
                "unique_detected_analytes": len(analytes),
                "unique_commodities": len(commodities),
                "unique_origin_labels": len(origins),
                "sample_type_field": "YES" if type_key in index else "NO",
                "placeholder_rows_per_sample_histogram": json.dumps(
                    dict(sorted(placeholder_hist.items())), separators=(",", ":")
                ),
                "analyte_specific_nd_denominator_reconstructable": "NO",
                "risk_based_sampling": "YES",
                "food_form_field": "NO",
                "risk_assessment_residue_definition": "NO",
                "compatible_dietary_linkage_verified": "NO",
                "evidence_level": "LEVEL_C_BRANCH_ISOLATED",
                "new_parent_exposure_units": 0,
            }
        )

    report_rows = []
    for year, filename in CA_REPORTS.items():
        reader = PdfReader(CA_DIR / filename)
        report_rows.append(
            {
                "year": year,
                "file": filename,
                "pages": len(reader.pages),
                "official_reported_samples": 3281 if year == 2022 else 3544,
                "workbook_unique_sample_ids": next(
                    row["unique_sample_ids"] for row in annual if row["year"] == year
                ),
                "difference_workbook_minus_report": next(
                    row["unique_sample_ids"] for row in annual if row["year"] == year
                )
                - (3281 if year == 2022 else 3544),
                "interpretation": (
                    "unresolved denominator difference"
                    if year == 2022
                    else "report denominator equals Original Sample IDs; workbook also contains follow-up/duplicate IDs"
                ),
            }
        )
    context = {
        "years": sorted(CA_XLSX),
        "workbooks": len(CA_XLSX),
        "reports": len(CA_REPORTS),
        "evidence_level": "LEVEL_C_BRANCH_ISOLATED",
        "new_parent_exposure_units": 0,
        "analyte_specific_nondetect_denominator_reconstructable": False,
        "sampling_estimand": "risk-directed enforcement monitoring, not probability-representative population occurrence",
        "organic_status_use": "descriptive label only; no causal comparison",
        "parent_pooling": "PROHIBITED_WITHOUT_DOCUMENTED_COMPATIBILITY_DECISION",
    }
    return annual, report_rows + sample_type_rows, context


def main() -> None:
    subprocess.run(
        ["python3", str(ROOT / "05_code" / "utilities" / "check_paths.py")],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    OUT.mkdir(parents=True, exist_ok=True)
    if "--verify" in sys.argv:
        with (OUT / "output_manifest.csv").open(
            "r", encoding="utf-8", newline=""
        ) as handle:
            output_rows = list(csv.DictReader(handle))
        for row in output_rows:
            path = OUT / row["file"]
            assert path.is_file(), path
            assert path.stat().st_size == int(row["bytes"]), path
            assert sha256(path) == row["sha256"], path

        with (OUT / "source_file_receipt.csv").open(
            "r", encoding="utf-8", newline=""
        ) as handle:
            source_rows = list(csv.DictReader(handle))
        for row in source_rows:
            path = Path(row["path"])
            assert path.is_file(), path
            assert path.stat().st_size == int(row["bytes"]), path
            assert sha256(path) == row["sha256"], path
            assert path.stat().st_mtime_ns == int(row["mtime_ns_before"]), path
        print(
            json.dumps(
                {
                    "status": "PASS_VERIFY_NO_WRITE",
                    "derived_files": len(output_rows),
                    "raw_files": len(source_rows),
                    "out": str(OUT),
                },
                ensure_ascii=False,
            )
        )
        return
    if "--refresh-output-manifest" in sys.argv:
        output_files = sorted(
            p
            for p in OUT.iterdir()
            if p.is_file()
            and not p.name.startswith("._")
            and p.name != "output_manifest.csv"
        )
        write_csv(
            OUT / "output_manifest.csv",
            [
                {"file": p.name, "bytes": p.stat().st_size, "sha256": sha256(p)}
                for p in output_files
            ],
        )
        for sidecar in OUT.glob("._*"):
            sidecar.unlink()
        print(json.dumps({"out": str(OUT), "manifested_files": len(output_files)}))
        return
    manifest = manifest_rows()
    source_paths = sorted(
        [p for p in WHO_DIR.glob("*.csv") if not p.name.startswith("._")]
        + [CA_DIR / name for name in CA_XLSX.values()]
        + [CA_DIR / name for name in CA_REPORTS.values()]
    )
    before = {
        str(path): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in source_paths
    }
    receipts = []
    for path in source_paths:
        digest = sha256(path)
        expected = manifest.get(str(path))
        assert expected is not None, f"Manifest row absent: {path}"
        assert path.stat().st_size == int(expected["bytes"]), path
        assert digest == expected["sha256"], path
        receipts.append(
            {
                "source": "WHO_GEMS_FOOD" if path.parent == WHO_DIR else "CALIFORNIA_DPR",
                "role": "CSV_EXPORT" if path.suffix.lower() == ".csv" else ("WORKBOOK" if path.suffix.lower() == ".xlsx" else "REPORT"),
                "path": str(path),
                "file": path.name,
                "bytes": path.stat().st_size,
                "sha256": digest,
                "mtime_ns_before": before[str(path)][1],
                "manifest_identity_match": "YES",
            }
        )

    who_files, who_overlaps, who_metrics, who_context = audit_who()
    ca_annual, ca_detail, ca_context = audit_california()
    for path in source_paths:
        after = (path.stat().st_size, path.stat().st_mtime_ns)
        assert after == before[str(path)], f"Raw file identity metadata changed: {path}"
    for receipt in receipts:
        receipt["bytes_unchanged"] = "YES"
        receipt["mtime_unchanged"] = "YES"

    write_csv(OUT / "source_file_receipt.csv", receipts)
    write_csv(OUT / "who_file_summary.csv", who_files)
    write_csv(OUT / "who_overlap_relations.csv", who_overlaps)
    write_csv(OUT / "who_figure_ready_completeness.csv", who_metrics)
    write_csv(OUT / "california_figure_ready_annual_structure.csv", ca_annual)
    write_csv(OUT / "california_report_and_sample_type_checks.csv", ca_detail)
    (OUT / "source_admission_receipt.json").write_text(
        json.dumps(
            {
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "status": "PASS_BOUNDED_SOURCE_ADMISSION_NO_EXPOSURE",
                "who": who_context,
                "california": ca_context,
                "raw_files_verified": len(receipts),
                "raw_bytes_and_mtime_unchanged": True,
                "new_exposure_units": 0,
                "exposure_calculations": 0,
                "organic_causal_comparisons": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    output_files = sorted(
        p
        for p in OUT.iterdir()
        if p.is_file()
        and not p.name.startswith("._")
        and p.name != "output_manifest.csv"
    )
    output_manifest = []
    for path in output_files:
        output_manifest.append(
            {
                "file": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    write_csv(OUT / "output_manifest.csv", output_manifest)
    # ExFAT may create AppleDouble sidecars for newly written derived files.
    # They are not scientific outputs and are removed only from this dedicated
    # output directory; raw directories are never touched.
    for sidecar in OUT.glob("._*"):
        sidecar.unlink()
    print(json.dumps({"out": str(OUT), "who": who_context, "california": ca_context}, ensure_ascii=False))


if __name__ == "__main__":
    main()
