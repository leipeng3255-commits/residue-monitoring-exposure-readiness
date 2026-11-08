"""Generate a bounded v23 revision from preserved v22; never alter raw/frozen data."""
import csv, hashlib, json, shutil
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'10_submission/最终投稿材料_v22_文件夹版'
WORK=ROOT/'08_manuscript/question_decisions_v23'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write_csv(p, data):
    with p.open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
def replace(s,a,b):
    assert s.count(a)==1,(a[:100],s.count(a));return s.replace(a,b,1)

assert all(sha(OLD/r['path'])==r['sha256'] for r in json.loads((OLD/'file_manifest.json').read_text()))
cfg=yaml.safe_load((ROOT/'00_admin/paths.yaml').read_text())
assert Path(cfg['data_root']).is_dir()
receipt_dir=Path(cfg['outputs_root'])/'diagnostics/question_interval_v23_20261009'
test=json.loads((receipt_dir/'interval_rule_first_run.json').read_text());assert not test['failures']
WORK.mkdir(exist_ok=False)
q=WORK/'question_rules_v23';q.mkdir()
for name in ['interval_rule_first_run.json','empirical_question_outcomes.csv']:
    shutil.copy2(receipt_dir/name,q/name)
for rel in ['01_protocol/question_interval_cases_v23.json','01_protocol/question_interval_rules_v23_20261009.md','05_code/quality_control/question_interval_audit_v23.py']:
    shutil.copy2(ROOT/rel,q/Path(rel).name)
v22=ROOT/'08_manuscript/existing_data_evidence_v22'
for directory in ['evidence_extension','new_figure_v2','reviews']:
    shutil.copytree(v22/directory,WORK/directory)
for name in ['calculation_validation.json','preservation_checks.json','spacing_repair.json']:
    shutil.copy2(v22/name,WORK/name)

# Five selected, retrospective, fully populated records. Roles are proposals, not people.
package=OLD/'01_Food_Control'
cells=rows(package/'tables/cell_diagnostics.csv');ratios=rows(package/'tables/same_chemical_ratio_bounds.csv')
pairs=rows(package/'evidence_extension_v22/paired_concentration_bounds.csv')
bycell={(r['occurrence_country'],r['pesticide']):r for r in cells}
byratio={r['pesticide']:r for r in ratios};bypair={r['pesticide']:r for r in pairs}
run=json.loads((package/'evidence_extension_v22/run_receipt.json').read_text())
br=json.loads((package/'provenance/brazil_two_pair_feasibility.json').read_text())
panel_scope=ROOT/'00_admin/local_data_readiness_20260930/brazil_panel_scope_audit.json'
shutil.copy2(panel_scope,q/panel_scope.name)
br_scope=json.loads(panel_scope.read_text())
records=[]
def record(id,target,path,key,values,status,c,i,a,claim,gaps,role,next_action,trigger):
    records.append(dict(record_id=id,record_date='2026-10-09',record_type='RETROSPECTIVE_WORKED_RECORD_NOT_INDEPENDENT_REVIEW',
      target=target,source_version='2022 occurrence / frozen 2026-09-21 snapshot' if id.startswith('EU') else 'PARA 2017-2018; preserved official PDFs' if id.startswith('BR') else 'DE 2022 archive; resolved v22 extension 2026-10-08',
      source_locator=path,source_key_or_pages=key,source_sha256=sha(q/Path(path).name if path.startswith('question_rules_v23/') else package/path),recorded_values=values,
      evidence_status=status,calculability=c,information_adequacy=i,inferential_applicability=a,permitted_claim=claim,
      unresolved_evidence=gaps,proposed_responsible_role=role,next_action=next_action,review_trigger=trigger))
