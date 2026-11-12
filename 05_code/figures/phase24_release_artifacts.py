#!/usr/bin/env python3
"""Verify canonical approved artwork and recreate the release PDFs and SI.

SVG checks demonstrate artifact fidelity, not independent reconstruction from
PDFs, scientific observations, or original plotting inputs. Six figure PDFs
are copied from the author-supplied inputs and three are rendered from the
canonical SVGs. Outputs are compared with an independently supplied approved
release package. No scientific data or values are computed.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

import cairosvg
import fitz

NAMES = [f"Figure_{i}" for i in range(1, 5)] + [f"Figure_S{i}" for i in range(1, 6)]
RENDERED = {"Figure_1", "Figure_S1", "Figure_S3"}
SI_MANIFEST = "Supplementary_Information_Complete_17pages_NoBoxPanelLegends.pdf"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def approved(path, entry):
    return path.is_file() and path.stat().st_size == entry["bytes"] and digest(path) == entry["sha256"]


def same_pixels(first, second, scale):
    with fitz.open(first) as a, fitz.open(second) as b:
        if len(a) != len(b):
            return []
        result = []
        for left, right in zip(a, b):
            x = left.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            y = right.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            result.append((x.width, x.height, x.n, x.samples) == (y.width, y.height, y.n, y.samples))
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--figures-dir", type=Path, required=True)
    parser.add_argument("--si-complete", type=Path, required=True)
    parser.add_argument("--approved-package-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out
    if out.exists():
        raise FileExistsError(f"Output directory already exists: {out}")
    package = args.approved_package_root
    canonical = Path(__file__).resolve().parent / "phase24_final_svg"
    manifest = json.loads((Path(__file__).resolve().parent / "phase24_panel_legend_manifest.json").read_text())["assets"]
    out.mkdir(parents=True)
    svg_checks, pdf_checks, failures = {}, {}, []
    for name in NAMES:
        source = canonical / f"{name}.svg"
        submitted = package / "02_EDITABLE_SVG" / source.name
        entry = manifest[source.name]
        source_ok = approved(source, entry)
        submitted_ok = approved(submitted, entry)
        if not source_ok or not submitted_ok:
            raise ValueError(f"Canonical or submitted SVG fails approved manifest: {name}")
        target = out / source.name
        shutil.copy2(source, target)
        svg_checks[name] = {
            "canonical_matches_manifest": source_ok,
            "submitted_matches_manifest": submitted_ok,
            "output_matches_manifest": approved(target, entry),
            "output_matches_canonical_and_submitted": digest(target) == digest(source) == digest(submitted),
            "sha256": entry["sha256"], "bytes": entry["bytes"],
        }
        pdf = out / f"{name}.pdf"
        if name in RENDERED:
            cairosvg.svg2pdf(url=str(target), write_to=str(pdf))
        else:
            shutil.copy2(args.figures_dir / pdf.name, pdf)
        expected_dir = "03_OPTIONAL_ONLY" if name.startswith("Figure_S") else "01_UPLOAD_FOR_JOURNAL"
        expected = package / expected_dir / pdf.name
        if not approved(expected, manifest[pdf.name]):
            raise ValueError(f"Submitted PDF fails approved manifest: {name}")
        with fitz.open(pdf) as d:
            pages = len(d)
        pixels = same_pixels(pdf, expected, 2.0)
        passed = pages == 1 and pixels == [True]
        pdf_checks[name] = {"pages": pages, "pixels_identical_2x": passed,
                            "method": "canonical_svg_render" if name in RENDERED else "source_pdf_copy"}
        if not passed:
            failures.append(f"PDF {name}")

    expected_si = package / "01_UPLOAD_FOR_JOURNAL" / "Supplementary_Information_Complete_17pages.pdf"
    if not approved(expected_si, manifest[SI_MANIFEST]):
        raise ValueError("Submitted SI fails approved manifest")
    with fitz.open(args.si_complete) as source_si:
        if len(source_si) != 17:
            raise ValueError("Original SI must contain 17 pages")
        with fitz.open() as result:
            for i in range(17):
                if i in (4, 10):
                    with fitz.open(out / ("Figure_S1.pdf" if i == 4 else "Figure_S3.pdf")) as page:
                        result.insert_pdf(page)
                else:
                    result.insert_pdf(source_si, from_page=i, to_page=i)
            result.save(out / expected_si.name, garbage=4, deflate=True)
    si_pixels = same_pixels(out / expected_si.name, expected_si, 1.5)
    si_ok = len(si_pixels) == 17 and all(si_pixels)
    if not si_ok:
        failures.append("SI page pixels")
    svg_ok = len(svg_checks) == 9 and all(x["output_matches_canonical_and_submitted"] and x["output_matches_manifest"] for x in svg_checks.values())
    pdf_ok = len(pdf_checks) == 9 and all(x["pixels_identical_2x"] for x in pdf_checks.values())
    result = {"validation_scope": "canonical approved artifact fidelity, not independent scientific validation",
              "independent_pdf_to_svg_byte_reproduction": False,
              "all_9_svg_release_artifacts_byte_identical": svg_ok,
              "all_9_pdf_pixels_identical": pdf_ok,
              "all_17_si_page_pixels_identical": si_ok,
              "svg_checks": svg_checks, "pdf_checks": pdf_checks,
              "si_page_pixels_identical_1_5x": si_pixels,
              "scientific_values_recalculated": False,
              "all_checks_pass": svg_ok and pdf_ok and si_ok,
              "failures": failures}
    (out / "phase26_validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("all_9_svg_release_artifacts_byte_identical", "all_9_pdf_pixels_identical", "all_17_si_page_pixels_identical", "independent_pdf_to_svg_byte_reproduction", "all_checks_pass", "failures")}, indent=2))
    if not result["all_checks_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
