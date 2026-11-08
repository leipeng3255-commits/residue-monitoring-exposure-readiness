"""Ten source-semantics panels from frozen, source-reconciled summary tables.

No raw-data changes or new exposure calculation. Run with --data pointing at
the v29 reproducibility payload and --out at a new directory. --config accepts
a relocated paths.yaml; the external drive is not used for plotting inputs.
"""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.text import Text
from matplotlib.ticker import MaxNLocator, PercentFormatter
import numpy as np
from PIL import Image
import yaml


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--config", type=Path)
    args = ap.parse_args()
    config = args.config
    if config is None:
        config = next((p / "00_admin/paths.yaml" for p in [Path.cwd(), *Path(__file__).resolve().parents]
                       if (p / "00_admin/paths.yaml").is_file()), None)
    if config is None:
        ap.error("Provide --config pointing to the project paths.yaml")
    cfg = yaml.safe_load(config.read_text())
    assert (cfg.get("project_root") and cfg.get("data_root")) or cfg.get("mode") == "saved_derived_replay_only"
    assert not args.out.exists(), "Use a fresh output directory; prior renders are preserved."
    args.out.mkdir(parents=True)
    inputs = {}
    plotted = []
    panel_sources = collections.defaultdict(list)

    def read(name, panel, json_file=False):
        path = args.data / name
        inputs[name] = sha(path)
        for letter in panel:
            if name not in panel_sources[letter]:
                panel_sources[letter].append(name)
        if json_file:
            return json.loads(path.read_text())
        return list(csv.DictReader(path.open(encoding="utf-8-sig")))

    def point(panel, series, ident, x, y, weight=1, detail=""):
        plotted.append(dict(panel="3" + panel, series=series, source_id=ident,
                            x=x, y=y, weight=weight, detail=detail))

    sr = "source_reassessment/"
    tr = "source_transport_v28/"
    cols = read(sr + "eat2_whole_and_vegetable_denominators.csv", "ABCD")
    coverage = read(sr + "eat2_group_chemical_coverage.csv", "A")
    thresholds = read(sr + "eati_censor_threshold_distribution.csv", "E")
    examples = read(sr + "eati_source_interval_examples.csv", "F")
    nz = read(sr + "nz_difference_endpoint_counts.csv", "I")
    summary = read(sr + "reassessment_summary.json", "ABCDEF I".replace(" ", ""), True)
    brazil = read(sr + "brazil_two_pair_feasibility.json", "J", True)
    year_states = read(tr + "year_state_counts.csv", "G")
    food_states = read(tr + "food_state_counts.csv", "H")
    transport = read(tr + "source_profile_first_run.json", "GH", True)
    profiles = {year: read(tr + f"year_{year}_profile.json", "G", True) for year in range(2018, 2023)}
    assert len(cols) == 322 and len(examples) == 6

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8,
        "axes.labelsize": 8, "axes.titlesize": 8.5, "xtick.labelsize": 8,
        "ytick.labelsize": 8, "legend.fontsize": 8, "legend.frameon": False,
        "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": .6,
        "svg.fonttype": "none", "pdf.fonttype": 42, "svg.hashsalt": "source-ten-v30",
        "savefig.dpi": 600, "lines.linewidth": 1})
    blue, teal, orange, grey = "#0072B2", "#00856A", "#B84A00", "#737D87"
    fig, grid = plt.subplots(5, 2, figsize=(180 / 25.4, 238 / 25.4))
    axs = grid.ravel()
    fig.subplots_adjust(left=.115, right=.975, bottom=.08, top=.963,
                        wspace=.57, hspace=1.15)
    titles = ["EAT2 analytical coverage", "EAT2 denominator factors",
              "EAT2 scope dependence", "EAT2 quantification support",
              "EATi censoring limits", "EATi record-level envelopes",
              "FDA reporting states", "FDA food-code heterogeneity",
              "NZ recorded brand ordering", "Brazil recovered denominators"]
    for letter, ax, title in zip("ABCDEFGHIJ", axs, titles):
        ax.set_gid("panel_" + letter)
        ax.set_title(letter + "  " + title, loc="left", fontweight="bold", pad=9)
        ax.tick_params(length=2.5, pad=2)

    # A: same 36 x 322 coverage values as v26; no selective removal of food groups.
    colmap = {int(r["chemical_column"]): r for r in cols}
    order = sorted(colmap, key=lambda c: (float(colmap[c]["whole_factor"]), c))
    matrix = np.zeros((36, 322))
    for row in coverage:
        rank, chemical = int(row["group_rank"]), int(row["chemical_column"])
        matrix[rank - 1, chemical - 1] = float(row["tested_fraction"])
        point("A", "tested_fraction", f"group={rank};chemical={chemical}",
              order.index(chemical) + 1, rank, detail=row["tested_fraction"])
    ax = axs[0]
    mesh = ax.pcolormesh(matrix[:, np.array(order) - 1], vmin=0, vmax=1,
                         cmap="cividis", shading="nearest", rasterized=False)
    ax.invert_yaxis()
    ax.set(xlabel="Chemical columns (coverage-ordered)", ylabel="Food-group rank",
           xticks=[0, 160, 321], xticklabels=["1", "161", "322"],
           yticks=[0, 11, 23, 35], yticklabels=["1", "12", "24", "36"])
    cbar = fig.colorbar(mesh, ax=ax, fraction=.038, pad=.04)
    cbar.solids.set_rasterized(False)
    cbar.set_ticks([0, .5, 1], labels=["0%", "50%", "100%"])
    cbar.ax.set_title("Tested", fontsize=8, pad=5)

    # B: defined denominator factors only, not the ratio of zero-valued means.
    ax = axs[1]
    valid = [r for r in cols if r["vegetable_factor"]]
    assert len(valid) == 275
    for rows, field, color, style, label in [
            (cols, "whole_factor", blue, "-", "All foods (322)"),
            (valid, "vegetable_factor", teal, "--", "Vegetables (275)")]:
        data = sorted((float(r[field]), r["chemical_column"]) for r in rows)
        x = [p[0] for p in data]
        y = np.arange(1, len(data) + 1) / len(data)
        ax.step(x, y, where="post", color=color, ls=style, label=label)
        for (value, ident), share in zip(data, y):
            point("B", field, ident, value, share)
    ax.set(xlim=(0, 1.03), ylim=(0, 1.03), xlabel="Tested / all composites",
           ylabel="Cumulative share", xticks=[0, .5, 1], yticks=[0, .5, 1])
    for axis in [ax.xaxis, ax.yaxis]:
        axis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.legend(loc="upper left", bbox_to_anchor=(0, -.48), handlelength=1.4,
              borderaxespad=0, labelspacing=.2)

    # C/D: preserve grouped overplotting; point area reflects repeated coordinates.
    ax = axs[2]
    pairs = collections.Counter((float(r["whole_factor"]), float(r["vegetable_factor"])) for r in valid)
    ax.scatter([p[0] for p in pairs], [p[1] for p in pairs],
               s=[8 + 3 * np.sqrt(n) for n in pairs.values()], color=blue,
               edgecolor="white", linewidth=.3, alpha=.85)
    for (x, y), n in pairs.items():
        point("C", "scope_factors", "coordinate_group", x, y, n)
    ax.plot([0, 1], [0, 1], color=grey, ls="--", lw=.7)
    ax.set(xlim=(-.03, 1.03), ylim=(-.03, 1.03), xlabel="All-food factor",
           ylabel="Vegetable factor", xticks=[0, .5, 1], yticks=[0, .5, 1])
    for axis in [ax.xaxis, ax.yaxis]:
        axis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax = axs[3]
    pairs = collections.Counter((int(r["vegetable_n_tested"]), int(r["vegetable_n_VAL"])) for r in valid)
    ax.scatter([p[0] for p in pairs], [p[1] for p in pairs],
               s=[8 + 3 * np.sqrt(n) for n in pairs.values()], color=teal,
               edgecolor="white", linewidth=.3, alpha=.85)
    for (x, y), n in pairs.items():
        point("D", "tested_vs_quantified", "coordinate_group", x, y, n)
    ax.set(xlabel="Tested vegetable composites", ylabel="Quantified records", xlim=(0, 280))
    ax.set_yscale("symlog", linthresh=1)
    ax.set_xticks([0, 135, 267])
    ax.set_yticks([0, 1, 10, 100], labels=["0", "1", "10", "100"])

    # E/F: conservative envelopes, not estimates of actual concentration or CIs.
    ax = axs[4]
    for status, color, style, label in [("<LD", blue, "-", "<LOD (63,350)"),
                                       ("<LQ", orange, "--", "<LOQ (583)")]:
        rows = sorted([r for r in thresholds if r["type_res"] == status],
                      key=lambda r: float(r["upper_limit_ug_kg"]))
        values = np.array([float(r["upper_limit_ug_kg"]) for r in rows])
        counts = np.array([int(r["records"]) for r in rows])
        cum = np.cumsum(counts) / sum(counts)
        ax.step(values, cum, where="post", color=color, ls=style, label=label)
        for r, x, y in zip(rows, values, cum):
            point("E", status, r["upper_limit_ug_kg"], x, y, int(r["records"]))
    ax.set_xscale("log")
    ax.set(xlabel="Typed upper limit (µg/kg)", ylabel="Cumulative share", ylim=(0, 1.03))
    ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.set_yticks([0, .5, 1])
    ax.legend(loc="upper left", bbox_to_anchor=(0, -.48), handlelength=1.4,
              borderaxespad=0, labelspacing=.2)
    ax = axs[5]
    examples.sort(key=lambda r: ({"<LD": 0, "<LQ": 1, "VAL": 2}[r["type_res"]], int(r["source_row"])))
    for i, row in enumerate(examples):
        lower, upper = float(row["lower_over_lq"]), float(row["upper_over_lq"])
        color = {"<LD": blue, "<LQ": orange, "VAL": teal}[row["type_res"]]
        if row["type_res"] == "VAL":
            ax.plot(lower, i, "o", ms=3.5, color=color)
        else:
            ax.plot([lower, upper], [i, i], color=color)
            ax.plot([lower, upper], [i, i], "|", ms=5, color=color)
        if row["type_res"] == "<LQ":
            ax.plot(float(row["ld"]) / float(row["lq"]), i, "x", ms=3.5, color=grey)
        point("F", row["type_res"], row["source_row"], lower, upper,
              detail="normalized_by_record_LOQ; LOD_marker=" + str(float(row["ld"]) / float(row["lq"])))
    ax.set_yticks(range(6), [r["type_res"] + " r" + r["source_row"] for r in examples])
    ax.invert_yaxis()
    ax.set(xlabel="Concentration envelope / LOQ", xlim=(-.05, 1.95))
    ax.xaxis.set_major_locator(MaxNLocator(3))

    # G: source reporting states. Fiscal-sheet year is not a contamination trend.
    state_lookup = {(int(r["sheet_year"]), r["source_trace_state"]): int(r["rows"]) for r in year_states}
    ax = axs[6]
    year_rows = []
    states = [("Non-Detect = 0", "concentration_zero", blue, "o"),
              ("Detect <LOQ", "value_between_limits", orange, "^"),
              ("Detect ≥LOQ", "value_ge_loq", teal, "s")]
    for i, (year, profile) in enumerate(profiles.items()):
        n = profile["rows"]
        assert profile["concentration_zero"] == state_lookup[(year, "Non-Detect")]
        assert profile["value_between_limits"] + profile["value_ge_loq"] == state_lookup[(year, "Detect")]
        assert n == sum(profile[k] for _, k, _, _ in states)
        for name, key, color, marker in states:
            percent = 100 * profile[key] / n
            ax.scatter(percent, i, color=color, marker=marker, s=20, label=name if i == 0 else None)
            point("G", name, str(year), percent, i, profile[key], f"total_analytical_rows={n}")
            year_rows.append(dict(sheet_year=year, state=name, records=profile[key], total_records=n, percent=percent))
    ax.set_xscale("log")
    ax.set(xlim=(.2, 135), xlabel="Share of analytical rows (%)", ylabel="Fiscal sheet-year",
           yticks=range(5), yticklabels=list(profiles), xticks=[.3, 1, 10, 100],
           xticklabels=["0.3", "1", "10", "100"])
    ax.invert_yaxis()
    ax.legend(loc="upper left", bbox_to_anchor=(-.03, -.49), handlelength=.8,
              handletextpad=.3, borderaxespad=0, labelspacing=.1, ncol=2, columnspacing=.5)

    # H: one point per source food code (not per independent food sample/person).
    grouped = {}
    for row in food_states:
        key = (row["food_code"], row["food_description"], row["food_category"])
        grouped.setdefault(key, collections.Counter())[row["source_trace_state"]] += int(row["rows"])
    assert len(grouped) == 284
    assert len({key[2] for key in grouped}) == 18
    assert sum(sum(s.values()) for s in grouped.values()) == transport["source_rows"] == 1897169
    ax = axs[7]
    food_rows = []
    for (code, desc, category), states_count in sorted(grouped.items()):
        total, detected = sum(states_count.values()), states_count["Detect"]
        percent = 100 * detected / total
        ax.scatter(total, percent, s=11, facecolor=blue, edgecolor="white", linewidth=.25, alpha=.7)
        point("H", "Detect_labelled", code, total, percent, detail=category)
        food_rows.append(dict(food_code=code, food_description=desc, food_category=category,
                              total_records=total, detect_labelled_records=detected, detect_percent=percent))
    ax.set_xscale("log")
    ax.set(xlabel="Analytical rows per food code", ylabel="Detect-labelled rows (%)")
    ax.set_ylim(0, max(r["detect_percent"] for r in food_rows) * 1.08)
    ax.yaxis.set_major_locator(MaxNLocator(3))

    # I: unchanged finite recorded-composite ordering, NOT an effect estimate.
    ax = axs[8]
    nz_totals = {}
    for status, color, marker, label in [
            ("UNRESOLVED_CENSORING", grey, "o", "Unresolved (19,246)"),
            ("BRAND1_ABOVE", blue, "^", "Above (30)"),
            ("BRAND1_BELOW", orange, "v", "Below (31)")]:
        rows = [r for r in nz if r["decision"] == status]
        nz_totals[status] = sum(int(r["record_pairs"]) for r in rows)
        ax.scatter([float(r["difference_LB"]) for r in rows], [float(r["difference_UB"]) for r in rows],
                   s=10, color=color, marker=marker, alpha=.7, linewidths=0, label=label)
        for row in rows:
            point("I", status, "endpoint_coordinate", row["difference_LB"], row["difference_UB"], int(row["record_pairs"]))
    assert nz_totals == {"UNRESOLVED_CENSORING": 19246, "BRAND1_ABOVE": 30, "BRAND1_BELOW": 31}
    ax.set_xscale("symlog", linthresh=.001)
    ax.set_yscale("symlog", linthresh=.001)
    ax.axhline(0, color="black", lw=.5)
    ax.axvline(0, color="black", lw=.5)
    ax.set(xlabel="Lower endpoint (mg/kg)", ylabel="Upper endpoint (mg/kg)",
           xticks=[-1, 0, 1], yticks=[-1, 0, 1])
    ax.set_xticklabels(["−1", "0", "1"])
    ax.set_yticklabels(["−1", "0", "1"])
    ax.legend(loc="upper left", bbox_to_anchor=(0, -.49), handlelength=.6,
              borderaxespad=0, labelspacing=.1, handletextpad=.3, ncol=2, columnspacing=.4)

    # J: tested denominator != a recovered full negative analytical matrix.
    ax = axs[9]
    bars = []
    for name in ["Acefato", "Acetamiprido"]:
        record = brazil["pairs"][name]
        classes = record["reporting_classes"]
        bars.append([classes.get("NUMERIC_REPORTED", 0), classes.get("DETECTED_BELOW_QUANTIFICATION", 0),
                     record["samples_without_listed_target_result"]])
    left = np.zeros(2)
    for j, (color, hatch, name) in enumerate([(blue, None, "Numeric"), (orange, "////", "<LOQ"),
                                             ("#C1C7CD", "..", "Unlisted")]):
        values = [row[j] for row in bars]
        ax.barh([0, 1], values, left=left, color=color, height=.42, label=name,
                edgecolor="white", linewidth=.4, hatch=hatch)
        for i, value in enumerate(values):
            if value >= 40:
                ax.text(left[i] + value / 2, i, str(value), ha="center", va="center",
                        color="white" if j == 0 else "black")
            elif value:
                ax.annotate(str(value), (left[i] + value / 2, i), xytext=(0, 13 if j == 0 else -15),
                            textcoords="offset points", ha="center", fontsize=8,
                            arrowprops={"arrowstyle": "-", "lw": .5})
            point("J", name, ["Acephate", "Acetamiprid"][i], left[i], value)
        left += values
    assert list(left) == [316, 316]
    ax.set_yticks([0, 1], ["Acephate", "Acetamiprid"])
    ax.set(xlim=(0, 330), ylim=(1.55, -.55), xlabel="Tested tomato samples", xticks=[0, 158, 316])
    ax.legend(loc="upper left", bbox_to_anchor=(0, -.49), ncol=2, columnspacing=.6,
              handlelength=1, handletextpad=.3, borderaxespad=0, labelspacing=.1)

    # Validate all painted text on the fixed-size canvas before saving.
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    width, height = fig.canvas.get_width_height()
    ignored = set()
    for ax in fig.axes:
        for axis, limits in [(ax.xaxis, ax.get_xlim()), (ax.yaxis, ax.get_ylim())]:
            lo, hi = sorted(limits)
            for tick in axis.get_major_ticks() + axis.get_minor_ticks():
                if not lo <= tick.get_loc() <= hi:
                    ignored.update([tick.label1, tick.label2])
    painted = [t for t in fig.findobj(match=Text) if t not in ignored and t.get_visible() and t.get_text().strip()]
    clipped = [t.get_text() for t in painted if (lambda bb: bb.x0 < 0 or bb.y0 < 0 or bb.x1 > width or bb.y1 > height)(t.get_window_extent(renderer))]
    assert not clipped, ("Text outside canvas", clipped)
    assert min(t.get_fontsize() for t in painted) >= 8
    for ext in ["svg", "pdf", "png"]:
        metadata = {"Date": None} if ext == "svg" else {"CreationDate": None, "ModDate": None} if ext == "pdf" else None
        fig.savefig(args.out / ("figure_3_disclosure." + ext), facecolor="white", metadata=metadata)
    Image.open(args.out / "figure_3_disclosure.png").convert("RGB").save(
        args.out / "figure_3_disclosure.tiff", compression="tiff_lzw", dpi=(600, 600))
    svg = (args.out / "figure_3_disclosure.svg").read_text()
    assert "<text" in svg and "<image" not in svg
    assert all('id="panel_' + p + '"' in svg for p in "ABCDEFGHIJ")
    for name, rows in [("plotted_values.csv", plotted), ("fda_year_plot_values.csv", year_rows),
                       ("fda_food_plot_values.csv", food_rows)]:
        with (args.out / name).open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    caption = """# Figure 3. Source semantics determine what a numeric field can support

**A–D, French EAT2.** (A) Tested fractions for all 36 source food groups and 322 chemical-expression columns; columns are ordered by whole-food coverage. Food-group rank 1 is vegetables excluding potatoes. (B) Empirical cumulative distributions of tested/all-composite denominator factors for all foods (322 columns) and vegetables (275 tested columns). These factors describe the proportional attenuation of a positive mean endpoint if unanalysed cells were incorrectly filled with zero and included in its denominator; they are not exposure reductions. (C) Matched all-food and vegetable factors. The 47 vegetable columns without an analysed record are held, not assigned a factor. (D) Tested versus quantified vegetable records for the 275 columns. In C and D, coincident coordinates are grouped; marker area is 8 + 3√n points². The vertical scale in D is symmetric-log with a linear segment through 1 record.

**E–F, French EATi.** (E) Weighted empirical cumulative distributions of positive reporting limits attached to 63,350 `<LD` and 583 `<LQ` censored records. All 63,933 concentration blanks are typed censored records, not unanalysed cells. (F) Six source-ordered examples (first two per status), expressed relative to each record's LOQ. Bars denote conservative [0, LOD] or [0, LOQ] envelopes, circles denote reported quantified values, and crosses mark the recorded LOD for `<LQ` records. These are censoring envelopes, not confidence intervals or reconstructed risk-residue expressions.

**G–H, US FDA Total Diet Study, fiscal sheets 2018–2022.** (G) Shares of analytical result rows recorded as numeric-zero Non-Detect, Detect below LOQ, and Detect at/above LOQ. Across 1,897,169 rows, these states comprise 1,880,200, 6,607 and 10,362 rows, respectively. The horizontal share axis is logarithmic. Fiscal-sheet years describe the archived reporting structure; changing sampling and analytical composition precludes a contamination-trend interpretation. (H) Analytical result counts versus Detect-labelled fractions for each of 284 food-code/description pairs across 18 categories. Detect includes results below LOQ and does not mean quantified. Rows, food codes and categories are not independent retail-sample or participant counts; no concentration endpoint or new exposure estimate is inferred.

**I, New Zealand 2024 first quarter.** Endpoint pairs for recorded brand-1 minus brand-2 composite differences. Of 19,422 source rows, 19,307 have usable paired endpoints: 19,246 are censoring-unresolved, 30 above and 31 below; 115 held rows are not plotted. Coordinates are displayed once per unique endpoint/decision combination; legend counts refer to source rows, not visible points. Both axes use symmetric-log scaling with a linear segment of ±0.001 mg/kg. This is finite recorded-composite ordering, not population inference.

**J, Brazil PARA 2017–2018.** For a recovered universe of 316 tomato samples, the listed target results comprise 67 numeric acephate records and 24 numeric plus 12 below-quantification acetamiprid records. The remaining 249 and 280 samples have no listed target result in the recovered output. These unlisted states are not automatically non-detects; a complete negative analytical matrix has not been reconstructed. Panels use different source-specific denominators and are not pooled. No panel adds an exposure calculation.
"""
    (args.out / "caption.md").write_text(caption)
    audit = dict(status="PASS_NUMERIC_AND_CANVAS_CHECKS_VISUAL_REVIEW_REQUIRED",
        panels=["3" + p for p in "ABCDEFGHIJ"], figure_mm=[180, 238], min_font_pt=8,
        code_sha256=sha(Path(__file__)), config_sha256=sha(config), inputs=inputs,
        panel_to_inputs=dict(panel_sources), quantitative_only=True, SVG_raster_images=0,
        editable_text=True, dpi=600, clipped_visible_text=clipped,
        FDA=dict(analytical_rows=1897169, food_code_description_pairs=284, food_categories=18,
                 NonDetect_zero=1880200, Detect_below_LOQ=6607, Detect_ge_LOQ=10362),
        NZ_decisions=nz_totals, new_exposure_units=0,
        boundaries=["No new raw-data analyses", "No population prevalence or contamination trend",
                    "Source-specific denominators are not pooled", "No independent-human validation"],
        outputs={p.name: sha(p) for p in args.out.iterdir() if p.is_file()})
    (args.out / "audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"out": str(args.out), "panels": 10, "status": audit["status"]}))


if __name__ == "__main__":
    main()
