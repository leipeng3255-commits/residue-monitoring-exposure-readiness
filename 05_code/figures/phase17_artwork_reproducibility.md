# Phase 17 artwork reproducibility

This folder contains the presentation-only script used to finalize the manuscript's main and supplementary figures.

## Purpose

- Add the four source parameter-type labels to Figure 1F: P005A, P002A, P004A and N_A.
- Replace the unsupported quantitative cell-fill encoding in Figure 4E with a uniform neutral fill while retaining the exact printed counts.
- Extract the current supplementary vector artwork S1–S5 from the author-supplied SI DOCX and render PDF/SVG/PNG outputs.

The script does not recalculate exposure, modify source monitoring observations, or generate synthetic scientific results.

## Required input files

The script requires three author-controlled source files:

1. The original, pre-repair Figure 1 PDF.
2. The original, pre-repair Figure 4 PDF.
3. The current Supplementary Information DOCX containing the source SVG media for S1–S5.

These input files are not redistributed in this public code folder. Their file names and SHA-256 checksums are recorded in `phase17_artwork_manifest.json`; the manifest deliberately omits local absolute paths.

## Environment

The preparation environment used the versions recorded in `requirements-phase17-artwork-observed.txt`. These are observed versions for this presentation-only workflow, not a claim that all historical scientific analyses used the same environment.

## Example command

```bash
python phase17_finalize_submission_artwork.py \
  --figure1 /path/to/original_Figure_1.pdf \
  --figure4 /path/to/original_Figure_4.pdf \
  --si-docx /path/to/current_Supplementary_Information.docx \
  --out /path/to/new_output_directory
```

The output directory must not already exist. The script writes repaired Figure 1 and Figure 4 PDFs, five supplementary SVG/PDF/PNG outputs, and a SHA-256 manifest.

## Validation

`phase17_artwork_validation.json` records the successful validation performed on the author-controlled input files:
- all four Figure 1F parameter-type labels are present;
- the obsolete Figure 4E quantitative colour-scale label is absent;
- the printed Figure 4E counts 19,246 and 115 each occur once in the PDF text layer;
- S1–S5 each render as one-page vector PDFs;
- no scientific observations were recalculated or changed.

The validation record describes the tested source files; it does not guarantee that arbitrary replacement inputs will produce identical output hashes.
