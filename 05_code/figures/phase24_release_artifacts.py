#!/usr/bin/env python3
"""Release and validate Phase24 canonical SVG artwork and derived PDF/SI outputs.

IMPORTANT PROVENANCE DISTINCTION
--------------------------------
The nine author-approved SVGs are canonical SOURCE ARTWORK, not output claimed
independently regenerated from PDFs. This script preserves those bytes exactly.
The PDFs for Figure 1, S1 and S3 are then rendered from approved SVG source;
unchanged six PDFs retain their original submitted bytes. Complete SI replaces
only original figure pages S1 (5) and S3 (11). Scientific observations are not
recomputed or modified.

The per-figure SVG checksum gate verifies artifact fidelity only, NOT independent
reproduction of PDF -> SVG vector geometry or upstream statistical analyses.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import cairosvg
import fitz

FIGURES = [f"Figure_{i}" for i in range(1, 5)] + [f"Figure_S{i}" for i in range(1, 6)]
MODIFIED = {"Figure_1", "Figure_S1", "Figure_S3"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def compare_pdf_pixels(a: Path, b: Path, zoom: float) -> dict[str, Any]:
    with fitz.open(a) as orig, fitz.open(b) as test:
        if len(orig) != len(test):
            return {"pass": False, "reason": "page-count mismatch", "a": len(orig), "b": len(test)}
        mismatch_pages = []
        for i in range(len(orig)):
            pa = orig[i].get_pixmap(matrix=fitz.Matrix(zoom, zoom), colorspace=fitz.csRGB, alpha=False)
            pb = test[i].get_pixmap(matrix=fitz.Matrix(zoom, zoom), colorspace=fitz.csRGB, alpha=False)
            if (pa.width, pa.height, pa.samples) != (pb.width, pb.height, pb.samples):
                mismatch_pages.append(i+1)
        return {"pass": len(mismatch_pages) == 0, "pages": len(orig),
                "zoom": zoom, "mismatch_pages": mismatch_pages}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--figures-dir", required=True, type=Path,
                        help="Private original one-page Figure_1..S5 PDFs (DO NOT publish)")
    parser.add_argument("--si-complete", required=True, type=Path,
                        help="Private original complete 17-page SI PDF (DO NOT publish)")
    parser.add_argument("--approved-package-root", required=True, type=Path,
                        help="Extracted author-approved Phase25 submission package for verification")
    parser.add_argument("--out", required=True, type=Path,
                        help="New directory for final release artifacts (must not exist)")
    args = parser.parse_args()

    if args.out.exists():
        raise FileExistsError(f"Refusing to overwrite output directory: {args.out}")
    args.out.mkdir(parents=True)

    results: dict[str, Any] = {"provenance": {
        "svg": "Canonical author-approved SVG source copied verbatim; NOT independently reconstructed from PDF",
        "modified_figure_pdfs": "Figure 1, S1 and S3 PDFs rendered from canonical SVG with CairoSVG",
        "other_pdfs": "Six unmodified original PDF source files copied verbatim",
        "si": "Reassembled from 15 original SI pages plus S1/S3 figure PDF replacements",
        "upstream_data_recomputed": False}, "svg_sha256": {}, "pdf_visual": {}, "si_visual": None}

    expected_manifest = json.loads((Path(__file__).with_name("phase24_panel_legend_manifest.json")).read_text(encoding="utf-8"))
    assets = expected_manifest["assets"]
    canonical = Path(__file__).with_name("phase24_final_svg")

    # Verify approved canonical artwork against independently archived approved manifest.
    for name in FIGURES:
        source_svg = canonical / (name + ".svg")
        reference = args.approved_package_root / "02_EDITABLE_SVG" / (name + ".svg")
        if not reference.is_file():
            raise FileNotFoundError(reference)
        approved = assets[name + ".svg"]
        checksum = sha256(source_svg)
        same_as_archive = checksum == sha256(reference)
        valid = (checksum == approved["sha256"] and source_svg.stat().st_size == approved["bytes"] and same_as_archive)
        results["svg_sha256"][name] = {"pass": valid,
            "release_sha256": checksum, "approved_sha256": approved["sha256"],
            "source": "versioned canonical author-approved SVG, not PDF-to-SVG regeneration"}
        if not valid:
            (args.out/"FAILED_VALIDATION.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
            raise RuntimeError(f"Original approved SVG source failed SHA256 and size verification: {name}")
        # Exact bytes retained for public release; does not imply regeneration from PDF.
        shutil.copyfile(source_svg, args.out/(name + ".svg"))

    # Build/copy PDFs. The six unchanged original PDFs have independent signed manifest hashes.
    for name in FIGURES:
        out_pdf = args.out/(name+".pdf")
        source_pdf = args.figures_dir/(name+".pdf")
        if not source_pdf.exists():
            raise FileNotFoundError(source_pdf)
        if name in MODIFIED:
            cairosvg.svg2pdf(url=str(args.out/(name+".svg")), write_to=str(out_pdf))
        else:
            original = assets[name+".pdf"]
            if sha256(source_pdf) != original["sha256"] or source_pdf.stat().st_size != original["bytes"]:
                raise RuntimeError(f"Unmodified input PDF hash != approved submitted PDF: {name}")
            shutil.copyfile(source_pdf, out_pdf)
        approved_pdf = (args.approved_package_root / "01_UPLOAD_FOR_JOURNAL" / (name+".pdf")) if name in {f"Figure_{i}" for i in range(1,5)} else (args.approved_package_root/"03_OPTIONAL_ONLY"/(name+".pdf"))
        comparison = compare_pdf_pixels(approved_pdf, out_pdf, 2.0)
        results["pdf_visual"][name] = comparison

    # SI rebuild and verification.
    with fitz.open(args.si_complete) as old_si:
        if len(old_si) != 17:
            raise ValueError("Expected exactly 17 pages in original SI")
        rebuilt = fitz.open()
        for page_no in range(17):
            if page_no in (4, 10):
                name = "Figure_S1" if page_no == 4 else "Figure_S3"
                with fitz.open(args.out/(name+".pdf")) as piece:
                    rebuilt.insert_pdf(piece)
            else:
                rebuilt.insert_pdf(old_si, from_page=page_no, to_page=page_no)
        si_pdf = args.out/"Supplementary_Information_Complete_17pages.pdf"
        rebuilt.save(si_pdf, garbage=4, deflate=True)
        rebuilt.close()

    si_ref = args.approved_package_root/"01_UPLOAD_FOR_JOURNAL"/"Supplementary_Information_Complete_17pages.pdf"
    results["si_visual"] = compare_pdf_pixels(si_ref, si_pdf, 1.5)
    results["all_9_svg_release_artifacts_byte_identical"] = all(v["pass"] for v in results["svg_sha256"].values())
    results["all_9_pdf_pixels_identical"] = all(v["pass"] for v in results["pdf_visual"].values())
    results["all_17_si_page_pixels_identical"] = bool(results["si_visual"]["pass"])
    results["independent_pdf_to_svg_byte_reproduction"] = False
    results["all_checks_pass"] = (results["all_9_svg_release_artifacts_byte_identical"]
                                   and results["all_9_pdf_pixels_identical"]
                                   and results["all_17_si_page_pixels_identical"])
    results["artifact_sha256"] = {p.name: sha256(p) for p in sorted(args.out.iterdir()) if p.is_file()}
    (args.out/"phase26_validation.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    if not results["all_checks_pass"]:
        print("VALIDATION FAILED. See phase26_validation.json for exact failures.",file=sys.stderr)
        sys.exit(2)
    print("PASS: 9/9 approved SVG archival SHA; 9/9 PDF pixels; 17/17 SI pixels.")
    print("IMPORTANT: SVG source fidelity is NOT independent PDF-to-SVG regeneration.")

if __name__ == "__main__":
    main()
