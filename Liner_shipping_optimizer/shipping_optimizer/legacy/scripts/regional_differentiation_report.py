"""
Regional Influence Verification — Phase F5.

Runs the full regional policy pipeline across all 5 regions and
measures differentiation. Produces REGIONAL_DIFFERENTIATION_REPORT.md.

Metrics measured
----------------
- Policy uniqueness score: fraction of region pairs with at least one
  differing field in their policy.
- Region-to-region distance: pairwise Euclidean distance over
  (coverage, profit, margin, vessel_code).
- Distinct vessel biases: number of unique vessel_bias values.
- Distinct corridor strategies: number of unique (coverage, profit) pairs.
- Distinct hub strategies: number of unique hub_focus sets.

Run:  python scripts/regional_differentiation_report.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.regional_intelligence_audit import load_problem_from_json
from src.decomposition.port_clustering import PortClustering
from src.decomposition.regional_splitter import RegionalSplitter
from src.agents.regional_metrics import STANDARD_REGION_NAMES
from src.agents.regional_policy_mapping import derive_all_regional_policies


VESSEL_CODE = {"small": 0.0, "balanced": 0.5, "large": 1.0, "feeder": -1.0}


def policy_distance(p1: dict, p2: dict) -> float:
    """Euclidean distance over the 4 main policy dimensions."""
    cov_d = p1["coverage_priority"]  - p2["coverage_priority"]
    prof_d = p1["profit_priority"]   - p2["profit_priority"]
    mar_d = p1["min_service_margin"] - p2["min_service_margin"]
    v1 = VESSEL_CODE.get(p1["vessel_bias"], 0.5)
    v2 = VESSEL_CODE.get(p2["vessel_bias"], 0.5)
    v_d = v1 - v2
    return (cov_d ** 2 + prof_d ** 2 + mar_d ** 2 + v_d ** 2) ** 0.5


def main():
    print("=" * 70)
    print("REGIONAL DIFFERENTIATION VERIFICATION — Phase F5")
    print("=" * 70)

    dataset_path = Path("data/datasets/large_shipping_problem.json")
    problem = load_problem_from_json(str(dataset_path))

    clusterer = PortClustering(n_clusters=5)
    clusters = clusterer.cluster_ports(problem.ports)
    splitter = RegionalSplitter(problem)
    regional_problems = splitter.split(clusters)

    sorted_clusters = sorted(clusters.keys(), key=lambda c: len(clusters[c]), reverse=True)
    name_list = list(STANDARD_REGION_NAMES.values())
    cluster_to_region = {}
    for rank, cid in enumerate(sorted_clusters):
        cluster_to_region[cid] = name_list[rank] if rank < len(name_list) else f"Region_{rank}"

    all_data = derive_all_regional_policies(regional_problems, cluster_to_region)
    names = list(all_data.keys())

    # ── Metric 1: Policy uniqueness score ──────────────────────────
    pairs_total = 0
    pairs_different = 0
    for i, n1 in enumerate(names):
        for j, n2 in enumerate(names):
            if i >= j:
                continue
            pairs_total += 1
            p1 = all_data[n1]["policy"]
            p2 = all_data[n2]["policy"]
            if (
                p1["coverage_priority"]  != p2["coverage_priority"] or
                p1["profit_priority"]    != p2["profit_priority"] or
                p1["min_service_margin"] != p2["min_service_margin"] or
                p1["vessel_bias"]        != p2["vessel_bias"]
            ):
                pairs_different += 1
    uniqueness_score = pairs_different / pairs_total if pairs_total else 0.0

    # ── Metric 2: Region-to-region distance matrix ─────────────────
    distance_matrix = {}
    for n1 in names:
        distance_matrix[n1] = {}
        for n2 in names:
            if n1 == n2:
                distance_matrix[n1][n2] = 0.0
            else:
                distance_matrix[n1][n2] = policy_distance(
                    all_data[n1]["policy"], all_data[n2]["policy"]
                )

    avg_distance = sum(
        distance_matrix[n1][n2]
        for n1 in names for n2 in names if n1 != n2
    ) / (len(names) * (len(names) - 1))
    min_distance = min(
        distance_matrix[n1][n2]
        for n1 in names for n2 in names if n1 != n2
    )

    # ── Metric 3: Distinct vessel biases ───────────────────────────
    vessel_biases = [all_data[n]["policy"]["vessel_bias"] for n in names]
    distinct_vessels = len(set(vessel_biases))

    # ── Metric 4: Distinct corridor strategies ─────────────────────
    # (coverage, profit) pair per region
    corridor_strats = {
        (all_data[n]["policy"]["coverage_priority"],
         all_data[n]["policy"]["profit_priority"])
        for n in names
    }
    distinct_corridor_strats = len(corridor_strats)

    # ── Metric 5: Distinct hub strategies ──────────────────────────
    hub_focus_sets = {tuple(sorted(all_data[n]["policy"]["hub_focus"])) for n in names}
    distinct_hub_strats = len(hub_focus_sets)

    # ── Print summary ──────────────────────────────────────────────
    print(f"\n  Pairs with differing policy:    {pairs_different}/{pairs_total}")
    print(f"  Policy uniqueness score:        {uniqueness_score:.2%}")
    print(f"  Average region-to-region dist:  {avg_distance:.3f}")
    print(f"  Minimum region-to-region dist:  {min_distance:.3f}")
    print(f"  Distinct vessel biases:         {distinct_vessels}/{len(names)}")
    print(f"  Distinct corridor strategies:   {distinct_corridor_strats}/{len(names)}")
    print(f"  Distinct hub strategies:        {distinct_hub_strats}/{len(names)}")

    # ── Success criteria ──────────────────────────────────────────
    success = (
        uniqueness_score >= 0.8
        and distinct_vessels >= 2
        and distinct_corridor_strats >= 4
        and pairs_different >= 8  # 10 pairs - up to 2 ties
    )

    print(f"\n  SUCCESS CRITERION: {'PASS' if success else 'FAIL'}")
    print(f"    uniqueness >= 80%:      {'YES' if uniqueness_score >= 0.8 else 'NO'}")
    print(f"    distinct vessels >= 2:  {'YES' if distinct_vessels >= 2 else 'NO'}")
    print(f"    distinct corridors>=4:  {'YES' if distinct_corridor_strats >= 4 else 'NO'}")

    # ── Export REGIONAL_DIFFERENTIATION_REPORT.md ──────────────────
    output_path = Path("REGIONAL_DIFFERENTIATION_REPORT.md")
    with output_path.open("w", encoding="utf-8") as f:
        f.write("# Regional Differentiation Report — Phase F5\n\n")
        f.write("**Generated by:** `scripts/regional_differentiation_report.py`\n\n")
        f.write("This report verifies that the Regional Agent produces materially\n")
        f.write("different policies for each of the 5 regions based on regional\n")
        f.write("characteristics.\n\n")

        f.write("## Summary Metrics\n\n")
        f.write("| Metric | Value | Threshold | Pass? |\n")
        f.write("|---|---:|---|---|\n")
        f.write(f"| Policy uniqueness score | **{uniqueness_score:.1%}** | ≥80% | "
                f"{'YES' if uniqueness_score >= 0.8 else 'NO'} |\n")
        f.write(f"| Distinct vessel biases | **{distinct_vessels}** | ≥2 | "
                f"{'YES' if distinct_vessels >= 2 else 'NO'} |\n")
        f.write(f"| Distinct corridor strategies | **{distinct_corridor_strats}** | ≥4 | "
                f"{'YES' if distinct_corridor_strats >= 4 else 'NO'} |\n")
        f.write(f"| Distinct hub strategies | **{distinct_hub_strats}** | ≥3 | "
                f"{'YES' if distinct_hub_strats >= 3 else 'NO'} |\n")
        f.write(f"| Average region-to-region distance | **{avg_distance:.3f}** | — | — |\n")
        f.write(f"| Minimum region-to-region distance | **{min_distance:.3f}** | >0 | "
                f"{'YES' if min_distance > 0 else 'NO'} |\n")
        f.write(f"\n**Overall verdict:** {'**PASS**' if success else '**FAIL**'}\n\n")

        f.write("## Per-Region Policy Snapshot\n\n")
        f.write("| Region | Coverage | Profit | Margin | Vessel | "
                "Hub# | Corridor# | Service Style |\n")
        f.write("|---|---:|---:|---:|---|---:|---:|---|\n")
        for name in names:
            p = all_data[name]["policy"]
            m = all_data[name]["metrics"]
            style = m["derived"].get("concentration_level", "?") + "/"
            style += m["derived"].get("density_level", "?")
            f.write(
                f"| **{name}** | {p['coverage_priority']:.2f} | {p['profit_priority']:.2f} | "
                f"{p['min_service_margin']:.2f} | {p['vessel_bias']} | "
                f"{len(p['hub_focus'])} | {len(p['corridor_focus'])} | {style} |\n"
            )

        f.write("\n## Pairwise Policy Distance Matrix\n\n")
        f.write("Euclidean distance over (coverage, profit, margin, vessel_code).\n\n")
        f.write("| | " + " | ".join(names) + " |\n")
        f.write("|---|" + "|".join(["---:"] * len(names)) + "|\n")
        for n1 in names:
            row = [n1]
            for n2 in names:
                row.append(f"{distance_matrix[n1][n2]:.3f}")
            f.write("| " + " | ".join(row) + " |\n")

        f.write("\n## Region-to-Region Comparison (Adjacency Pairs)\n\n")
        for i, n1 in enumerate(names):
            for j, n2 in enumerate(names):
                if i >= j:
                    continue
                p1 = all_data[n1]["policy"]
                p2 = all_data[n2]["policy"]
                d = distance_matrix[n1][n2]
                f.write(f"### {n1} vs {n2}\n\n")
                f.write(f"- Distance: **{d:.3f}**\n")
                f.write(f"- Coverage: {p1['coverage_priority']:.2f} vs {p2['coverage_priority']:.2f}\n")
                f.write(f"- Profit: {p1['profit_priority']:.2f} vs {p2['profit_priority']:.2f}\n")
                f.write(f"- Margin: {p1['min_service_margin']:.2f} vs {p2['min_service_margin']:.2f}\n")
                f.write(f"- Vessel: {p1['vessel_bias']} vs {p2['vessel_bias']}\n")
                f.write(f"- Hub focus: {p1['hub_focus']} vs {p2['hub_focus']}\n\n")

        f.write("## Distinct Element Counts\n\n")
        f.write(f"- **Vessel biases:** {sorted(set(vessel_biases))} "
                f"({distinct_vessels} distinct)\n")
        f.write(f"- **Corridor strategies** (coverage, profit):\n")
        for cov, prof in sorted(corridor_strats):
            f.write(f"  - ({cov:.2f}, {prof:.2f})\n")
        f.write(f"- **Hub focus sets** ({distinct_hub_strats} distinct):\n")
        for hfs in hub_focus_sets:
            f.write(f"  - {list(hfs)}\n")

        f.write("\n## Rationale per Region\n\n")
        for name in names:
            p = all_data[name]["policy"]
            m = all_data[name]["metrics"]
            f.write(f"### {name}\n\n")
            f.write(f"- Total demand: {m['total_demand']:,.0f} TEU/wk\n")
            f.write(f"- Top-3 corridor share: {m['top3_corridor_share']:.1f}%\n")
            f.write(f"- Median lane volume: {m['median_lane_volume']:,.0f} TEU\n")
            f.write(f"- Network density: {m['network_density']:.1f}%\n")
            f.write(f"- Hub centrality: {m['hub_centrality']:.1f}%\n")
            f.write(f"- Imbalance: {m['import_export_imbalance']:.1f}%\n")
            f.write(f"\n**Policy rationale:**\n")
            for r in p.get("rationale", []):
                f.write(f"- {r}\n")
            f.write("\n")

    print(f"\n[OK] Differentiation report exported to: {output_path}")
    print(f"   Overall: {'PASS' if success else 'FAIL'}")


if __name__ == "__main__":
    main()
