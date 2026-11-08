# Residue monitoring and dietary exposure readiness

Code accompanying **Dietary exposure assessment using pesticide monitoring data: analytical coverage, censoring and dietary compatibility**.

This repository contains the analysis, checking and figure-generation code for the parent manuscript. The animal-food, plant-trade and network-toxicology projects are separate and are not included.

## What is included

- `05_code/quality_control/`: core admission, PRIMo input and saved-export checks.
- `archived_code/`: versioned scientific scripts from the frozen author package; directory names retain the original revision lineage.
- `verify_saved_results.py`: standalone arithmetic and denominator checks using saved derived tables.
- `CODE_PROVENANCE.json`: original and public-copy SHA256 hashes. Local home/external-drive prefixes were replaced by neutral placeholders; scientific expressions were retained.

## Reproduction levels

The code is public. Raw monitoring files, dietary microdata, authenticated downloads, provider-internal PRIMo consumption objects, correspondence and author declarations are not redistributed here. Input availability and reuse conditions remain those of each official provider. This repository is a code release, not a self-contained raw-to-results dataset.

1. **Saved-result checks** require the derived table directory supplied with the author reproducibility package:

   `python verify_saved_results.py --data /path/to/reproducibility_package`

   This checks the 19-unit/88-stratum saved result structure and the 6,688 reported ADI conversions. It does not recalculate exposure.
2. **Plotting**: scripts in `archived_code/reproduction_code/` consume saved derived summaries. Legacy replay entry points reconstruct historical figure versions; the publication layout is subsequently produced by `archived_code/layout_v42/reflow_svg_panels_v42.py`. The latter requires Inkscape and retains its documented platform-specific executable location. Figure S4 in `replay_figures_v37.py` is copied from an archived plot, not independently recomputed; its source plotting script is supplied separately. The final author package contains eight figures and 43 panels.
3. **Original-source processing and hosted PRIMo** require the documented external source archives, a configured `00_admin/paths.yaml`, original project directory structure and authorised PRIMo access. Historical scripts are research provenance, not a universal one-command pipeline. Do not run every script in alphabetical order. Copy `paths.example.yaml` to `paths.yaml`, supply actual paths and run `05_code/utilities/check_paths.py` before source processing. Raw data must remain immutable.

## Scientific scope

The manuscript evaluates question-specific analytical and dietary compatibility. Censoring intervals are not confidence intervals. Unanalysed records are not non-detections. The saved PRIMo subset is not a global population exposure estimate. Controlled computational cases and simulations, where referenced in historical scripts, are not observations from human assessors. No disease-burden calculation is included in this release.

## Software

The standalone checker uses the Python standard library (Python >=3.10). Historical scientific scripts additionally use NumPy, pandas, matplotlib, Pillow, PyYAML, openpyxl, SciPy, lxml and related source-specific readers. `requirements-observed.txt` records versions installed in the preparation environment, not a claim that every historical script was rerun in that environment. Platform-specific tools and input requirements are described in individual scripts.

## Rights and status

The repository makes the authors' code available for inspection. No additional software licence has been selected; third-party code and data retain their own rights. This release is not a statement of journal submission or acceptance. Please cite the manuscript and the specific repository commit used.
