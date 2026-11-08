"""Bounded figure-led revision; sealed v29 text and analyses remain untouched."""
import csv,hashlib,json,re
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2]
cfg=yaml.safe_load((ROOT/'00_admin/paths.yaml').read_text())
BASE=ROOT/'10_submission/最终投稿材料_v29_公平比较定稿_文件夹版'
WORK=ROOT/'08_manuscript/figure_upgrade_v30'
sources=WORK/'revised_sources_final';sources.mkdir(exist_ok=False)
audit=json.loads((WORK/'main_figures_reviewed/audit.json').read_text())
captions={r['stem']:r['caption'] for r in audit['figures']}
full3=(WORK/'figure3/final/caption.md').read_text()
short3='(A) Tested fractions across 36 EAT2 food groups and 322 chemical columns. (B) Cumulative tested/all-record factors for all foods and vegetables; incorrectly including unanalysed zeros would attenuate positive mean endpoints by these factors. (C) Matched factors for 275 tested vegetable columns; 47 untested columns remain held. (D) Tested versus quantified vegetable counts. Coincident marks in C–D have area 8 + 3√n points². (E) EATi typed limit distributions. (F) Six source-ordered examples: conservative censoring envelopes, reported quantified points and LOD crosses, relative to LOQ. (G) FDA fiscal-sheet reporting-state shares, not contamination trends. (H) Result counts versus Detect-labelled fractions for 284 food codes; Detect includes below-LOQ results. (I) NZ difference endpoints: 61 directions, 19,246 unresolved comparisons; 115 holds omitted. (J) Brazilian counts per 316 tested samples: numeric, below-LOQ and unlisted results; unlisted complements do not reconstruct a sample-level negative matrix. Denominators are source-specific. Full scales, ordering and policies appear in Supplementary section S39. No panel estimates exposure.'
titles={'figure_1_qualification':'Figure 1. Question-specific qualification of monitoring units.',
 'figure_2_primo':'Figure 2. Saved single-food scenarios, dietary timing and reference sensitivity.',
 'figure_3_disclosure':'Figure 3. Source semantics determine numerical interpretation.',
 'figure_4_comparison':'Figure 4. Same-evidence comparison and controlled omission diagnostics.'}
captions['figure_3_disclosure']=short3
captions['figure_2_primo']=captions['figure_2_primo'].replace('(E) The same','In D, CZ is solid blue and DE dashed orange; E uses blue circles/CZ and orange squares/DE. (E) The same')
captions['figure_4_comparison']=captions['figure_4_comparison'].replace('on a symmetric-log axis','on a symmetric-log axis with a linear region of ±10⁻¹⁰')
maincaps='## Figure legends\n\n'+'\n\n'.join('### '+titles[k]+'\n\n'+captions[k] for k in titles)+'\n'

