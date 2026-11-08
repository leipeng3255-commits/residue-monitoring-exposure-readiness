"""Build the 39-panel v36 source registry without touching frozen v35 files."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
V35_PACKAGE = ROOT / "10_submission/最终投稿材料_v35_来源稳定性补强_文件夹/03_可复现数据与代码_NOT_DIRECT_UPLOAD"
V35_REGISTRY = V35_PACKAGE / "source_stability_v35/panel_source_registry.csv"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_output_root() -> Path:
    text = (ROOT / "00_admin/paths.yaml").read_text()
    match = re.search(r'^outputs_root:\s*"([^"]+)"\s*$', text, flags=re.MULTILINE)
    assert match, "outputs_root missing from paths.yaml"
    return Path(match.group(1))


def encoded(paths: list[str]) -> str:
    return json.dumps(paths, ensure_ascii=False)


def main() -> None:
    outputs = load_output_root() / "manuscript_grilling_v36"
    figure4 = outputs / "source_stability/figure_4_source_stability.svg"
    figure_s4 = outputs / "external_source_challenge/external_source_challenge.svg"
    cutpoints = outputs / "pdp_threshold/cutpoint_profile.csv"
    field_matrix = outputs / "external_source_challenge/source_field_availability_matrix.csv"
    arithmetic = outputs / "external_source_challenge/official_table_arithmetic_checks.csv"
    figure4_code = ROOT / "05_code/figures/source_stability_panels_v36.py"
    figure_s4_code = ROOT / "05_code/analysis/external_source_challenge_v36.py"
    eligible = V35_PACKAGE / "source_stability_v35/pdp/eligible_comparisons.csv"

    with V35_REGISTRY.open(newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        fields = reader.fieldnames
    assert fields and len(rows) == 37
    assert [row["panel"] for row in rows if row["panel"].startswith("4")] == [f"4{x}" for x in "ABCDEF"]
    for row in rows:
        assert sha(V35_PACKAGE / row["figure_svg"]) == row["figure_svg_sha256"], row["panel"]

    # The first 31 panel rows remain bound to the frozen v35 production figures.
    for row in rows:
        if row["panel"].startswith("4"):
            row["figure_svg"] = "figures/figure_4_source_stability.svg"
            row["figure_svg_sha256"] = sha(figure4)
            row["generation_code"] = "reproduction_code/source_stability_panels_v36.py"
            row["generation_sha256"] = sha(figure4_code)
            row["boundary"] = (
                "Source-conditional reporting and repeated-container sensitivity; "
                "no new exposure or independent validation."
            )
    panel_4d = next(row for row in rows if row["panel"] == "4D")
    panel_4d["aggregate_sources"] = encoded([
        "source_stability_v35/pdp/eligible_comparisons.csv",
        "grilling_v36/pdp_threshold/cutpoint_profile.csv",
    ])
    panel_4d["aggregate_sha256"] = encoded([sha(eligible), sha(cutpoints)])
    panel_4d["boundary"] = (
        "Post hoc exact event-cutpoint diagnostic on partial tested frames; "
        "no confidence interval, p-value, temporal trend or exposure claim."
    )

    shared_s4 = {
        "figure_svg": "figures/figure_S4_external_source_challenge.svg",
        "figure_svg_sha256": sha(figure_s4),
        "generation_code": "reproduction_code/external_source_challenge_v36.py",
        "generation_sha256": sha(figure_s4_code),
    }
    rows.extend([
        {
            "panel": "S4A",
            **shared_s4,
            "aggregate_sources": encoded(["grilling_v36/external_source_challenge/source_field_availability_matrix.csv"]),
            "aggregate_sha256": encoded([sha(field_matrix)]),
            "boundary": (
                "Categorical public-field availability, not a score or exposure-readiness estimate; "
                "no new exposure unit."
            ),
        },
        {
            "panel": "S4B",
            **shared_s4,
            "aggregate_sources": encoded(["grilling_v36/external_source_challenge/official_table_arithmetic_checks.csv"]),
            "aggregate_sha256": encoded([sha(arithmetic)]),
            "boundary": (
                "Printed official value is preserved; 130 is an independent arithmetic reconstruction, "
                "not an official correction or exposure estimate."
            ),
        },
    ])

    assert len(rows) == 39 and len({row["panel"] for row in rows}) == 39
    assert all(len(row["figure_svg_sha256"]) == 64 for row in rows)
    out = HERE / "panel_source_registry.csv"
    with out.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({
        "registry": str(out),
        "panels": len(rows),
        "figure_4_sha256": sha(figure4),
        "figure_S4_sha256": sha(figure_s4),
        "registry_sha256": sha(out),
    }, indent=2))


if __name__ == "__main__":
    main()