r=bycell['DE','abamectin']
record('EU_REFERENCE_DE_ABAMECTIN','Does the saved maximum single-food survey-mean interval exceed 100% of the frozen ADI?',
 'tables/cell_diagnostics.csv','DE|abamectin; S8, S28; matched 88 historical strata',
 f"%ADI mean interval [{r['max_mean_percent_ADI_LB']}, {r['max_mean_percent_ADI_UB']}]; threshold=100; sample_n=214",
 'VERIFIED_SAVED_RESULTS; DOCUMENTED_RESEARCH_ADAPTATION', 'SUPPORTED_FOR_DOCUMENTED_RESEARCH_SCENARIO',
 'NO_EXCEEDANCE_WITHIN_RECORDED_CENSORING_BOUNDS', 'HISTORICAL_RAW_SINGLE_FOOD_SCENARIO_ONLY',
 'The saved maximum mean contribution remains strictly below 100% ADI under the recorded censoring bounds.',
 'Hosted build identity/formal EFSA endorsement; sampling, assay, dietary transport and total-diet uncertainty.',
 'Dietary modeller and chemical assessor','Retain conditional wording; recheck if engine or authoritative reference changes.',
 'Contrary official input clarification, revised reference value, occurrence or consumption release.')
for ch in ['azoxystrobin','boscalid']:
    r=byratio[ch];i='CENSORING_UNRESOLVED' if ch=='azoxystrobin' else 'ABOVE_UNDER_CENSORING_ONLY'
    record('EU_ORDER_'+ch.upper(),'Is the Czech sampled-lot mean greater than the German sampled-lot mean for this chemical?',
      'tables/same_chemical_ratio_bounds.csv',ch+'; numerator=CZ; denominator=DE; S15, S32',
      f"ratio [{r['ratio_lower']}, {r['ratio_upper']}]; threshold=1; CZ_n=18; DE_n=214",
      'VERIFIED_SAVED_RATIO_BOUNDS','SUPPORTED_FOR_SAMPLED_MEAN_RATIO',i,'SAMPLED_2022_MARKETS_ONLY; NOT_NATIONAL_POPULATION_CONTRAST',
      'The recorded bounds do not determine direction.' if ch=='azoxystrobin' else 'The sampled-mean ratio is above one throughout the recorded censoring interval; no significance claim.',
      'Sampling uncertainty, assay uncertainty and population/supply-chain transport; censoring additionally prevents azoxystrobin ordering.',
      'Occurrence analyst','Resolve compatible censored concentrations for ordering; address sample design before population inference.' if ch=='azoxystrobin' else 'Assess sampling design and uncertainty before any population comparison.',
      'Revised compatible concentration data, sample frame or stated target.')
record('BR_ACETAMIPRID_DENOMINATOR','Can companion documents recover the tested denominator for acetamiprid in PARA 2017-2018 tomato records?',
 'question_rules_v23/brazil_panel_scope_audit.json','Analyte-summary PDF p1 Acetamiprido/Tomate; result PDF pp369-418; programme report p65,p128; preparation pp26,81; historical assessment pp82-83; S14',
 'tested=316; listed detections=36 (24 numeric,12 detected-below-LOQ); unlisted target results=280; report panel=151',
 'VERIFIED_DOCUMENTARY_COUNTS; CHEMICAL_DIETARY_VERIFICATION_NOT_COMPLETED',
 'SUPPORTED_FOR_DENOMINATOR_RECONCILIATION; EXPOSURE_HOLD',
 'TESTED_COUNT_RECOVERED; NO_CONCENTRATION_ANSWER_EVALUATED',
 'SELECTED_DOCUMENTARY_CASE_ONLY; NOT_EXPOSURE_OR_PROGRAMME_PREVALENCE',
 'The companion analyte summary and programme report, linked to the result file, recover 316 tested samples and distinguish the 36 listed detections; the 280 complement is not a materialised sample-level negative matrix.',
 'Source-result linkage for negative membership, chemical expression, preparation and compatible dietary period.',
 'Data steward, chemical assessor and dietary modeller','Confirm remaining field/target requirements before constructing any chronic exposure input.',
 'Authoritative negative-result linkage, risk-definition or dietary evidence.')