methods='''## 2. Methods

### 2.1. Study design and assessment targets

This retrospective secondary analysis used immutable, source-linked official data. The European snapshot was frozen on 21 September 2026; framework development and descriptive diagnostics followed. Documentary cases did not enlarge the exposure subset. The estimand was the unweighted arithmetic mean in sampled 2022 EU multiannual coordinated control programme (MACP) raw-tomato lots, by reporting market and chemical. PRIMo applied these means to historical diets. Reporting market, production origin and dietary country remained distinct: cross-country applications were transport scenarios without established supply-chain or population correspondence. Calculability, answer invariance within recorded censoring and inferential applicability were assessed separately, without a score or independent validation (Supplementary section S32).

### 2.2. Evidence qualification and occurrence intervals

Each record specifies a question, evidence status, judgement, boundary and next requirement (Tables 1 and 3). Missing disclosure, incomplete investigator verification and demonstrated incompatibility remain distinct; none alone establishes national deficiency.

The 262-key admission frame comprised 150 tomato and 112 sweet-pepper keys in 13 markets. It intersected an earlier linkage-HOLD set, an archived 2022 food screen and a same-country chronic RPC entry in official PRIMo Annex D.1. Keys excluded year; retrieved 2022–2023 records were subsequently separated by year and programme. The exact reconstruction is supplied in Supplementary section S1. This was not an exhaustive EFSA inventory. Strict eligibility required 2022 raw-tomato K009A/ST10A records, compatible legal references and resolved sample identities (European Commission, 2021). Unknown inclusion probabilities precluded population-weighted pooling; national risk-based records were kept separate.

At least ten tested and three quantified records selected a detected-residue demonstration, yielding 37 strict candidates. These are study-specific criteria, not universal readiness requirements; neither 19/262 nor 19/37 estimates general readiness. The ledger is not a first-failure sequence.

For n analyte-tested records, C_LB = sum(quantified values)/n; C_UB additionally includes each LOQ-coded non-quantified result's limit. Below LOQ is not necessarily undetected. Generic ND/BQL and LOD-only records need separate interpretation. The endpoints bound recorded censoring conditional on measurements and limits, not sampling or all uncertainty.

### 2.3. Chemical expression and food form

Official chemical assessments and reporting-code mappings were checked against declarations and sample identities. The crosswalk separates exact matches, authoritative conversions, mismatches and unresolved cases. Identity checks prevented overlapping abamectin aggregate/component pooling and confirmed disjoint hexythiazox groups (EFSA, Alvarez et al., 2022; EFSA et al., 2019; Supplementary section S34). The complete fosetyl/phosphonic-acid/salt sum expressed as fosetyl received the documented 0.75 expression factor once (EFSA, Bellisai et al., 2021); no unmeasured metabolite was inferred. Exact-only results were retained separately. No unverified processing factor was applied. Raw-RPC-equivalent scenarios are neither prepared-food estimates nor universally conservative bounds.

### 2.4. Monitoring means in PRIMo 4.0.1

Revision-3 guidance supports post-marketing monitoring means (EFSA, Brancato, Brocca, Ferreira et al., 2018). We separately inspected version-4 documentation, archived code and nine synthetic cases (EFSA, Dujardin et al., 2024; Bossier et al., 2024). The function selects numeric RPC_STMR and a supplied definition factor. We used a monitoring mean, not an STMR. The required nonmissing RPC_MRL entry was a labelled nonregulatory routing value; explicit chronic input prevented fallback. No compliance or acute result was interpreted. These checks document a research adaptation, not regulatory endorsement (Supplementary sections S8 and S34).

Paired lower/upper runs were exported from the authenticated application. Saved EFSA references were retained without defaults (EFSA, n.d.): azoxystrobin ADI 0.2 mg/kg body weight/day, with JMPR 2024's 0.03 examined separately (FAO/WHO JMPR, n.d.); pyrimethanil 0.013. All 88 strata and subject counts matched official Annex C, based on submissions through 31 March 2018. Surveys ended in 2000–2012. Explicit EFSA endorsement of this field use and the hosted-build identifier remain unavailable.

### 2.5. Output checks and question-specific diagnostics

Survey/population keys paired saved exports. Checks covered chemical/food identities, ADI units, UB ≥ LB and concentration proportionality; a separate script rechecked 6,688 ADI conversions in 1,672 saved rows. This verifies arithmetic, not assessors or the hosted engine.

For positive dietary coefficient q, E = Cq and %ADI = 100E/ADI. Thus paired mean endpoints share the maximising stratum, apart from ties/precision; saved outputs were checked. Native percentiles were not relabelled P95. For strict exceedance, U ≤ t excludes and L > t establishes exceedance within bounds; otherwise the answer is unresolved. Market ratios use [L_CZ/U_DE, U_CZ/L_DE]. Bounds strictly on one side of 1 establish sampled-mean ordering under censoring; touching 1 does not. This marginal enclosure needs no independence assumption, excludes sampling error and does not assert every apparent reversal attainable. Shared positive q and ADI cancel. All three shared chemicals were retained (Supplementary section S32). Dietary timing, support settings and subset restrictions are descriptive, not optimal thresholds or new exposure scenarios.

### 2.6. Documentary and concentration cases

Canadian/Taiwanese summaries were reconciled without inferring tested panels. Brazilian PARA 2017–2018 results, analyte-specific summaries and the programme report supplied tomato identifiers and two tested denominators. Unlisted result complements remained distinct from reconstructed sample-level negatives. This was retrospective documentary recovery, not prospective performance measurement (Supplementary sections S13–S14 and S34).

Two German all-below-LOQ strata supplied monitored-expression bounds but no new exposure. Mandipropamid's fruit-crop documentary match did not certify historical laboratory coverage; cyazofamid's target expression remained unadjudicated (EFSA, Brancato, Brocca, De Lentdecker et al., 2018; EFSA, Bellisai et al., 2023; Supplementary section S17). The production-label comparison required ≥20 complete records per group, strict 2022 MACP tomato eligibility and frozen-set chemistry; 15 chemicals qualified and reconciled to pooled means (Supplementary section S29). USDA and global audits remain contextual. No organic coefficient, mixture index or disease burden was estimated.

### 2.7. Source semantics and computational challenges

Previously inspected French EAT2/EATi and NZ workbooks were reconciled against official instructions (ANSES, 2014, 2018; Ministry for Primary Industries, 2024). EAT2's deliberately wrong denominator included unanalysed zeros; EATi used typed limits; NZ used difference bounds with methodological holds. A separate XML/rational reader checked counts and arithmetic (Supplementary section S34).

For FDA TDSi 2018–2022, tasks and criteria were locally fixed before full-record analysis; prior header/count/Non-Detect knowledge was disclosed (FDA, n.d.-c). Separate readers checked all five sheets. Official preparation and dietary-linkage descriptions bounded interpretation (FDA, n.d.-a, n.d.-b). This was neither wholly unseen nor publicly preregistered or independently adjudicated (Supplementary section S37).

A same-evidence comparison used separately coded source-aware guidance and framework implementations (EFSA, 2010; EFSA Scientific Committee et al., 2018). We kept 37 saved questions, 11 source examples, 19 paired target challenges and 23 artificial fixtures separate. Diagnostics omitted source qualifiers, demanded point precision or ignored target support. Developer-derived references defined unsupported permissions and unnecessary holds. The comparator was not official software or observed usual practice. Computational replay, source review and controlled cases support implementation consistency, not independent human validation (Supplementary sections S28, S32, S34 and S38).

'''

