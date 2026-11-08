"""Audit Israel Agriculture/PPIS annual residue reports without calculating exposure.

The raw PDFs are immutable inputs. Outputs are report-level field, schema and
arithmetic checks only; they must not be interpreted as dietary exposure.
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
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "01_protocol/israel_agriculture_official_source_audit_v37.md"
AUDIT_DATE = "2026-10-16"


def load_config() -> dict[str, str]:
    config: dict[str, str] = {}
    for line in (ROOT / "00_admin/paths.yaml").read_text(encoding="utf-8").splitlines():
        match = re.match(r'^([a-z_]+):\s*"(.*)"\s*$', line)
        if match:
            config[match.group(1)] = match.group(2)
    assert Path(config["project_root"]).resolve() == ROOT
    return config


CFG = load_config()
RAW = Path(CFG["raw_data_root"]) / "israel_official/agriculture"
OUT = Path(CFG["outputs_root"]) / "manuscript_grilling_v37/israel_agriculture_source_audit"


SPECS = {
    2019: {
        "filename": "pesticideremnants_survey2019.pdf",
        "pages": 75,
        "samples": 1347,
        "crops": 80,
        "summary_regions": [264, 346, 108, 311, 318],
        "graph_regions": [264, 346, 108, 311, 318],
        "locations": None,
        "commodity_counts": [772, 355, 77, 143],
        "tomato_n": 73,
        "tomato_rows": 49,
        "tomato_next": "עדשים",
        "table_no": 3,
        "table_pages": "34-36",
        "min_max": False,
        "sampling_frame": "local produce; fields and packing houses",
    },
    2020: {
        "filename": "PPIS_seker_hadbara_2020.pdf",
        "pages": 76,
        "samples": 1590,
        "crops": 84,
        # Exact values printed in the summary (visually checked on printed p4).
        "summary_regions": [280, 249, 145, 278, 274],
        # Totals printed in the regional graph (printed p14).
        "graph_regions": [311, 545, 152, 300, 282],
        "locations": [768, 274, 548],
        "commodity_counts": None,
        "tomato_n": 87,
        "tomato_rows": 47,
        "tomato_next": "עדשים",
        "table_no": 5,
        "table_pages": "37-38",
        "min_max": False,
        "sampling_frame": "local produce; fields, packing houses and logistics/transit",
    },
    2021: {
        "filename": "pesticide_residues_in_local_agricultural_produce_for_2021.pdf",
        "pages": 61,
        "samples": 1451,
        "crops": 69,
        "summary_regions": [411, 506, 262, 272],
        "graph_regions": [411, 506, 262, 272],
        "locations": [517, 710, 224],
        "commodity_counts": None,
        "tomato_n": 68,
        "tomato_rows": 42,
        "tomato_next": "עלי חרדל",
        "table_no": 3,
        "table_pages": "32-33",
        "min_max": True,
        "sampling_frame": "local produce; fields, packing houses and logistics/transit",
    },
    2022: {
        "filename": "PPIS_seker-sheeriot-homrey-hadbara-2022.pdf",
        "pages": 66,
        "samples": 1446,
        "crops": 66,
        "summary_regions": [480, 531, 353, 82],
        "graph_regions": [480, 531, 353, 82],
        "locations": [586, 667, 193],
        "commodity_counts": [667, 540, 119, 120],
        "tomato_n": 78,
        "tomato_rows": 41,
        "tomato_next": "עירית בצלית",
        "table_no": 3,
        "table_pages": "32-33",
        "min_max": True,
        "sampling_frame": "local produce; fields, packing houses and logistics/transit",
    },
    2023: {
        "filename": "review_of_pesticide_residues_in_local_agricultural_produce__2023.pdf",
        "pages": 71,
        "samples": 1467,
        "crops": 77,
        "summary_regions": [446, 497, 361, 163],
        "graph_regions": [446, 497, 361, 163],
        "locations": [512, 702, 253],
        "commodity_counts": [710, 511, 130, 116],
        "tomato_n": 59,
        "tomato_rows": 29,
        "tomato_next": "עירית בצלית",
        "table_no": 4,
        "table_pages": "35-36",
        "min_max": True,
        "sampling_frame": "local produce; fields, packing houses and logistics/transit",
    },
    2024: {
        "filename": "survey_of_pesticide_residues_in_local_agricultural_produce_for_2024.pdf",
        "pages": 63,
        "samples": 1003,
        "crops": 76,
        # Exact values printed in the summary (printed p7); north is printed as 446.
        "summary_regions": [446, 373, 180, 171],
        # Totals in the regional graph (printed p15); north is printed as 279.
        "graph_regions": [279, 373, 180, 171],
        "locations": [120, 676, 207],
        "commodity_counts": [416, 332, 100, 155],
        "tomato_n": 36,
        "tomato_rows": 26,
        "tomato_next": "ענבים",
        "table_no": 4,
        "table_pages": "35-36",
        "min_max": True,
        "sampling_frame": "local produce; fields, packing houses and logistics/transit; intensified fresh-herb oversight for local and export markets",
    },
    2025: {
        "filename": "survey_of_pesticider_esidues_in_fresh_agricultural_produce_in_israel_for_the_year_2025.pdf",
        "pages": 57,
        "samples": 797,
        "crops": 68,
        "summary_regions": [296, 232, 138, 131],
        "graph_regions": [296, 232, 138, 131],
        "locations": [194, 421, 89, 93],
        "commodity_counts": [239, 388, 71, 99],
        "tomato_n": 15,
        "tomato_rows": 20,
        "tomato_next": "עירית בצלית",
        "table_no": 4,
        "table_pages": "34",
        "min_max": True,
        "sampling_frame": "local produce at fields, packing houses and logistics points; separately identified export-herb component",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pdf_pages(path: Path) -> int:
    result = subprocess.run(["pdfinfo", str(path)], check=True, capture_output=True, text=True)
    match = re.search(r"^Pages:\s+(\d+)\s*$", result.stdout, re.MULTILINE)
    assert match, path
    return int(match.group(1))


def pdf_envelope(path: Path) -> bool:
    with path.open("rb") as stream:
        head = stream.read(8)
        stream.seek(max(0, path.stat().st_size - 4096))
        tail = stream.read()
    return head.startswith(b"%PDF-") and b"%%EOF" in tail


def check_paths() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "05_code/utilities/check_paths.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0 and "PASS overall" in result.stdout, result.stdout + result.stderr


def read_manifest() -> list[dict[str, str]]:
    with (ROOT / "00_admin/download_manifest.csv").open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    assert rows or fields
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def extract_and_verify_sources(out: Path) -> tuple[list[dict], dict[int, str], dict[str, dict]]:
    manifest = read_manifest()
    verification: list[dict] = []
    texts: dict[int, str] = {}
    raw_before: dict[str, dict] = {}
    text_dir = out / "extracted_text"
    text_dir.mkdir(parents=True, exist_ok=True)

    for year, spec in SPECS.items():
        path = RAW / str(year) / spec["filename"]
        assert path.is_file(), path
        stat = path.stat()
        digest = sha256(path)
        raw_before[str(path)] = {"bytes": stat.st_size, "sha256": digest, "mtime_ns": stat.st_mtime_ns}
        pages = pdf_pages(path)
        envelope = pdf_envelope(path)
        matches = [
            row
            for row in manifest
            if row.get("local_file_path") == str(path)
            and row.get("sha256") == digest
            and int(row.get("bytes") or -1) == stat.st_size
        ]
        assert pages == spec["pages"] and envelope and len(matches) == 1, (year, pages, envelope, len(matches))

        text_path = text_dir / f"{year}.txt"
        subprocess.run(["pdftotext", "-layout", str(path), str(text_path)], check=True)
        text = text_path.read_text(encoding="utf-8", errors="strict")
        sentinels = [str(year), "MRL", "LOQ", "עגבני", "ממוצע"]
        sentinel_pass = all(token in text for token in sentinels)
        assert sentinel_pass, (year, sentinels)
        texts[year] = text
        verification.append(
            {
                "year": year,
                "raw_path": str(path),
                "bytes": stat.st_size,
                "sha256": digest,
                "pdf_pages": pages,
                "pdf_envelope": "PASS",
                "manifest_exact_match": "PASS",
                "manifest_download_id": matches[0]["download_id"],
                "whole_document_text_extraction": "PASS",
                "year_table_sentinels": "PASS",
            }
        )
    return verification, texts, raw_before


def field_rows() -> list[dict]:
    rows = []
    for year, spec in SPECS.items():
        rows.append(
            {
                "year": year,
                "sample_id": "NO",
                "commodity": "YES_AGGREGATE_CROP",
                "pesticide_analyte": "YES_AGGREGATE_ACTIVE_SUBSTANCE",
                "quantitative_concentration": "PARTIAL_AGGREGATE_MEAN" + ("_MIN_MAX" if spec["min_max"] else ""),
                "non_detect_information": "PARTIAL_CROP_RESIDUE_FREE_COUNTS_NOT_SAMPLE_BY_ANALYTE",
                "lod_loq": "PARTIAL_GENERIC_LOQ_0.01_SOME_0.005_NO_ANALYTE_MATRIX",
                "risk_assessment_residue_definition": "NO_VERIFIED_RISK_DEFINITION",
                "sampling_year": "YES",
                "food_form": "FRESH_PRODUCE_AGGREGATE",
                "country_market_frame": spec["sampling_frame"],
                "organic_conventional_status": "NO",
                "compatible_dietary_linkage": "NO",
                "evidence_level": "LEVEL_C",
                "exposure_unit_admitted": "NO",
            }
        )
    return rows


def schema_rows() -> list[dict]:
    rows = []
    for year, spec in SPECS.items():
        rows.append(
            {
                "year": year,
                "annual_sample_total": spec["samples"],
                "reported_crop_count": spec["crops"],
                "crop_sample_count": "YES",
                "active_substance": "YES",
                "occurrence_count": "YES",
                "mean_over_total_crop_samples_stated": "YES",
                "minimum_detected_residue": "YES" if spec["min_max"] else "NO",
                "maximum_detected_residue": "YES" if spec["min_max"] else "NO",
                "mrl_column": "YES",
                "generic_loq": "0.01 mg/kg; report states 0.005 mg/kg for some substances without a reusable analyte-specific matrix",
                "sampling_frame": spec["sampling_frame"],
                "cross_year_comparability": "DESCRIPTIVE_ONLY_NO_UNQUALIFIED_TREND",
            }
        )
    return rows


def arithmetic_rows() -> list[dict]:
    rows: list[dict] = []
    for year, spec in SPECS.items():
        for identity, values, locator in [
            ("summary_regional_counts", spec["summary_regions"], "annual summary"),
            ("regional_graph_totals", spec["graph_regions"], "regional graph"),
            ("sampling_location_totals", spec["locations"], "sampling-location graph"),
            ("commodity_group_totals", spec["commodity_counts"], "commodity-group text/graph"),
        ]:
            if values is None:
                continue
            observed = sum(values)
            expected = spec["samples"]
            rows.append(
                {
                    "year": year,
                    "identity": identity,
                    "printed_components": "+".join(str(value) for value in values),
                    "reconstructed_sum": observed,
                    "printed_annual_total": expected,
                    "difference_sum_minus_total": observed - expected,
                    "status": "PASS" if observed == expected else "PRINTED_INTERNAL_INCONSISTENCY",
                    "evidence_locator": locator,
                    "interpretation": "audit reconstruction; not an official correction",
                }
            )
    return rows


ANALYTE_RE = re.compile(r"([A-Z][A-Z0-9\- ]{2,}(?:HCl|HCL)?)")


def tomato_block(text: str, year: int) -> tuple[list[str], int]:
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if "לחומרים הפעילים שהתגלו בכל גידול" in line]
    assert starts, year
    section = starts[-1]
    start = next(i for i in range(section, len(lines)) if "עגבני" in lines[i])
    next_crop = SPECS[year]["tomato_next"]
    stop = next(i for i in range(start + 1, len(lines)) if next_crop in lines[i] and "עגבני" not in lines[i])
    return lines[start:stop], start + 1


def analyte_name(line: str) -> tuple[str, int] | None:
    matches = list(ANALYTE_RE.finditer(line))
    if not matches:
        return None
    match = matches[-1]
    name = " ".join(match.group(1).split())
    name = re.sub(r"\s+\d+$", "", name).strip()
    if name == "MRL" or "BET DAGAN" in name or name == "ISRAEL":
        return None
    return name, match.start()


def decimal_interval(token: str, role: str) -> tuple[float, float]:
    value = float(token)
    places = len(token.split(".", 1)[1]) if "." in token else 0
    unit = 10 ** (-places)
    if role == "mean":
        return max(0.0, value - unit / 2), value + unit
    return max(0.0, value - unit / 2), value + unit / 2


def parse_tomato(texts: dict[int, str]) -> tuple[list[dict], list[dict]]:
    summaries: list[dict] = []
    checks: list[dict] = []
    for year, spec in SPECS.items():
        block, source_start = tomato_block(texts[year], year)
        parsed: list[tuple[int, str, list[str]]] = []
        for offset, line in enumerate(block):
            match = analyte_name(line)
            if not match:
                continue
            name, name_start = match
            numbers = re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", line[:name_start])
            parsed.append((source_start + offset, name, numbers))
        assert len(parsed) == spec["tomato_rows"], (year, len(parsed), spec["tomato_rows"])

        summaries.append(
            {
                "year": year,
                "tomato_sample_count": spec["tomato_n"],
                "reported_crop_analyte_rows": len(parsed),
                "table": spec["table_no"],
                "printed_pages": spec["table_pages"],
                "schema": "mean_occurrences_mrl" + ("_min_max" if spec["min_max"] else ""),
                "permitted_interpretation": "year-specific reporting descriptor only",
                "prohibited_interpretation": "no probability-sample trend; no exposure calculation",
            }
        )

        if not spec["min_max"]:
            continue
        name_index: dict[str, int] = {}
        for line_number, name, numbers in parsed:
            name_index[name] = name_index.get(name, 0) + 1
            row_id = f"{year}_TOMATO_{name.replace(' ', '_')}_{name_index[name]}"
            special = None
            if year == 2022 and name == "DIFENOCONAZOLE":
                special = (numbers[0], numbers[1], "", numbers[2], numbers[3])
            elif year == 2022 and name == "IMIDACLOPRID" and len(numbers) == 3:
                special = (numbers[0], numbers[1], "", "", numbers[2])
            elif year == 2024 and name == "DIFENOCONAZOLE":
                special = (numbers[0], numbers[1], "", numbers[2], numbers[3])
            elif year == 2025 and name == "BOSCALID":
                special = (numbers[0], numbers[1], "", "", numbers[2])

            if special is not None:
                mrl, mean, high, low, occurrences = special
            elif len(numbers) >= 5:
                mrl, mean, high, low, occurrences = numbers[-5:]
            elif len(numbers) == 4:
                mrl = ""
                mean, high, low, occurrences = numbers
            else:
                raise AssertionError((year, name, numbers))

            if not high or not low:
                status = "INCOMPLETE_FOR_CHECK"
                mean_total_low = mean_total_high = detection_total_low = detection_total_high = ""
            else:
                mean_low, mean_high = decimal_interval(mean, "mean")
                low_low, _ = decimal_interval(low, "bound")
                _, high_high = decimal_interval(high, "bound")
                k = int(float(occurrences))
                n = int(spec["tomato_n"])
                mean_total_low = n * mean_low
                mean_total_high = n * mean_high
                detection_total_low = k * low_low
                detection_total_high = k * high_high
                possible = mean_total_high + 1e-12 >= detection_total_low and mean_total_low - 1e-12 <= detection_total_high
                status = "CONSISTENT_WITHIN_PRECISION_ALLOWANCE" if possible else "INTERNALLY_INCONSISTENT_AFTER_PRECISION_ALLOWANCE"

            checks.append(
                {
                    "row_id": row_id,
                    "year": year,
                    "commodity": "tomato",
                    "crop_sample_count": spec["tomato_n"],
                    "analyte": name,
                    "mrl_printed": mrl,
                    "mean_printed": mean,
                    "maximum_printed": high,
                    "minimum_printed": low,
                    "occurrences_printed": occurrences,
                    "mean_implied_total_lower": mean_total_low,
                    "mean_implied_total_upper": mean_total_high,
                    "detection_implied_total_lower": detection_total_low,
                    "detection_implied_total_upper": detection_total_high,
                    "status": status,
                    "pdftotext_line": line_number,
                    "printed_table_pages": spec["table_pages"],
                    "note": "precision-aware table identity only; no value corrected and no exposure inferred",
                }
            )
    return summaries, checks


def manifest_outputs(out: Path) -> None:
    rows = []
    for path in sorted(
        p
        for p in out.rglob("*")
        if p.is_file() and p.name != "derived_manifest.csv" and not p.name.startswith("._")
    ):
        rows.append(
            {
                "relative_path": str(path.relative_to(out)),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    write_csv(out / "derived_manifest.csv", rows)


def build(out: Path) -> None:
    check_paths()
    out.mkdir(parents=True, exist_ok=True)
    verification, texts, raw_before = extract_and_verify_sources(out)
    write_csv(out / "source_verification.csv", verification)
    write_csv(out / "field_availability.csv", field_rows())
    write_csv(out / "annual_schema_and_counts.csv", schema_rows())
    arithmetic = arithmetic_rows()
    write_csv(out / "report_level_arithmetic.csv", arithmetic)
    tomato_summary, tomato_checks = parse_tomato(texts)
    write_csv(out / "tomato_reporting_summary.csv", tomato_summary)
    write_csv(out / "tomato_mean_bound_checks.csv", tomato_checks)

    raw_after = {}
    for raw_path in raw_before:
        path = Path(raw_path)
        stat = path.stat()
        raw_after[raw_path] = {"bytes": stat.st_size, "sha256": sha256(path), "mtime_ns": stat.st_mtime_ns}
    assert raw_before == raw_after

    status_counts: dict[str, int] = {}
    for row in tomato_checks:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
    receipt = {
        "audit_date": AUDIT_DATE,
        "protocol": str(PROTOCOL),
        "source_series": "Israel Ministry of Agriculture / PPIS annual pesticide-residue reports 2019-2025",
        "source_files_verified": len(verification),
        "source_years": sorted(SPECS),
        "manifest_matches": len(verification),
        "evidence_level": "LEVEL_C",
        "new_exposure_ready_units": 0,
        "exposure_calculations": 0,
        "tomato_sample_counts_by_year": {str(year): SPECS[year]["tomato_n"] for year in SPECS},
        "tomato_row_counts_by_year": {str(row["year"]): row["reported_crop_analyte_rows"] for row in tomato_summary},
        "tomato_precision_check_status_counts_2021_2025": status_counts,
        "report_level_internal_inconsistencies": [
            {"year": row["year"], "identity": row["identity"], "difference": row["difference_sum_minus_total"]}
            for row in arithmetic
            if row["status"] != "PASS"
        ],
        "raw_immutability": "PASS_BYTES_SHA256_MTIME_UNCHANGED",
        "decision": "NO_NEW_EXPOSURE_UNIT; REPORT_LEVEL_CONTEXT_AND_REPRODUCIBILITY_CASE_ONLY",
        "limitations": [
            "No public sample identifiers or complete sample-by-analyte matrix.",
            "No analyte-specific LOD/LOQ censoring matrix or verified risk-assessment residue-definition crosswalk.",
            "No compatible dietary linkage; production-point sampling is not a consumer-market probability sample.",
            "Annual sample allocation, crop mix and table schema differ; no unqualified time trend is admissible.",
            "Printed inconsistencies are preserved and not silently corrected.",
        ],
    }
    write_json(out / "audit_receipt.json", receipt)
    manifest_outputs(out)


def file_map(folder: Path) -> dict[str, str]:
    return {
        str(path.relative_to(folder)): sha256(path)
        for path in folder.rglob("*")
        if path.is_file() and not path.name.startswith("._")
    }


def verify() -> None:
    assert OUT.is_dir(), OUT
    with tempfile.TemporaryDirectory(prefix="israel-agri-v37-verify-") as temp:
        temp_out = Path(temp)
        build(temp_out)
        expected = file_map(OUT)
        observed = file_map(temp_out)
        assert expected == observed, {
            "missing": sorted(set(expected) - set(observed)),
            "unexpected": sorted(set(observed) - set(expected)),
            "changed": sorted(key for key in expected.keys() & observed.keys() if expected[key] != observed[key]),
        }
    print(f"PASS verify: {len(expected)} derived files are byte-identical; raw data unchanged")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        verify()
        return
    if OUT.exists():
        shutil.rmtree(OUT)
    build(OUT)
    print(f"PASS build: {OUT}")
    print("Decision: LEVEL_C; 0 new exposure-ready units; no exposure calculated")


if __name__ == "__main__":
    main()
