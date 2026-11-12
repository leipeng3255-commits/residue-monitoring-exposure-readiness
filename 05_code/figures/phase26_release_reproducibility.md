# Environmental Research — Phase 26 final-artwork provenance

This is a correction to the Phase 25 PDF-to-SVG *byte-reproducibility* claim, not a change to the manuscript's scientific analysis.

## What has been established

- The nine author-approved editable SVGs are archived as **canonical source artwork** in `phase24_final_svg/`. Their original SHA-256 hashes are checked against the Phase 25 approved-artwork manifest and the exact files in the author-approved submission archive.
- The Phase 26 release script copies these nine SVGs **verbatim**. Passing 9/9 SVG SHA256 proves **artifact/source preservation**, *not independent PDF-to-SVG regeneration*.
- PDF pages for Figures 1, S1 and S3 are rendered from the canonical SVGs with CairoSVG. The other six figures' approved PDFs are preserved unchanged.
- The 17-page SI PDF replaces only figure pages 5 and 11 (Figures S1 and S3) and keeps the other 15 original pages.
- The artifact release step does not reconstruct the original statistical plots from raw monitoring data; this is a presentation/release workflow. Scientific scripts are separately archived in the repository.

## Why the Phase 25 independent SVG gate failed

The original code used `pdftocairo -svg` for six unchanged figures. Poppler/Cairo version differences changed SVG path/definition structure even in cases where the final PDFs rendered pixel-identically. A requirement to produce the same SVG bytes by *re-exporting a PDF* is different from a requirement to preserve the approved SVG artwork. The original reproducibility claim overstated the scope.

## Verifiable commands

Place the original one-page PDFs (Figure_1–4 and Figure_S1–S5), the pre-update 17-page SI, and the author-approved Phase 25 package in private/local directories. Never upload the private input bundle to the public repository.

```bash
python 05_code/figures/phase24_release_artifacts.py \
  --figures-dir /absolute/private/path/07_AUTHOR_ONLY_REPRO_INPUTS \
  --si-complete /absolute/private/path/07_AUTHOR_ONLY_REPRO_INPUTS/Supplementary_Information_Complete_v53_17pages.pdf \
  --approved-package-root /absolute/private/path/extracted_Phase25_package \
  --out /absolute/private/path/new_validation_run
```

The output directory must not exist. The script compares every canonical SVG SHA256 with the approved manuscript archive, checks nine PDF figures for identical pixels at 2x and all 17 SI pages at 1.5x. A nonzero exit status means **do not commit**. `phase26_validation.json` stores the exact results and provenance classification.

## Current local verification

The validation performed on the author-approved archive in the preparation container returned:
- 9/9 canonical SVG bytes preserved, SHA256 and size matched;
- 9/9 figure PDF pages pixel-identical at 2x;
- 17/17 SI pages pixel-identical at 1.5x.

**Independent PDF-to-SVG byte reconstruction was not established.** That statement remains false in the validation JSON by design. No raw monitoring data or scientific observations were recalculated or modified.

## Repository modification scope

Upload this script, approved manifest, validation record, observed requirements and the nine canonical SVG sources. Preserve the prior Phase17/Phase54 scripts, `CODE_PROVENANCE.json`, current figure registries, and all historical source files. Update the root README by adding only two accurate pointers; do not rewrite it wholesale.