def renumber(s):
    for old,new in [('Figure S1A and Figure S1B','Figure 2F'),('Figure S1A','Figure 2F'),('Figure S1B','Figure 2F')]:s=s.replace(old,new)
    s=s.replace('Figure S2','Figure TEMP_ORGANIC').replace('Figure S3','Figure S2').replace('Figure TEMP_ORGANIC','Figure S1')
    s=s.replace('Figure 3G','Figure 3I').replace('Figure 3H','Figure 3J')
    return s

for folder in ['01_Food_Control','02_FAC_Part_A_alternative']:
    dest=sources/folder;dest.mkdir()
    old=(BASE/folder/'manuscript.md').read_text();main=renumber(old)
    main=main.replace('revision 29.','revision 30.')
    oldmethods=main.split('## 2. Methods')[1].split('## 3. Results')[0]
    main=main.replace('## 2. Methods'+oldmethods,methods)
    main=main.split('## Figure legends')[0]+maincaps
    main=main.replace('All 37 strict units had numerical reporting limits (Figure 1C),','Sample support varied within the strict subset (Figure 1C). All 37 had numerical reporting limits (Figure 1E),')
    main=main.replace('The admitted subset covered 16 chemical identities in Czechia and Germany.','The admitted subset covered 16 chemical identities in Czechia and Germany; the selected candidate frame was broader (Figure 1D).')
    main=main.replace('The 19 admitted units retained nonzero censoring widths (Supplementary section S16).','The 19 admitted units retained nonzero censoring widths; stricter support settings reduced that subset without establishing better population applicability (Figure 1F).')
    main=main.replace('Subset restrictions changed the displayed maximum (Figure 2F).','For azoxystrobin, saved contributions varied across historical dietary profiles (Figure 2D); replacing the 0.2 ADI with 0.03 rescales the same inputs by 6.67, without changing exposure (Figure 2E). Subset restrictions changed the displayed maximum (Figure 2F).')
    main=main.replace('Two implementations agreed on all annual counts and 524 food–state summaries.','Two implementations agreed on all annual counts and 524 food–state summaries. Figure 3G separates the fiscal-sheet reporting states; Figure 3H shows analytical coverage across 284 food codes, not a population detection prevalence.')
    main=main.replace('No superiority was demonstrated. In the source examples,','Figure 4A displays fair-arm concordance, and Figure 4B locates the artificial intervals relative to their thresholds. No superiority was demonstrated. In the source examples,')
    main=main.replace('These controlled omissions are diagnostic failure mechanisms, not usual-practice error rates (Supplementary section S38).','Unsupported permissions and unnecessary holds are separated by case family (Figure 4C and Figure 4D). These controlled omissions are not usual-practice error rates (Supplementary section S38).')
    (dest/'manuscript.md').write_text(main)
    si=renumber((BASE/folder/'supplementary_information.md').read_text())
    si=si.replace('Author-review revision 29. Three main figures and three supplementary figures, comprising 21 panels.','Author-review revision 30. Four main figures and two supplementary figures, comprising 31 panels.')
    si=si.replace('Figure 2F displays retained unit counts and Figure 2F displays saved maxima.','Figure 2F displays retained unit counts, scenario-row counts and saved maxima together.')
    si=si.replace('all 21 current panels','all 31 current panels')
    si=si.replace('panel_source_registry.csv links all 31 current panels','figure_revision_v30/panel_source_registry.csv links all 31 current panels')
    si=si.replace('Current Figure 3A–G show source coverage, food-scope and censoring diagnostics.','Current Figure 3A–I show source coverage, food-scope, censoring and reporting-state diagnostics.')
    # Replace obsolete current replay paragraph and former subset caption, preserving scientific text elsewhere.
    paras=si.split('\n\n')
    for i,p in enumerate(paras):
        if p.startswith('From the common reproducibility folder, run'):
            paras[i]='From the common reproducibility folder, run `python reproduction_code/replay_figures_v30.py --package . --out NEW_REPLAY_DIRECTORY`. It regenerates Figures 1A–F, 2A–F, 3A–J, 4A–D, S1A–C and S2A–B (31 panels) from supplied derived inputs and rechecks 6,688 saved ADI conversions. No raw data, hosted exposure run or internet access is required. Earlier generators are retained as historical provenance, not the current figure entry point.'
        if p.startswith('**Figure S1.** Composition-sensitive'):
            paras[i]='The former two-panel subset figure is consolidated into current Figure 2F; its retained counts and maxima use the same saved table. Current supplementary Figure S1 is the production-group comparison, and Figure S2 the below-LOQ example.'
    si='\n\n'.join(paras)
    si+='\n\n## S39. Current panel-level audit and extended plotting specification\n\nFour main figures (6, 6, 10 and 4 panels) and two supplementary figures (3 and 2 panels) give 31 panels. Extra views are descriptive reorganisations of saved evidence, not additional independent studies or new exposure runs. The Figure 1E unit order, all source hashes, generators and current panel registry are in figure_revision_v30/. Figure 4 retains six dependent case families, no pooled accuracy and no demonstrated superiority. Its symmetric-log linear region is ±10⁻¹⁰ in the plotted dimensionless coordinates.\n\n'+full3+'\n'
    (dest/'supplementary_information.md').write_text(si)
    oldcaps=renumber((BASE/folder/'figure_captions.md').read_text())
    organic=oldcaps[oldcaps.index('Figure S1. Censoring limits'):oldcaps.index('### Figure S2.')].strip()
    organic=organic.replace('question_rules_v23/panel_source_registry.csv','figure_revision_v30/panel_source_registry.csv')
    below=oldcaps[oldcaps.index('### Figure S2.'):].strip()
    (dest/'figure_captions.md').write_text(maincaps+'\n\n### '+organic+'\n\n'+below+'\n')
    for name in ['title_page','cover_letter','highlights']:
        t=(BASE/folder/(name+'.md')).read_text()
        t=re.sub(r'\n\nWord count excluding references[^\n]+\n?','\n',t)
        t=t.replace('revision 29','revision 30').replace('three main and three supplementary','four main and two supplementary')
        t=t.replace('Main figures: 3. Supplementary figures: 3. Current panels: 21.','Main figures: 4. Supplementary figures: 2. Current panels: 31.')
        (dest/(name+'.md')).write_text(t)
    # Every current panel must be explicitly discussed, not merely exist in an image.
    expected=[f'{n}{c}' for n,letters in [('1','ABCDEF'),('2','ABCDEF'),('3','ABCDEFGHIJ'),('4','ABCD'),('S1','ABC'),('S2','AB')] for c in letters]
    for token in expected:assert 'Figure '+token in main+si,token
    assert main.split('## References')[1].split('## Main tables')[0]==old.split('## References')[1].split('## Main tables')[0]

(WORK/'revision_tracking.md').write_text('''# v30 targeted visual revision

- User-approved structure: 6 + 6 + 10 + 4 main panels, 3 + 2 supplementary panels; no arbitrary 12-panel quota.
- Figure 1D–F: candidate-frame composition, question-conditioned evidence matrix and saved support sensitivity.
- Figure 2D–F: historical diet-profile distributions, saved ADI sensitivity and consolidated subset diagnostics.
- Figure 3G–H: FDA reporting-state composition and food-code analytical coverage; old NZ/Brazil G/H become I/J.
- Figure 4A–D: fair-arm decisions, artificial interval geometry, unsupported permissions and unnecessary withholding. No superiority claim.
- Old supplementary subsets consolidated into Figure 2F. Organic S2 becomes S1; below-LOQ S3 becomes S2.
- Current Methods condensed, not expanded to claim new experiments. Full scientific detail remains in the unchanged source evidence, SI and sealed prior version. References and declarations retained.
- academic-plotting and the revision-mode academic-paper workflow informed quantitative panel selection, readable vector output and source–panel–text checks. No image generation, new exposure model, burden calculation or submission.
''')
print(sources)