r=bypair['azoxystrobin']
record('DE_PRODUCTION_AZOXYSTROBIN','Is the sampled organic-production mean lower than the nonorganic mean for the selected DE 2022 tomato expression?',
 'evidence_extension_v22/paired_concentration_bounds.csv','azoxystrobin|RF-0035-001-PPP; S29; official archive 11043863 / DE2022 member',
 f"organic_n=28; nonorganic_n=186; difference [{r['difference_LB_mg_kg']}, {r['difference_UB_mg_kg']}] mg/kg; threshold=0",
 'VERIFIED_COMPLETE_EXPRESSION_BOUNDS; SOURCE_DECLARED_PRODUCTION_LABELS',
 'SUPPORTED_FOR_SAMPLED_EXPRESSION_BOUNDS','CENSORING_UNRESOLVED','SELECTED_SOURCE_GROUPS_ONLY; NOT_CAUSAL_OR_AS_EATEN_EXPOSURE',
 'The difference interval crosses zero; the recorded limits do not identify production-group ordering.',
 'Sampling uncertainty, group composition/season, certified production and laboratory completeness for historical expression.',
 'Occurrence analyst and source-domain assessor','Improve compatible concentration information; specify/verify the target and sampling design before causal or exposure use.',
 'Revised limits/measurements, production certification, population frame or laboratory expression evidence.')
write_csv(q/'worked_decision_records.csv',records)
(q/'source_chain.json').write_text(json.dumps({'freeze_manifest_sha256':sha(ROOT/'00_admin/analysis_freeze_manifest_20260921.json'),
 'DE_2022_archive':{'official_record':'https://zenodo.org/records/11043863','member_archive':Path(run['source_path']).name,'sha256':run['source_sha256'],'extraction_sha256':run['extraction_sha256']},
 'Brazil_original_PDFs':[{'filename':Path(s['path']).name,'url':s['url'],'sha256':s['sha256']} for s in br_scope['sources']],
 'boundary':'Source-chain locators, not a new assay, hosted-engine or independent assessor validation.'},indent=2))

# Direct panel -> supplied aggregate -> generation code, hash-pinned and unpooled.
panels=[
 ('1A','figure_1_qualification','tables/admission_decision_ledger.csv','262 unit dispositions; not a rate'),
 ('1B','figure_1_qualification','tables/strict_37_ledger.csv','37 residue-definition classes'),
 ('1C','figure_1_qualification','tables/strict_37_ledger.csv','Sample support and quantified fraction within 37'),
 ('2A','figure_2_primo','tables/cell_diagnostics.csv','19 recorded maximum mean/native high-percentile contributions'),
 ('2B','figure_2_primo','tables/same_chemical_ratio_bounds.csv','3 matched-chemical censoring-only ratios'),
 ('2C','figure_2_primo','tables/dietary_strata.csv','88 distinct dietary strata; shared surveys dependent'),
 ('3A','figure_3_disclosure','provenance/disclosure_audit.json','CFIA_2009_2010.screen_results; summaries not analyte-tested matrix'),
 ('3B','figure_3_disclosure','provenance/disclosure_audit.json','TFDA_retail result strings; rows not unique samples'),
 ('3C','figure_3_disclosure','provenance/brazil_two_pair_feasibility.json','316 tested per selected analyte; companion documentary counts'),
 ('4A','figure_4_information','tables/nondetect_limit_distribution.csv','214 complete below-LOQ records per chemical; literal historical filename'),
 ('4B','figure_4_information','tables/nondetect_limit_distribution.csv','Weighted recorded limit bounds; no exposure admission'),
 ('S1A','figure_S1_subsets','tables/robustness_subsets.csv','Retained occurrence-unit count'),
 ('S1B','figure_S1_subsets','tables/robustness_subsets.csv','Largest saved mean UB by descriptive restriction'),
 ('S2A','figure_S2_organic_identification','evidence_extension_v22/paired_concentration_bounds.csv','15 selected production-group means'),
 ('S2B','figure_S2_organic_identification','evidence_extension_v22/paired_concentration_bounds.csv','15 difference intervals; not independent lots'),
 ('S2C','figure_S2_organic_identification','evidence_extension_v22/shared_sample_metadata_balance.csv','Origin composition of 214 shared lots')]
