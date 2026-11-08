"""Re-express historical evidence concurrently; no new admission or raw write."""
import collections as C
import csv,json,hashlib
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2]
CFG=yaml.safe_load((ROOT/'00_admin/paths.yaml').read_text())
OUT=Path(CFG['intermediate_data_root'])/'depth_extension_v31_20261014'
BASE=ROOT/'10_submission/最终投稿材料_v30_31面板科学图修订_文件夹版/03_可复现数据与代码_NOT_DIRECT_UPLOAD/tables'
D=Path(CFG['outputs_root'])/'diagnostics/efsa_scientific_exposure_admission'
def read(p):return list(csv.DictReader(p.open(encoding='utf-8-sig',newline='')))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,rows):
    with (OUT/name).open('x',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def key(r):return (r['reporting_country'],r['rpc_code'],r['active_substance_code'])
ledger=read(BASE/'admission_decision_ledger.csv'); strict=read(D/'macp_37_execution_readiness_20260921_v6.csv')
occ=read(D/'macp_occurrence_lbub.csv')
eligible={key(r):r for r in occ if r['year']=='2022' and r['rpc_code']=='P0231010A'}
st={key(r):r for r in strict}
assert len(ledger)==262 and len(eligible)==82
V='VERIFIED';N='NOT_YET_AUDITED';K='KNOWN_INCOMPATIBLE';O='OUTSIDE_ESTIMAND';R='NOT_REQUIRED'
rows=[]; bundles=[]
for r in ledger:
    k=key(r); unit='|'.join(k); src=eligible.get(k); s=st.get(k)
    admitted=r['current_classification']=='PRIMARY_MACP_ADMISSIBLE'
    common=dict(unit_id=unit,market=k[0],food=r['vegetable'],chemical=r['pesticide'],
                historical_disposition=r['current_classification'],review_date='2026-10-14',
                target='2022_MACP_RAW_TOMATO_HISTORICAL_SCENARIO')
    def add(gate,status,owner,evidence,note):
        rows.append(dict(**common,gate=gate,status=status,issue_owner=owner,evidence_locator=evidence,note=note))
    add('target_scope',V if src else O,'ESTIMAND_SELECTION','macp_occurrence_lbub.csv::'+unit,
        '2022 MACP tomato row exists in checked historical frame' if src else
        'No such row in checked historical frame; other years/programmes/foods remain evidence, not missing surveillance')
    if src:
        limits=V if src['loq_complete']=='YES' and int(src['duplicate_conflict_n'])==0 else N
        add('typed_numeric_limits',limits,'SOURCE_SPECIFIC_REVIEW','macp_occurrence_lbub.csv::2022|'+unit,
            'Historical aggregation documents limits and conflicts; this does not adjudicate complete chemical expression')
    else:add('typed_numeric_limits',N,'INVESTIGATOR_REVIEW','admission_decision_ledger.csv::'+unit,
             'Not transferred from unexamined year/programme; absent review is not source nondisclosure')
    ls=r['library_status']
    chemical=V if ls in ('RD_EXACT','RD_CONVERSION_AVAILABLE') else K if ls=='RD_MISMATCH_NO_CONVERSION' else N
    add('crop_specific_documentary_chemistry',chemical,'DEFINITION_COMPATIBILITY' if chemical==K else 'INVESTIGATOR_REVIEW',
        'admission_decision_ledger.csv::'+unit+'::library_status',
        'Saved application-specific review, not universal/current regulation: '+ls+'; '+r['current_reason'])
    add('source_identity_expression',V if admitted else N,'SOURCE_SPECIFIC_REVIEW',
        ('source_bindings.csv::'+r['reporting_country']+'|2022|A0DMX|K009A|ST10A|'+r['active_substance_code']) if admitted else 'admission_decision_ledger.csv::'+unit,
        'Complete-expression raw reconstruction passed' if admitted else 'No completed source-specific full-expression admission established by these records')
    add('raw_food_form',V if s else N,'SOURCE_SPECIFIC_REVIEW',
        'macp_37_execution_readiness_20260921_v6.csv::'+unit if s else 'admission_decision_ledger.csv::'+unit,
        'Strict raw-RPC mapping recorded' if s else 'Technical food-code bridge is not sufficient evidence of source food-form compatibility')
    add('pesticide_processing_factor',R,'TARGET_DEFINITION','depth_extension_v31_20261014.md::Targets',
        'No adjustment requested for declared raw-RPC target; not a pass for prepared/as-eaten food')
    add('native_paired_output',V if admitted else N,'IMPLEMENTATION_REVIEW','cell_diagnostics.csv' if admitted else 'admission_decision_ledger.csv::'+unit,
        'Saved paired export verified' if admitted else 'No completed paired output admitted; do not run before other required gates')
    add('monitoring_mean_research_path',V,'COMMON_METHOD_SUPPORT','manuscript.md::2.4; supplementary_material.md::S34',
        'Documented method/code/saved-output support for research adaptation; not an official endorsement or source-specific pass')
    add('hosted_build_identifier','NOT_DISCLOSED_IN_CHECKED_SOURCE','SOFTWARE_PROVENANCE','manuscript.md::2.4',
        'Exact hosted-build identifier unavailable in checked interface; public software tag does not prove hosted build identity')
    # A second target is not silently passed because a historical model runs.
    add('contemporary_population_link',N,'NEW_DESIGN_AND_LINKAGE_EVIDENCE','manuscript.md::2.1|3.3|4',
        'No established contemporary supply/population correspondence or adequate design weights; not an inferential licence')
    needs=[]
    if not src:needs.append('DEFINE_SEPARATE_ELIGIBLE_SOURCE_TARGET')
    if chemical==K:needs.append('RESOLVE_DEFINITION_WITH_VALID_MEASUREMENT_OR_JUSTIFIED_CONVERSION')
    elif chemical==N:needs.append('ADJUDICATE_CROP_SPECIFIC_CHEMISTRY')
    if not admitted:needs.append('VERIFY_SOURCE_EXPRESSION_FOOD_LIMITS_AND_IDENTITIES')
    if src and not s:needs.append('REASSESS_QUESTION_WITHOUT_ASSUMING_QUANTIFIED_COUNT_IS_SCIENTIFIC_NECESSITY')
    if not admitted:needs.append('PAIRED_IMPLEMENTATION_QA_ONLY_AFTER_SCIENTIFIC_ADMISSION')
    bundles.append(dict(unit_id=unit,historical_target_in_scope=bool(src),historical_admission=admitted,
        necessary_work_bundle='|'.join(needs) or 'MAINTAIN_DOCUMENTED_SCENARIO_LIMITS',
        current_population_additional_bundle='ESTABLISH_TARGET_AND_SUPPLY_LINK|AUDIT_SAMPLING_DESIGN|MATCH_DIETARY_PERIOD_AND_FOOD',
        admission_after_work='NOT_GUARANTEED',basis='Concurrent documented states; not minimum-cost or optimal information-value analysis'))
counts=C.Counter((r['gate'],r['status']) for r in rows)
write('concurrent_gate_262_long.csv',rows)
write('concurrent_gate_summary.csv',[dict(gate=g,status=s,units=n,denominator=262) for (g,s),n in sorted(counts.items())])
write('necessary_evidence_bundles.csv',bundles)
report=dict(units=262,gate_rows=len(rows),in_fixed_target=len(eligible),outside_fixed_target=262-len(eligible),
    strict_selected=37,in_target_below_historical_rule=len(eligible)-37,
    no_new_admissions=True,no_first_reason_causal_attribution=True,
    investigator_unknown_not_national_absence=True,
    inputs={str(p):sha(p) for p in [BASE/'admission_decision_ledger.csv',D/'macp_37_execution_readiness_20260921_v6.csv',D/'macp_occurrence_lbub.csv']})
with (OUT/'concurrent_gate_receipt.json').open('x') as h:json.dump(report,h,indent=2)
print(json.dumps(report,indent=2))
