# Canonical artwork release fidelity

This release archives the nine author-approved final SVG artifacts. The script
checks their SHA256 and size against the approved artwork manifest and against
the SVGs in the author-supplied submission package. It then copies those
canonical SVGs, renders the three changed figure PDFs (Figure 1, S1 and S3),
copies the six remaining PDFs from author-supplied original figure files, and
rebuilds the 17-page supplementary PDF by replacing the two changed pages.

Each output PDF is compared at 2x and each supplementary page at 1.5x against
the approved package using the same PyMuPDF renderer. These checks establish
release-artifact fidelity in the tested environment. They do not independently
reconstruct the nine SVGs from PDFs, original plotting code or scientific data,
validate scientific results, or make the non-redistributed inputs public.

The input figure PDFs, source SI and approved submission package are supplied
separately by the authors. They are not included in this public code release.
The three PDFs rendered from SVG require a compatible CairoSVG/Cairo/font
environment; the observed environment used Arimo as an Arial substitute.

```sh
python 05_code/figures/phase24_release_artifacts.py \
  --figures-dir /path/to/original_figure_pdfs \
  --si-complete /path/to/original_17_page_SI.pdf \
  --approved-package-root /path/to/author_approved_package \
  --out /path/to/new_output_directory
```

The Phase 25 PDF-to-SVG byte-identity experiment was not
reproduced for six figures across tested converter environments. This Phase 26
workflow explicitly does not claim to resolve that independent reconstruction
question. Its validation record was produced by an actual local run.