registry=[]
for label,stem,source,interpretation in panels:
    generator='evidence_extension_v22/paired_concentration_figure_v22.py' if label.startswith('S2') else 'reproduction_code/portable_replay_v19.py'
    registry.append(dict(panel=label,figure_svg='figures/'+stem+'.svg',figure_svg_sha256=sha(package/'figures'/(stem+'.svg')),
      aggregate_source=source,aggregate_sha256=sha(package/source),generation_code=generator,generation_sha256=sha(package/generator),interpretation_boundary=interpretation))
write_csv(q/'panel_source_registry.csv',registry)

review=WORK/'review_preparation';shutil.copytree(ROOT/'08_manuscript/framework_revision_v4/review_preparation',review)
manual=(review/'reviewer_manual.md').read_text().replace('version 1, 2026-09-28','version 2, 2026-10-09')
manual=replace(manual,'5. Describe information adequacy using observed diagnostics, without a universal pass threshold or total score. Distinguish censoring from sampling, measurement and processing uncertainty. The historical n>=10 and quantified>=3 selection rule is not a universal requirement; all-nondetect data can be calculable with adequate limits.',
 '5. Specify the question and uncertainty domain before judging information adequacy. For reference exceedance or ordering, apply the recorded-interval answer rules in Supplement S32 and report whether the answer changes within those bounds. Record the actual interval, threshold and outcome, not a universal width cutoff or total score. Other questions require separately justified criteria. Missing/reversed/nonfinite inputs yield HOLD. Do not treat censoring invariance as resolved sampling, measurement, transport or processing uncertainty. Historical support rules are study selection criteria, not universal readiness requirements.')
(review/'reviewer_manual.md').write_text(manual)
form=rows(review/'blank_assessment_form.csv')
if not form:
    header=(review/'blank_assessment_form.csv').read_text().strip()
    (review/'blank_assessment_form.csv').write_text(header+',question_type,uncertainty_domain,interval_lower,interval_upper,question_threshold,interval_answer_state,proposed_responsible_role,review_trigger\n')
else:raise AssertionError('Expected genuinely blank reviewer form')

