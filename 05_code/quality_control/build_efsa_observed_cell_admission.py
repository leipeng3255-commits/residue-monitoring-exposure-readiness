#!/usr/bin/env python3
"""Freeze an EFSA observed-cell input inventory from the saved sample-level audit.

This does not combine years, join dietary intake, or estimate exposure. Outputs are
new diagnostics on the configured external drive; all existing files are read-only.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PATHS = yaml.safe_load((ROOT / "00_admin/paths.yaml").read_text(encoding="utf-8"))
DATA = Path(PATHS["data_root"])
INPUT = DATA / "06_outputs/diagnostics/efsa_2022_2024_sample_level_candidates_20260914T111235"
OUTPUT = DATA / "06_outputs/diagnostics/efsa_observed_cell_admission_20260920"
KEY = ("sampling_country_code", "rpc_code", "active_substance_code")


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(name: str, data: list[dict[str, str]]) -> None:
    with (OUTPUT / name).open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)


if not DATA.is_dir() or not (DATA / "02_raw_data").is_dir():
    raise RuntimeError("Configured external data root is unavailable")
if OUTPUT.exists():
    raise FileExistsError(f"Refusing to overwrite existing admission: {OUTPUT}")

summary_path = INPUT / "sample_level_cell_year_bounds.csv"
eligibility_path = INPUT / "sample_level_temporal_eligibility.csv"
qa_path = INPUT / "qa.json"
summary = rows(summary_path)
eligibility = rows(eligibility_path)
qa = json.loads(qa_path.read_text(encoding="utf-8"))
if qa["status"] != "SAMPLE_LEVEL_CANDIDATE_INPUT_COMPLETE_NO_MODEL_FITTED":
    raise ValueError("Unexpected candidate audit state")

unique = {}
for row in summary:
    key = tuple(row[col] for col in KEY) + (row["year"],)
    if key in unique:
        raise ValueError(f"Duplicate country-food-chemical-year: {key}")
    unique[key] = row

primary = []
stress = []
for row in eligibility:
    key = tuple(row[col] for col in KEY)
    years = set(row["years_meeting_n10_val3_complete_limits"].split("|"))
    if not {"2022", "2023"}.issubset(years):
        continue
    for year in ("2022", "2023"):
        item = unique[key + (year,)]
        if item["meets_n10_val3_complete_limits"] != "YES" or item["bounds_complete"] != "YES":
            raise ValueError(f"Incomplete primary bounds: {key} {year}")
        lower, upper = float(item["lower_mean_mg_kg"]), float(item["upper_mean_mg_kg"])
        if not 0 <= lower <= upper or int(item["missing_censor_limit_n"]) != 0:
            raise ValueError(f"Invalid censoring interval: {key} {year}")
        primary.append({**item, "analytical_role": "PRIMARY_YEAR_SPECIFIC_OBSERVED_CELL"})
    if "2024" in years:
        item = unique[key + ("2024",)]
        if item["meets_n10_val3_complete_limits"] != "YES" or item["bounds_complete"] != "YES":
            raise ValueError(f"Incomplete stress bounds: {key} 2024")
        lower, upper = float(item["lower_mean_mg_kg"]), float(item["upper_mean_mg_kg"])
        if not 0 <= lower <= upper or int(item["missing_censor_limit_n"]) != 0:
            raise ValueError(f"Invalid stress interval: {key} 2024")
        stress.append({**item, "analytical_role": "HELD_YEAR_RECENCY_STRESS_ONLY"})

if len(primary) != 1048 or len(stress) != 34:
    raise ValueError(f"Expected 524 replicated pairs and 34 held-year cells, got {len(primary)//2}, {len(stress)}")
if len({tuple(r[c] for c in KEY) for r in primary}) != 524:
    raise ValueError("Primary country-food-chemical key mismatch")

OUTPUT.mkdir(parents=True, exist_ok=False)
write("primary_2022_2023_observed_cell_years.csv", primary)
write("held_2024_observed_cells.csv", stress)
receipt = {
    "status": "INPUT_ADMISSION_ONLY_NO_DIET_JOIN_OR_EXPOSURE_ESTIMATE",
    "source_qa_sha256": digest(qa_path),
    "source_bounds_sha256": digest(summary_path),
    "source_eligibility_sha256": digest(eligibility_path),
    "primary_replicated_country_food_chemical_keys": 524,
    "primary_cell_year_rows": len(primary),
    "primary_country_counts_by_distinct_cell": dict(sorted(Counter(r["sampling_country_code"] for r in primary if r["year"] == "2022").items())),
    "held_2024_cell_rows": len(stress),
    "primary_csv_sha256": digest(OUTPUT / "primary_2022_2023_observed_cell_years.csv"),
    "held_csv_sha256": digest(OUTPUT / "held_2024_observed_cells.csv"),
    "interpretation": "Programme-conditioned observed bounds, years never pooled, no missing-cell fill or exposure estimate",
}
with (OUTPUT / "receipt.json").open("x", encoding="utf-8") as stream:
    json.dump(receipt, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
print(json.dumps({"output": str(OUTPUT), "primary_pairs": 524, "held_2024": len(stress)}, ensure_ascii=False))
