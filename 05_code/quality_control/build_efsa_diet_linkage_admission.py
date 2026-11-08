#!/usr/bin/env python3
"""Auditable EFSA–RPC2 linkage gate; never computes pesticide exposure."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
P = {k.strip(): v.strip().strip('"') for k, v in
     (line.split(":", 1) for line in (ROOT / "00_admin/paths.yaml").read_text(encoding="utf-8").splitlines()
     if line.strip() and not line.lstrip().startswith("#"))}
D = Path(P["data_root"])
PRE = D / "06_outputs/diagnostics/efsa_rpc2_exact_link_candidates_20260920"
SCOPE = D / "06_outputs/diagnostics/efsa_vegetable_scope_screen_20260920"
pre_path = PRE / "code_country_candidates.csv"
scope_path = SCOPE / "primary_food_scope_screen.csv"
RPC2 = D / "02_raw_data/efsa_zenodo/19455832/ANNEX C - RPC model summary statistics.xlsx"
MAP = D / "02_raw_data/efsa_zenodo/15363327/Annex B_FoodEx2 Coding.xlsx"
OUT = D / "06_outputs/diagnostics/efsa_diet_linkage"
CROSS = D / "04_processed/efsa_diet_food_crosswalk.parquet"
PRIMARY = D / "04_processed/efsa_diet_primary_admissible_cells.parquet"
COUNTRY = {"BE":"Belgium","CY":"Cyprus","CZ":"Czechia","DE":"Germany",
           "DK":"Denmark","ES":"Spain","FI":"Finland","FR":"France",
           "GR":"Greece","HR":"Croatia","HU":"Hungary","IE":"Ireland",
           "IT":"Italy","NL":"Netherlands","PL":"Poland","RO":"Romania"}
KEY = ("sampling_country_code", "rpc_code", "active_substance_code")


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def write(name: str, rows: list[dict[str, object]], fields: list[str] | None = None) -> None:
    path = OUT / name
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def years_from_label(label: str) -> list[int]:
    # Label tokens are provisional; they are not verified fieldwork dates.
    return [int(x) for x in re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", label)]


if not D.is_dir() or not (D / "02_raw_data").is_dir():
    raise RuntimeError("Configured external data root unavailable")
if OUT.exists() or CROSS.exists() or PRIMARY.exists():
    raise FileExistsError("Linkage output exists; refusing overwrite")
pr = json.loads((PRE / "receipt.json").read_text(encoding="utf-8"))
scope_receipt = json.loads((SCOPE / "receipt.json").read_text(encoding="utf-8"))
if sha(pre_path) != pr["output_sha256"] or sha(scope_path) != scope_receipt["primary_screen_sha256"]:
    raise ValueError("Saved candidate inputs do not match receipts")
pre = read(pre_path)
scope = read(scope_path)
if len(pre) != 492 or len(scope) != 1048:
    raise ValueError("Candidate denominator changed")

base = {tuple(r[k] for k in KEY): r for r in scope if r["year"] == "2022"}
pea = [r for r in base.values() if r["rpc_code"] == "P0260040A"]
if len(pea) != 2:
    raise ValueError("Expected two shelled-pea candidate keys")
candidate = {tuple(r[k] for k in KEY): r for r in scope
             if r["year"] == "2022" and r["food_scope_status"] == "CANDIDATE_FOOD_SCOPE"}
candidate.update({tuple(r[k] for k in KEY): r for r in pea})
if len(candidate) != 494:
    raise ValueError("Vegetable-scope key count after pea decision changed")

wb = openpyxl.load_workbook(MAP, read_only=True, data_only=True)
official: dict[str, set[str]] = defaultdict(set)
for row in wb["FoodEx2 coding processed food"].iter_rows(min_row=2, max_col=4, values_only=True):
    if row[2] and row[3]:
        official[str(row[2])].add(str(row[3]))
wb.close()

target_codes = {x for r in candidate.values() for x in official.get(r["rpc_code"][:-1], set())}
target_countries = set(COUNTRY.values())
wb = openpyxl.load_workbook(RPC2, read_only=True, data_only=True)
diet: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
facet_counts: Counter[tuple[str, str, str]] = Counter()
for row in wb["Table C.2"].iter_rows(min_row=5, max_col=25, values_only=True):
    if row[1] not in target_countries or not isinstance(row[15], (int, float)):
        continue
    code = str(row[13] or "")
    for target in target_codes:
        if code.startswith(target + "#"):
            facet_counts[(str(row[1]), str(row[2]), target)] += 1
    if code not in target_codes:
        continue
    diet[(str(row[1]), code)].append({"popclass":str(row[0]),"survey":str(row[2]),
                                     "food_label":str(row[14]),"n":int(row[15]),
                                     "consumer_percent":float(row[16]),
                                     "mean_g_kg_bw_day":float(row[17]),"sd":float(row[18]),
                                     "median_g_kg_bw_day":float(row[19])})
wb.close()

form, hierarchy, temporal, duplicates, availability, pending, final, crosswalk = ([] for _ in range(8))
for key, row in sorted(candidate.items()):
    country_code, rpc, pesticide = key
    country = COUNTRY[country_code]
    codes = sorted(official.get(rpc[:-1], set()))
    exact_code = codes[0] if len(codes) == 1 else ""
    matches = diet.get((country, exact_code), []) if exact_code else []
    surveys = sorted({m["survey"] for m in matches})
    popclasses = sorted({m["popclass"] for m in matches})
    facet_n = sum(facet_counts[(country, s, exact_code)] for s in surveys)
    code_status = "RESOLVED_EXACT" if len(codes) == 1 and matches else "NO_COMPATIBLE_INTAKE_VARIABLE"
    intake_status = "INTAKE_PARTIAL" if matches else "INTAKE_UNAVAILABLE"
    form_status = "FORM_AGGREGATED" if matches else "FORM_UNKNOWN"
    hierarchy_status = "AGGREGATION_REQUIRED" if facet_n else "EXACT_LEVEL" if matches else "INCOMPATIBLE"
    dup_status = "HIERARCHICAL_OVERLAP" if facet_n else "ONE_TO_ONE" if matches else "UNRESOLVED"
    # Raw-primary-commodity equivalents may include recipe/processing allocation;
    # form equivalence and processing factors are not confirmed by a code match.
    reason = ("RAW_EQUIVALENT_PROCESSING_AND_SURVEY_YEAR_UNVERIFIED" if matches
              else "NO_SAME_COUNTRY_EXACT_CODE_ROW_IN_OFFICIAL_C2")
    status = "HOLD" if matches else "EXCLUDE"
    base_fields = {"sampling_country_code":country_code,"survey_country":country,
                   "rpc_code":rpc,"rpc_name":row["rpc_name"],
                   "active_substance_code":pesticide,"foodex_code":exact_code,
                   "mapping_method":"OFFICIAL_MATRIX_TO_RPC_CODE_EXACT" if exact_code else "NO_UNIQUE_OFFICIAL_CODE",
                   "mapping_confidence":"EXACT_CODE_ONLY" if matches else "UNRESOLVED"}
    form.append({**base_fields,"form_status":form_status,"residue_form":"RAW_PRIMARY_COMMODITY_MONITORING",
                 "diet_form":"MODELLED_RAW_PRIMARY_COMMODITY_EQUIVALENT" if matches else "NO_VARIABLE",
                 "processing_factor_available":"NO","edible_portion_compatibility":"UNVERIFIED",
                 "reason":reason})
    hierarchy.append({**base_fields,"hierarchy_status":hierarchy_status,
                      "same_country_base_rows":len(matches),"same_country_facet_rows":facet_n,
                      "parent_child_simultaneous_use":"PROHIBITED"})
    duplicates.append({**base_fields,"mapping_graph_status":dup_status,
                       "intake_code_reused_across_pesticides":"YES_PESTICIDE_SPECIFIC_ONLY" if matches else "NO_VARIABLE",
                       "risk":"DO_NOT_SUM_BASE_AND_FACET_OR_REUSE_FOOD_MEAN_AS_DISTINCT_CONSUMPTION"})
    availability.append({**base_fields,"intake_status":intake_status,
                         "actual_rows":len(matches),"unit":"g/kg bw/day" if matches else "NOT_AVAILABLE",
                         "statistic":"TOTAL_POPULATION_MEAN_MEDIAN_SD" if matches else "NOT_AVAILABLE",
                         "age_strata":"|".join(popclasses),"sex_strata":"NOT_AVAILABLE",
                         "sample_n_values":"|".join(str(n) for n in sorted({m["n"] for m in matches})),
                         "survey_weights":"NOT_REPORTED_IN_AGGREGATE_TABLE",
                         "uncertainty":"SD_NOT_STANDARD_ERROR_OR_MODEL_UNCERTAINTY" if matches else "NOT_AVAILABLE",
                         "zero_consumer_handling":"TOTAL_POPULATION_INCLUDES_ZERO_CONSUMERS" if matches else "NOT_AVAILABLE",
                         "data_type":"MODELLED_AGGREGATE_NOT_INDIVIDUAL" if matches else "NOT_AVAILABLE"})
    for year in (2022, 2023):
        if matches:
            for survey in surveys:
                tokens = years_from_label(survey)
                temporal.append({**base_fields,"residue_year":year,"diet_survey":survey,
                                 "survey_label_year_tokens":"|".join(map(str,tokens)),
                                 "diet_survey_year":"NOT_VERIFIED",
                                 "absolute_year_gap":"NOT_VERIFIED",
                                 "provisional_label_gap":min(abs(year-y) for y in tokens) if tokens else "",
                                 "temporal_status":"UNVERIFIED_SURVEY_YEAR"})
        else:
            temporal.append({**base_fields,"residue_year":year,"diet_survey":"NONE",
                             "survey_label_year_tokens":"","diet_survey_year":"NOT_AVAILABLE",
                             "absolute_year_gap":"NOT_AVAILABLE","provisional_label_gap":"",
                             "temporal_status":"TEMPORALLY_UNSUPPORTED"})
    if key in {tuple(r[k] for k in KEY) for r in scope if r["year"] == "2022" and r["food_scope_status"] == "CANDIDATE_FOOD_SCOPE"}:
        if any(p["reporting_country_code"] == country_code and p["residue_rpc_code"] == rpc and
               p["link_status"].startswith("HOLD") for p in pre):
            pending.append({**base_fields,"resolution":code_status,
                            "original_intake_food":"|".join(sorted({m["food_label"] for m in matches})) if matches else "NONE_IN_SAME_COUNTRY_C2",
                            "harmonised_food":exact_code or "NONE",
                            "reason":reason})
    final.append({**base_fields,"food_scope":"INCLUDE","code_resolution":code_status,
                  "food_form":form_status,"hierarchy":hierarchy_status,
                  "duplicate_risk":dup_status,"intake_availability":intake_status,
                  "country_link":"REPORTING_MARKET_TO_SURVEY_COUNTRY_EXACT",
                  "origin_country":"NOT_PRESERVED_IN_CELL_YEAR_SUMMARY",
                  "temporal_alignment":"UNVERIFIED_SURVEY_YEAR" if matches else "TEMPORALLY_UNSUPPORTED",
                  "residue_bounds":"COMPLETE_2022_AND_2023",
                  "final_status":status,"reason":reason})
    crosswalk.append({**base_fields,"food_scope":"INCLUDE","diet_variable_exists":bool(matches),
                      "dietary_surveys":"|".join(surveys),"final_status":status})

if len(final) != 494 or len(pending) != 188:
    raise ValueError(f"Unexpected final/pending counts: {len(final)}, {len(pending)}")
OUT.mkdir(parents=True, exist_ok=False)
files = {"food_form_audit.csv":form,"hierarchy_audit.csv":hierarchy,
         "temporal_alignment.csv":temporal,"duplicate_consumption_risk.csv":duplicates,
         "intake_availability.csv":availability,"pending_188_resolution.csv":pending,
         "final_admission_status.csv":final}
for name, rows in files.items():
    write(name, rows)

for field, name in (("sampling_country_code","country_coverage.csv"),
                    ("rpc_code","food_coverage.csv"),
                    ("active_substance_code","pesticide_coverage.csv")):
    groups: dict[str, Counter[str]] = defaultdict(Counter)
    for r in final:
        groups[r[field]][r["final_status"]] += 1
    write(name,[{field:k,"primary_admissible":v["PRIMARY_ADMISSIBLE"],
                 "secondary_admissible_with_caveat":v["SECONDARY_ADMISSIBLE_WITH_CAVEAT"],
                 "sensitivity_only":v["SENSITIVITY_ONLY"],"hold":v["HOLD"],
                 "exclude":v["EXCLUDE"]} for k,v in sorted(groups.items())])
write("population_coverage.csv",[{"population":"WORLD","primary_represented_percent":"NOT_CALCULATED",
                                  "reason":"NO_PRIMARY_ADMISSIONS_AND_NO_VALID_GLOBAL_DENOMINATOR_JOIN"}])
write("vegetable_consumption_coverage.csv",[{"population":"WORLD","primary_vegetable_consumption_percent":"NOT_CALCULATED",
                                           "reason":"NO_PRIMARY_ADMISSIONS_AND_NO_VALID_GLOBAL_INTAKE_DENOMINATOR_JOIN"}])

pq.write_table(pa.Table.from_pylist(crosswalk), CROSS)
primary_rows = [r for r in final if r["final_status"] == "PRIMARY_ADMISSIBLE"]
schema = pa.schema([(k, pa.string()) for k in final[0]])
pq.write_table(pa.Table.from_pylist([{k:str(v) for k,v in r.items()} for r in primary_rows], schema=schema), PRIMARY)
count = Counter(r["final_status"] for r in final)
report = ("# EFSA–diet linkage admission report\n\n"
          f"Source-scope candidates: 492; newly included shelled-pea keys: 2; evaluated: {len(final)}.\n\n"
          f"Final statuses: PRIMARY_ADMISSIBLE={count['PRIMARY_ADMISSIBLE']}, "
          f"SECONDARY_ADMISSIBLE_WITH_CAVEAT={count['SECONDARY_ADMISSIBLE_WITH_CAVEAT']}, "
          f"SENSITIVITY_ONLY={count['SENSITIVITY_ONLY']}, HOLD={count['HOLD']}, "
          f"EXCLUDE={count['EXCLUDE']}.\n\n"
          "The 188 prior pending keys are resolved **for this RPC2 release** in `pending_188_resolution.csv`; "
          "other compatible dietary sources are not ruled out. A Table C.1 catalogue entry was never treated as an intake value: "
          "actual Table C.2 country-food rows were checked. Matched intake is modelled raw-commodity equivalent, "
          "not demonstrated to be the same physical food form as monitored residue; processed food allocations, "
          "parent/child hierarchy, origin mix and survey fieldwork years remain unverified. "
          "No primary, secondary or sensitivity exposure link is released from these unresolved gates.\n\n"
          "Label-derived four-digit years are retained only as exploratory gap tokens in `temporal_alignment.csv`; "
          "their distribution must be reviewed against official survey metadata before a prespecified "
          "CONTEMPORANEOUS / NEAR_TEMPORAL / HISTORICAL / TEMPORALLY_UNSUPPORTED rule can be locked. "
          "No arbitrary threshold or implied temporal invariance is used.\n\n"
          "Population and vegetable-consumption represented percentages: NOT CALCULATED. "
          "No EDI, HQ, scenario or burden estimate was produced.\n")
with (OUT / "linkage_admission_report.md").open("x", encoding="utf-8") as stream:
    stream.write(report)
receipt = {"source_preflight_sha256":sha(pre_path),"source_scope_sha256":sha(scope_path),
           "rpc2_annex_c_sha256":sha(RPC2),"official_mapping_sha256":sha(MAP),
           "evaluated_keys":len(final),"prior_pending_keys":len(pending),
           "status_counts":dict(count),"diagnostic_sha256":{n:sha(OUT/n) for n in [*files,
             "country_coverage.csv","food_coverage.csv","pesticide_coverage.csv",
             "population_coverage.csv","vegetable_consumption_coverage.csv","linkage_admission_report.md"]},
           "crosswalk_parquet_sha256":sha(CROSS),"primary_parquet_sha256":sha(PRIMARY)}
with (OUT / "receipt.json").open("x", encoding="utf-8") as stream:
    json.dump(receipt, stream, indent=2, ensure_ascii=False)
    stream.write("\n")
print(json.dumps({"status_counts":dict(count),"pending_188":len(pending),
                  "primary_parquet_rows":pq.ParquetFile(PRIMARY).metadata.num_rows},ensure_ascii=False))
