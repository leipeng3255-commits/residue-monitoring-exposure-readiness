#!/usr/bin/env python3
"""
Presentation-only finalization for the Environmental Research submission figures.

Inputs:
  --figure1  original Figure 1 PDF (before Phase 17 legend repair)
  --figure4  original Figure 4 PDF (before Phase 17 Panel E neutral-fill repair)
  --si-docx  current Supplementary Information DOCX containing the current S1-S5 SVG media
  --out      new output directory

This script does not recalculate, simulate, or alter scientific observations.
It adds the source parameter-type key to Figure 1F, replaces the unsupported
quantitative fill encoding in Figure 4E with neutral fills while retaining the
printed cell counts, and extracts the current S1-S5 SVG assets from the SI DOCX.
"""
from __future__ import annotations
import argparse, hashlib, json, zipfile
from pathlib import Path
import fitz
from lxml import etree
import cairosvg

MEDIA = {
    "S1": "word/media/image2.svg",
    "S2": "word/media/image4.svg",
    "S3": "word/media/image6.svg",
    "S4": "word/media/image8.svg",
    "S5": "word/media/image10.svg",
}
PARAMETER_TYPES = [
    (306.0, (0.0, 0.447, 0.698), "P005A"),
    (343.0, (0.835, 0.369, 0.0), "P002A"),
    (380.0, (0.0, 0.62, 0.451), "P004A"),
    (417.0, (0.725, 0.757, 0.788), "N_A"),
]
PANEL_E_COUNTS = [
    ["30", "0", "0", "0"],
    ["1", "30", "0", "0"],
    ["0", "0", "19,246", "0"],
    ["0", "0", "0", "115"],
]

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def repair_figure1(src: Path, dst: Path) -> None:
    doc = fitz.open(src)
    page = doc[0]
    text = page.get_text()
    for required in ("P005A", "P002A", "P004A", "N_A"):
        if required not in text:
            raise ValueError(f"Figure 1 source is missing expected Panel D key: {required}")
    # Remove the earlier two-entry key area and draw the four source categories.
    page.draw_rect(fitz.Rect(303, 386, 456, 397), color=None, fill=(1, 1, 1), overlay=True)
    for x, colour, label in PARAMETER_TYPES:
        page.draw_circle(fitz.Point(x, 392.2), 2.2, color=colour, fill=colour, width=0.35, overlay=True)
        page.insert_text(fitz.Point(x + 4.5, 394.3), label, fontsize=6.2,
                         fontname="helv", color=(0.12, 0.16, 0.20), overlay=True)
    doc.save(dst, garbage=4, deflate=True)
    doc.close()

def repair_figure4(src: Path, dst: Path) -> None:
    doc = fitz.open(src)
    page = doc[0]
    text = page.get_text()
    for required in ("19,246", "115", "Above", "Below", "Unres.", "Held"):
        if required not in text:
            raise ValueError(f"Figure 4 source is missing expected Panel E value/label: {required}")
    # Remove the original cell text and obsolete quantitative scale label from
    # the PDF text layer, while preserving the surrounding vector graphics.
    page.add_redact_annot(fitz.Rect(71.5, 440.1, 219.5, 559.2), fill=(1, 1, 1))
    page.add_redact_annot(fitz.Rect(82, 584, 211, 599), fill=(1, 1, 1))
    page.apply_redactions(images=0, graphics=0, text=0)

    # Panel E 4x4 matrix: retain the printed counts and use one neutral fill.
    x0, y0, x1, y1 = 71.887, 440.453, 219.141, 558.933
    nrows, ncols = 4, 4
    cw, ch = (x1 - x0) / ncols, (y1 - y0) / nrows
    for r in range(nrows):
        for c in range(ncols):
            rect = fitz.Rect(x0 + c*cw, y0 + r*ch, x0 + (c+1)*cw, y0 + (r+1)*ch)
            page.draw_rect(rect, color=(0.73, 0.77, 0.81), fill=(0.93, 0.95, 0.97),
                           width=0.45, overlay=True)
            page.insert_textbox(fitz.Rect(rect.x0+1, rect.y0+8, rect.x1-1, rect.y1-3),
                                PANEL_E_COUNTS[r][c], fontsize=8.0, fontname="hebo",
                                color=(0.12, 0.16, 0.20), align=fitz.TEXT_ALIGN_CENTER,
                                overlay=True)
    # Add the replacement non-quantitative label.
    page.insert_textbox(fitz.Rect(82, 586, 211, 598), "Counts shown; uniform cell fill",
                        fontsize=6.6, fontname="helv", color=(0.12, 0.16, 0.20),
                        align=fitz.TEXT_ALIGN_CENTER, overlay=True)
    doc.save(dst, garbage=4, deflate=True)
    doc.close()

def extract_si_figures(si_docx: Path, out: Path) -> None:
    with zipfile.ZipFile(si_docx) as z:
        for label, member in MEDIA.items():
            root = etree.fromstring(z.read(member))
            # White page background ensures stable display in PDF viewers.
            vb = list(map(float, root.get("viewBox", "0 0 510 720").split()))
            bg = etree.Element("{http://www.w3.org/2000/svg}rect")
            bg.set("x", str(vb[0])); bg.set("y", str(vb[1]))
            bg.set("width", str(vb[2])); bg.set("height", str(vb[3]))
            bg.set("fill", "#FFFFFF")
            insert_at = 0
            while insert_at < len(root) and etree.QName(root[insert_at]).localname == "defs":
                insert_at += 1
            root.insert(insert_at, bg)
            svg = etree.tostring(root, encoding="utf-8", xml_declaration=True)
            (out / f"Figure_{label}.svg").write_bytes(svg)
            cairosvg.svg2pdf(bytestring=svg, write_to=str(out / f"Figure_{label}.pdf"))
            cairosvg.svg2png(bytestring=svg, write_to=str(out / f"Figure_{label}.png"),
                             background_color="#FFFFFF", scale=3.0)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--figure1", required=True, type=Path)
    ap.add_argument("--figure4", required=True, type=Path)
    ap.add_argument("--si-docx", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    repair_figure1(args.figure1, args.out / "Figure_1_Legend_Repaired.pdf")
    repair_figure4(args.figure4, args.out / "Figure_4_Legend_Repaired.pdf")
    extract_si_figures(args.si_docx, args.out)
    manifest = {
        "method": "presentation-only PDF/SVG finalization",
        "source_files": {
            args.figure1.name: sha256(args.figure1),
            args.figure4.name: sha256(args.figure4),
            args.si_docx.name: sha256(args.si_docx),
        },
        "outputs": {p.name: sha256(p) for p in sorted(args.out.iterdir()) if p.is_file()},
        "scientific_data_changed": False,
    }
    (args.out / "phase17_artwork_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

if __name__ == "__main__":
    main()
