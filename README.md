# Residue monitoring and dietary exposure readiness

Code accompanying **Question-specific qualification of pesticide monitoring data for dietary exposure assessment: analytical coverage, censoring and dietary compatibility**.

This repository contains the analysis, checking and figure-generation code for the parent manuscript. The animal-food, plant-trade and network-toxicology projects are separate and are not included.

## What is included

- `05_code/quality_control/`: core admission, PRIMo input and saved-export checks.
- `archived_code/`: versioned scientific scripts from the frozen author package; directory names retain the original revision lineage.
- `verify_saved_results.py`: standalone arithmetic and denominator checks using saved derived tables.
- `CODE_PROVENANCE.json`: original and public-copy SHA256 hashes. Local home/external-drive prefixes were replaced by neutral placeholders; scientific expressions were retained.
- - `05_code/figures/phase17_finalize_submission_artwork.py`: presentation-only finalization of Figure 1F and Figure 4E and extraction of supplementary figures S1–S5.
- `05_code/figures/phase17_artwork_reproducibility.md`: input requirements, execution instructions and validation scope.

## Reproduction levels

The code is public. Raw monitoring files, dietary microdata, authenticated downloads, provider-internal PRIMo consumption objects, correspondence and author declarations are not redistributed here. Input availability and reuse conditions remain those of each official provider. This repository is a code release, not a self-contained raw-to-results dataset.

1. **Saved-result checks** require the derived table directory supplied with the author reproducibility package:

   `python verify_saved_results.py --data /path/to/reproducibility_package`

   This checks the 19-unit/88-stratum saved result structure and the 6,688 reported ADI conversions. It does not recalculate exposure.
2. **Plotting**: scripts in `archived_code/reproduction_code/` consume saved derived summaries. Legacy replay entry points reconstruct historical figure versions; the publication layout is subsequently produced by `archived_code/layout_v42/reflow_svg_panels_v42.py`. The latter requires Inkscape and retains its documented platform-specific executable location. Figure S4 in `replay_figures_v37.py` is copied from an archived plot, not independently recomputed; its source plotting script is supplied separately. The historical revision-38 author package contains eight figures and 43 panels. The current revision-49 manuscript uses nine figures and 44 panels after splitting the former Figure S4 into S4 and S5. The final layout removes the relocated panel subtitles while retaining panel letters, axes and legends. Reproduce this last presentation-only step with `python layout/remove_panel_titles.py --source /path/to/v42_figures --out /path/to/new_output`. Set `INKSCAPE` to your executable when it is not on PATH; the output directory must be new. Geometric elements and all non-subtitle text are checked for preservation.

   **Revision-49 S4/S5:** `05_code/figures/phase54_replot_s4_s5.py` and `phase54_figure_registry.csv` describe the current two-figure layout. After configuring `00_admin/paths.yaml`, run `python 05_code/figures/phase54_replot_s4_s5.py --input-dir /path/to/authorised_saved_tables --out /path/to/new_output`. The five input CSVs are listed in the script and are not redistributed here; their availability and third-party rights remain subject to review. The script reads existing tables and creates no exposure results. Only the script and registry are released; this repository does not itself establish full public reproducibility.

3. **Original-source processing and hosted PRIMo** require the documented external source archives, a configured `00_admin/paths.yaml`, original project directory structure and authorised PRIMo access. Historical scripts are research provenance, not a universal one-command pipeline. Do not run every script in alphabetical order. Copy `paths.example.yaml` to `paths.yaml`, supply actual paths and run `05_code/utilities/check_paths.py` before source processing. Raw data must remain immutable.

## Scientific scope

The current 44-panel provenance index is `05_code/figures/current_44_panel_registry.csv`. It combines the historical v38 source registry for 37 panels with the current S4/S5 source receipts for seven panels. Current SVG hashes are recorded separately from historical source receipts; inclusion does not assert that every panel was independently rerun or that all third-party inputs may be redistributed.

The manuscript evaluates question-specific analytical and dietary compatibility. Censoring intervals are not confidence intervals. Unanalysed records are not non-detections. The saved PRIMo subset is not a global population exposure estimate. Controlled computational cases and simulations, where referenced in historical scripts, are not observations from human assessors. No disease-burden calculation is included in this release.

## Software

The standalone checker uses the Python standard library (Python >=3.10). Historical scientific scripts additionally use NumPy, pandas, matplotlib, Pillow, PyYAML, openpyxl, SciPy, lxml and related source-specific readers. `requirements-observed.txt` records versions installed in the preparation environment, not a claim that every historical script was rerun in that environment. Platform-specific tools and input requirements are described in individual scripts.

## Rights and status

The repository makes the authors' code available for inspection. No additional software licence has been selected; third-party code and data retain their own rights. This release is not a statement of journal submission or acceptance. Please cite the manuscript and the specific repository commit used.

