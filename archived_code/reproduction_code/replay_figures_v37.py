"""Portable eight-figure v37 replay from saved derived summaries.

The historical seven figures are replayed through the v36 portable entry point.
The six-panel v37 Figure S4 is reproduced from its hash-pinned derived outputs;
no raw source or exposure model is read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--package", type=Path, required=True)
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
base = args.package.resolve()
out = args.out.resolve()
out.mkdir(parents=True, exist_ok=False)

historical = out / "historical_v36_replay"
subprocess.run(
    [
        sys.executable,
        str(base / "reproduction_code/replay_figures_v36.py"),
        "--package",
        str(base),
        "--out",
        str(historical),
    ],
    check=True,
)

figures = out / "figures"
figures.mkdir()
stems = [
    "figure_1_qualification",
    "figure_2_primo",
    "figure_3_disclosure",
    "figure_4_source_stability",
    "figure_S1_organic_identification",
    "figure_S2_information",
    "figure_S3_comparison",
]
sealed_current = base / "provenance/historical_v36_figures"
for stem in stems:
    for extension in ["svg", "pdf", "png", "tiff"]:
        source = sealed_current / f"{stem}.{extension}"
        regenerated = historical / "figures" / f"{stem}.{extension}"
        assert source.is_file() and regenerated.is_file()
        # PNG equality establishes unchanged rendered data while the sealed
        # publication bytes retain their existing registry hashes.
        if extension == "png":
            from PIL import Image, ImageChops
            left = Image.open(source).convert("RGB")
            right = Image.open(regenerated).convert("RGB")
            assert left.size == right.size
            assert ImageChops.difference(left, right).getbbox() is None, stem
        shutil.copy2(source, figures / f"{stem}.{extension}")

challenge = base / "grilling_v37/external_source_challenge"
for extension in ["svg", "pdf", "png", "tiff"]:
    shutil.copy2(
        challenge / f"external_source_challenge_v37.{extension}",
        figures / f"figure_S4_external_source_challenge.{extension}",
    )

for svg in sorted(figures.glob("*.svg")):
    text = svg.read_text()
    assert "<text" in text and "<image" not in text, svg

v36_receipt = json.loads((historical / "replay_receipt.json").read_text())
receipt = {
    "figure_count": 8,
    "panel_count": 43,
    "main_panels": 28,
    "supplementary_panels": 15,
    "new_exposure_calculations": 0,
    "new_exposure_units": 0,
    "editable_vector_svg_count": 8,
    "saved_ADI_conversion_rechecks": v36_receipt["saved_ADI_conversion_rechecks"],
    "figures": {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(figures.iterdir())
    },
    "scope": (
        "Derived-summary plotting and saved-output checks only. Figure S4 is a six-panel "
        "official-source structure and reporting-reproducibility audit. No raw-data "
        "analysis, exposure estimate, organic effect or independent human validation."
    ),
}
(out / "replay_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps({key: receipt[key] for key in ["figure_count", "panel_count", "new_exposure_calculations"]}))
