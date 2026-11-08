"""Versioned manuscript integration; no change to analytical tables or figures."""
import csv,hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'08_manuscript/verification_extension_v21'
AUDIT=ROOT/'00_admin/verification_extension_v21'
if WORK.exists(): assert '--refresh-owned' in sys.argv
else: WORK.mkdir()
shutil.copytree(ROOT/'08_manuscript/language_polish_v20/reviews',WORK/'reviews',dirs_exist_ok=True)
shutil.copy2(ROOT/'08_manuscript/language_polish_v20/calculation_validation.json',WORK/'calculation_validation.json')
shutil.copy2(AUDIT/'verification_report.md',WORK/'verification_report.md')
methods='''### 2.8. Computational replay and controlled verification

A separately written reader compared the 38 original Excel exports with the paired result table and recalculated percent ADI using decimal arithmetic. Understated worksheet-dimension metadata were ignored when reading populated cells; workbooks were not edited. Agreement tolerances were the larger of absolute 1e-12 and relative 1e-10. Four decision-bearing claim groups were checked against official documentation, with source-specific limits retained (Supplementary section S28).

Expected decisions were saved before executing 24 artificial rule cases and nine numerical bound cases. Separate prerequisite and dimension implementations tested rule decisions; Decimal and exact rational implementations tested numerical endpoints. Order, identifier and consistently rescaled unit checks examined invariance. These were internal software tests, not independent assessor validation. The existing USDA cherry-tomato case was replayed from its original archive. A new spinach application specified before catalogue inspection was stopped because that commodity was absent from the 2024 programme; no alternative was selected.

'''
results='''
Direct replay of 38 native exports reconciled 3,344 bound-specific records and 13,376 numerical values with the paired table; 6,688 percent-ADI recalculations passed. All 24 artificial rule cases, nine numerical cases and 71 invariance checks matched their specified outcomes. The USDA replay confirmed unequal analyte panels and 201 unrecorded sample–analyte combinations, not non-detections. The planned spinach case was unavailable, so no new-commodity transferability result was obtained. These checks added no exposure unit (Supplementary section S28).

'''
si='''
## S28. Computational replay, primary-source checks and controlled cases

The dated verification specification and expected artificial outcomes were saved before executing the tests. The specification is local, not externally registered. First-run receipts, case definitions and scripts accompany the package in `verification_extension/`. A fresh replay uses a new `--out` directory; existing receipts are not overwritten. The full native-export and PDP replay requires the project paths configuration and official archives on the external drive.

| Check | Distinct denominator | Result | What remains untested |
|---|---|---|---|
| Frozen-file integrity | 95 files | 95 matching SHA256 values | Scientific validity is not inferred from hashes |
| Original Excel replay | 38 exports / 3,344 bound-specific records | 13,376 numerical comparisons matched | Hosted-engine reconstruction and independent assay validation |
| Decimal percent-ADI replay | 6,688 arithmetic operations | All matched within specified rounding tolerance | New exposure or population estimates |
| Artificial rule cases | 24 fixtures | Both implementations matched decisions and reasons | Human assessor agreement or real-programme accuracy |
| Artificial numerical cases | 9 fixtures | Decimal and rational endpoints/holds matched | Assay performance or empirical concentration distributions |
| Invariance checks | 71 transformations of the rule fixtures | All retained decisions/reasons | A sample of 71 independent studies |
| Existing PDP case replay | 529 samples / 178,601 rows / 338 codes | Counts and structural checks matched | Risk-definition and dietary admission |
| New spinach application | Official 2024 commodity catalogue | Absent; application stopped | New-commodity generalisability |

The 24 fixtures distinguish a monitored concentration, a single-food reference-value scenario and an intended population claim. Missing ADI blocks the reference-value scenario tested here; it does not universally prevent calculating absolute dietary intake. Valid all-below-LOQ and explicitly historical targets are retained. A documented conversion does not rescue an incomplete chemical expression. The nine numerical fixtures exercise heterogeneous censoring limits, mixed concentration units, expression conversion, incomplete denominators, repeated keys, absent limits and compliance labels. They are disclosed artificial inputs, not replacements for unavailable scientific observations.

The source ledger checks monitoring means against EFSA 2018 Table 2, the equivalent-expression factor against EFSA 2021 footnote 12, and censoring principles against EFSA 2010. Embedded USDA 2024 dictionaries retain ND/NP/O meanings and numerical LOD units. The official 2024 report, Table 4, records washing and draining cherry tomatoes without peeling. Its analytical-quality section distinguishes LOD and LOQ. Current 2025 SOP language is supplementary context, not assumed to certify every 2024 limit. A revision-3 post-marketing method remains different from explicit revision-4.0.1 field endorsement.

The native Excel files declared insufficient worksheet dimensions. Resetting the read-only parser's dimensions exposed their actual cells, without changing any workbook. All exports reconciled by country, survey and population-group keys, subject counts, ADI units and native percentile labels. Numerical tolerance was max(1e-12 absolute, 1e-10 relative). Original-export values, not just CSV values, entered the Decimal check. The 19 monitoring means were not newly reconstructed from the complete source SSD2 archive in this extension; existing sample-level audits retain that provenance.

The PDP replay retained 168,987 ND, 7,890 NP and 1,724 O records. Panels ranged from 335 to 338 analytes per sample, with 473–529 tested samples per analyte. The 201 absent combinations were not filled with zeros. No duplicate sample–analyte keys, orphans or invalid/nonpositive reported LODs were found. Archive hashes before and after matched. This is replay of a previously inspected second programme, not a blinded external validation. The planned spinach case's absence is recorded rather than replaced with a favourable alternative.

All first-run tests passed; no discrepancy was removed through outcome-driven revision. Shared AI-assisted development can still produce correlated omissions. These checks establish archived-result fidelity and disclosed implementation behaviour, not independent personnel, predictive performance or superiority over usual assessment practice.
'''
checks=[]
for key in ['food_control','fac']:
    old=ROOT/f'08_manuscript/final_{key}_version/revision_v20_language_polish'
    new=old.parent/'revision_v21_verification'
    if not new.exists(): shutil.copytree(old,new)
    original=(old/'manuscript.md').read_text()
    limitation='Internal replay and artificial-case checks support traceability and implementation consistency, but do not address assessor reproducibility or programme-level transferability. '
    legacy=original.replace('## 3. Results\n',methods+'## 3. Results\n',1).replace('## 4. Discussion\n',results+'## 4. Discussion\n',1).replace("The study's main limitations are",limitation+"The study's main limitations are",1)
    main=original.replace('revision 20. Journal-language revision','revision 21. Verification extension')
    result_heading='## 3. Results\n' if key=='food_control' else '## Results\n'
    discussion_heading='## 4. Discussion\n' if key=='food_control' else '## Discussion\n'
    assert result_heading in main and discussion_heading in main
    main=main.replace(result_heading,(methods if key=='food_control' else methods.replace('### 2.8.','###'))+result_heading,1)
    main=main.replace(discussion_heading,results+discussion_heading,1)
    main=main.replace("The study's main limitations are",limitation+"The study's main limitations are",1)
    if '--refresh-owned' in sys.argv: assert (new/'manuscript.md').read_text() in [legacy,main], 'Unexpected source edit'
    (new/'manuscript.md').write_text(main)
    (new/'supplementary_information.md').write_text((old/'supplementary_information.md').read_text()+si)
    for directory in ['tables','figures']:
        for p in (old/directory).iterdir():
            if p.is_file():
                a=hashlib.sha256(p.read_bytes()).hexdigest();b=hashlib.sha256((new/directory/p.name).read_bytes()).hexdigest()
                assert a==b;checks.append({'journal':key,'path':directory+'/'+p.name,'sha256':a,'unchanged':True})
    assert main.split('## References')[1] == (old/'manuscript.md').read_text().split('## References')[1]
    assert main.split('## Declarations')[1].split('## References')[0] == (old/'manuscript.md').read_text().split('## Declarations')[1].split('## References')[0]
    mainwords=len((main.split('## References')[0]+main.split('## Main tables')[1]).split())
    print(key,'words excluding references incl tables/captions',mainwords)
(WORK/'preservation_checks.json').write_text(json.dumps(checks,indent=2))