new_intro='This study examines a European raw-tomato application and selected public-source cases. Its contribution is an inspectable, question-conditioned decision record, not new regulatory requirements. We connect the available evidence to the supported judgement and next information needed, examining reference comparisons, market ordering, dietary timing and documentary recovery.'
new_framework='The framework organises established occurrence, reporting and modelling requirements (EFSA, Arcella et al., 2021; EFSA, 2010; EFSA, 2013). Calculability asks whether compatible inputs support the calculation; inferential applicability specifies the represented food, population and period. For the interval questions tested here, information adequacy asks whether the answer changes within the recorded censoring bounds (Supplementary section S32). Other questions require justified criteria. These separate dimensions are not a score. The retrospective framework was neither used to select the frozen analysis nor independently validated.'
new_questions='We distinguished single-food reference exceedance from same-chemical market ordering. For a reference t, U ≤ t rules out exceedance within the recorded bounds; L > t establishes exceedance; other intervals leave it unresolved. Equality does not establish a strictly lower value. For positive market bounds, the ratio is [L_CZ/U_DE,U_CZ/L_DE]. Bounds wholly above or below 1 determine sampled-mean ordering under censoring; touching or crossing 1 leaves it unresolved. This outer interval assumes no correlation between unknown values. The common positive dietary coefficient and ADI cancel across matched strata. Sampling error is excluded, so ordering is not a significance test. All three shared chemicals were retained, without selecting by result (Supplementary section S32).'
new_pair='The additional German comparison required both source-declared production groups to have at least 20 records with complete numerical limits, strict 2022 MACP tomato eligibility and intersection with the frozen chemical set. Fifteen chemicals met these study-specific criteria; group endpoints reconciled to frozen pooled means (Supplementary section S29).'
new_internal='Expected outcomes were saved before 24 artificial prerequisite cases and nine numerical bound cases were executed. Separate rule implementations and Decimal/rational arithmetic checked decisions and endpoints, including order, identifiers and consistently rescaled units. An additional 23 artificial cases and 20 joint-scale checks tested question-specific interval rules (Supplementary section S32). These are internal software tests, not independent assessor validation. The original USDA cherry-tomato archive was replayed; a prespecified spinach case stopped because the commodity was absent. No alternative was selected.'
supp='''

## S32. Question-conditioned interval decisions and worked records

Information adequacy is specific to a question and an uncertainty domain. For a recorded censoring interval I=[L,U] and a question d, report the possible answers d(x) for x in I. One possible answer is invariant to this recorded censoring uncertainty; multiple answers leave the question unresolved. This is not a universal width score or proof that all uncertainty has been resolved. Successful calculability does not establish target applicability.

For strict reference exceedance x>t, U≤t gives no exceedance within bounds, L>t gives exceedance throughout, and other intervals are unresolved. Equality is not strictly below. For ordering sign(x−t), L>t gives above, U<t gives below, and an interval touching or crossing t is unresolved unless it is the singleton L=U=t. That singleton matches the recorded bounded statistic only, not population equivalence or a null causal effect. Ratios use t=1 and differences t=0. Missing, nonfinite or reversed bounds are held. Known target incompatibility remains held regardless of a numerical answer; the compatibility flag in a software fixture is not independently verified source truth. Other assessment questions require separate, justified criteria.

The local specification and expected answers were saved before implementing and running these added rules. Endpoint comparisons using Decimal and separately coded rational possible-answer enumeration agreed on 23 explicitly artificial fixtures, including reference equality, threshold crossing/touching, point matches, invalid inputs and a known target-incompatibility flag. Twenty finite-input joint positive-scale checks passed. These test implementation and boundary behaviour, not predictive performance, independent source verification or independent assessor agreement. They are a distinct suite from the version-21 tests in S28; counts are not pooled into a validation sample.

Applying the rules to saved results gave 19 no-exceedance answers for the single-food maximum-mean reference question; all empirical upper endpoints were strictly below 100% ADI. Of three within-chemical market ratios, two were above one and one remained unresolved under censoring. All 15 selected production-group difference intervals crossed zero. These are different question families reusing observations; they must not be summed into a readiness denominator or counted as independent studies. Wider bounds can still answer a reference question, while a narrow interval crossing its decision boundary cannot resolve ordering. The rules do not address sampling, assay, processing, dietary-transport or reference-value uncertainty.

Five fully populated retrospective records are supplied as question_rules_v23/worked_decision_records.csv. Each specifies the target, source version, SHA256, row/page locator, recorded values, evidence status, separate calculability/information/applicability outcomes, permitted claim, remaining evidence, proposed responsible role, next action and review trigger. No named independent assessor is implied.

| Worked record | Supported judgement | Remaining boundary |
|---|---|---|
| DE abamectin single-food reference | Saved mean interval remains below 100% ADI under recorded censoring | Historical research adaptation; not total-diet safety or current population exposure |
| CZ/DE azoxystrobin ordering | Ratio 0.44–2.62; direction unresolved | Censoring plus unmodelled sampling and transport |
| CZ/DE boscalid ordering | Ratio 1.45–3.77; above one throughout censoring bounds | No significance or national population claim |
| Brazilian acetamiprid denominator | Tested n=316; 24 numeric and 12 below-LOQ detections | Remaining 280 is an aggregate complement, not a materialised negative-result matrix; exposure held |
| DE azoxystrobin production groups | Difference crosses zero; direction unresolved | Selected source labels, composition/season and laboratory/production verification; no causal coefficient |

The CSV preserves full-precision endpoints; display rounding does not determine decisions. source_chain.json links the derived records to frozen provenance and the official Brazilian/DE source hashes. panel_source_registry.csv links all 16 panels to supplied aggregate inputs and generation scripts by SHA256. The version-2 reviewer manual and expanded blank form remain PREPARED, NOT EXECUTED; worked records are not completed independent-review forms.

Portable check: from the package folder run `python question_rules_v23/question_interval_audit_v23.py --package . --out replay_question_rules_v23` using a new output directory. It reads package-relative paths.yaml, the saved three CSVs and artificial fixture specification, writes question outcomes and a hash-pinned receipt, and executes no new PRIMo/exposure model. These rules formalise judgement for the demonstrated question types; they do not establish a regulatory standard or measured improvement in assessor agreement, efficiency or accuracy.
'''
for key in ['food_control','fac']:
    parent=ROOT/f'08_manuscript/final_{key}_version'
    src=parent/'revision_v22_existing_evidence';dest=parent/'revision_v23_question_decisions'
    shutil.copytree(src,dest)
    main=(src/'manuscript.md').read_text();si=(src/'supplementary_information.md').read_text()
    main=main.replace('Author-review manuscript, revision 22. Existing-data evidence extension;','Author-review manuscript, revision 23. Question-conditioned evidence decisions;')
    main=main.replace('In 15 German production-group comparisons,','In 15 selected German comparisons,')
    def paragraph_after(s,start):return next(p for p in s.split('\n\n') if p.startswith(start))
    for prefix,new in [('This study examines those distinctions',new_intro),('The framework brings together',new_framework),('We examined two different questions:',new_questions),('An additional paired comparison retained',new_pair),('Expected decisions were saved before executing',new_internal)]:
        main=replace(main,paragraph_after(main,prefix),new)
    main=main.replace('all organic-production contrasts remained unresolved under censoring','all 15 selected production-group contrasts remained unresolved under censoring')
    main=main.replace('The proposed record makes those requirements explicit;','The proposed record makes those requirements and question-specific answers explicit;')
    si=replace(si,'Author-review version 20. Four main figures and one supplementary figure (13 panels). Frozen exposure inputs and outputs unchanged; added diagnostics reuse preserved records.',
      'Author-review version 23. Four main figures and two supplementary figures (16 panels). Frozen exposure inputs and outputs unchanged; added diagnostics and question rules reuse preserved records.')
    s7=paragraph_after(si,'The current package includes REPRODUCE.md')
    si=replace(si,s7,'The current package supplies two aggregate replay routes covering six figures (16 panels): reproduction_code/portable_replay_v19.py regenerates the five preserved figures and evidence_extension_v22/paired_concentration_figure_v22.py regenerates Figure S2. The added question_rules_v23 route verifies saved-result decisions and artificial boundary fixtures (S32). No route requires restricted dietary microdata or executes a new exposure model. Full project checks additionally require check_paths.py, the external source store and the 95-file freeze manifest. Public deposition, permissions and author approval remain author actions. The research-adaptation evidence is in S8; no manuscript has been submitted.')
    si=si.replace('| Information adequacy | How strongly do observations constrain it? | Censoring interval, sample support, sensitivity diagnostics | LB/UB represents all uncertainty |',
      '| Information adequacy | Does the answer change within the stated uncertainty domain? | Question, interval, threshold and answer-invariance rule (S32); other questions need justified criteria | Censoring invariance resolves all uncertainty |')
    si=si.replace('All first-run tests passed; no discrepancy was removed through outcome-driven revision.','All first-run tests in the version-21 verification suite passed; no discrepancy was removed through outcome-driven revision.')
    si=replace(si,'This additional diagnostic was selected by intersection of structurally comparable German 2022 MACP tomato candidates with the frozen chemical set. All 15 candidates were retained; there was no selection by concentration contrast.',
      'This diagnostic required source-declared organic and nonorganic groups each with n≥20 and complete numerical reporting limits, strict 2022 DE MACP tomato programme/strategy codes, the resolved complete expression, and intersection with the frozen chemical set. All 15 eligible candidates were retained without selection by concentration contrast. The 16th frozen German chemical, the phosphonic-acid/fosetyl expression, had only 12 organic and 137 nonorganic records and failed the organic n≥20 criterion. This is a study-specific support choice, not a universal minimum or prohibition on converted expressions.')
    s2=paragraph_after(si,'Figure S2. Censoring limits a production-group comparison.')
    si=replace(si,s2,s2+' Panel A and B inputs: evidence_extension_v22/paired_concentration_bounds.csv. Panel C: evidence_extension_v22/shared_sample_metadata_balance.csv. Source: official EFSA archive record 11043863, DE 2022 member; expression and selection gates are documented in S29. All-panel input/code hashes are supplied in question_rules_v23/panel_source_registry.csv.')
    si+=supp
    (dest/'manuscript.md').write_text(main);(dest/'supplementary_information.md').write_text(si)
    title=(src/'title_page.md').read_text().replace('Main tables: 2. Main figures: 4. Supplementary figures: 1.','Main tables: 3. Main figures: 4. Supplementary figures: 2.')
    (dest/'title_page.md').write_text(title)
    cover=(src/'cover_letter.md').read_text().replace('A worked decision table identifies the evidence still needed for broader interpretation.',
      'Five source-linked worked records distinguish an executable calculation from a censoring-invariant answer and identify the remaining evidence.')
    (dest/'cover_letter.md').write_text(cover)
    # Frozen-result tables, figures, references and actual declarations remain unchanged.
    assert main.split('## References')[1]==(src/'manuscript.md').read_text().split('## References')[1]
    assert main.split('## Declarations')[1].split('## References')[0]==(src/'manuscript.md').read_text().split('## Declarations')[1].split('## References')[0]
    for dirname in ['tables','figures']:
        for p in (src/dirname).iterdir():
            if p.is_file():assert sha(p)==sha(dest/dirname/p.name)
    if key=='food_control':
        s1=next(p for p in si.split('\n\n') if p.startswith('**Figure S1.**'))
        legend_parts=[]
        for caption in [s1,next(p for p in si.split('\n\n') if p.startswith('Figure S2.'))]:
            heading,body=caption.replace('**','').split(' (A)',1)
            legend_parts.append('### '+heading+'\n\n(A)'+body)
        (WORK/'supplementary_captions.md').write_text('\n\n'.join(legend_parts)+'\n')
(WORK/'evidence_extension_report.md').write_text('''# Version 23 — question-conditioned scientific decisions

Grilling self-interview adopted three bounded improvements: operational censoring-answer rules, five fully populated source-linked decision records, and complete panel/caption traceability. Added 23 artificial cases and 20 joint positive-scale checks passed; actual question families remain separate (19 reference, 3 market-order, 15 selected production-order). This is internal implementation verification, not independent personnel validation. Explicit n≥20/complete-limit source selection and the 12/137 excluded phosphonic-expression group are now disclosed. Selected15 wording replaces the overbroad organic-contrast conclusion. Missing standalone S1 caption, S2 panel provenance and stale current version/figure metadata are repaired. No new figures, sources, exposure, intervention coefficient or regulatory standard. References, real declarations, frozen 19-result set and all 95 freeze files are preserved. Author confirmations remain pending and red; no submission.
''')
print(json.dumps({'worked_records':len(records),'panel_links':len(registry),'sources':['revision_v23_question_decisions'],'new_exposure':0}))
