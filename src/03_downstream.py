#!/usr/bin/env python3
"""
Stage 3 of the netbio-pipeline: visualise the network and report the top hubs.

Reads BOTH files produced upstream - the edge list from stage 1 and the metric
table from stage 2 - and draws the network with nodes coloured by community and
sized by degree centrality.

Example
-------
    python src/03_downstream.py --edges data/edges.csv \
        --hubs outputs/hub_genes.csv --output outputs/network.png
"""

import argparse
import os
import sys

import matplotlib

# Select a non-interactive backend BEFORE importing pyplot. Compute nodes have
# no display attached, so this is what keeps the script working under SLURM.
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (must follow matplotlib.use)
import networkx as nx  # noqa: E402
import pandas as pd  # noqa: E402

DEFAULT_EDGES = os.path.join("data", "edges.csv")
DEFAULT_HUBS = os.path.join("outputs", "hub_genes.csv")
DEFAULT_OUTPUT = os.path.join("outputs", "network.png")

TOP_N = 5


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Stage 3: draw the network and report the top hub genes.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--edges", "-e",
        default=DEFAULT_EDGES,
        help="Input edge list CSV produced by stage 1.",
    )
    parser.add_argument(
        "--hubs",
        default=DEFAULT_HUBS,
        help="Input hub gene table produced by stage 2.",
    )
    parser.add_argument(
        "--output", "-o",
        default=DEFAULT_OUTPUT,
        help="Path of the network figure to write.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for the layout, so the figure is reproducible.",
    )
    return parser.parse_args()


def require_file(path, produced_by):
    """Exit with a readable message if an expected input file is missing."""
    if not os.path.isfile(path):
        sys.exit(
            f"ERROR: required input file not found: {path}\n"
            f"       This file is produced by {produced_by}. Run that stage first,\n"
            f"       or pass the correct path on the command line."
        )


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def load_graph(edges_path):
    """Rebuild the same undirected weighted graph that stage 2 analysed."""
    frame = pd.read_csv(edges_path)

    graph = nx.Graph()
    for row in frame.itertuples(index=False):
        score = float(row.combined_score)
        confidence = score / 1000.0 if score > 1.0 else score
        graph.add_edge(row.protein1, row.protein2, weight=confidence)

    return graph


def draw_network(graph, hubs, output_path, seed):
    """Draw the network: colour = community, size = degree centrality."""
    # Look-ups keyed by gene, so we can order values to match graph.nodes().
    community_of = dict(zip(hubs["gene"], hubs["community"]))
    degree_of = dict(zip(hubs["gene"], hubs["degree_centrality"]))

    # A gene could appear in the graph but not the table if the two inputs came
    # from different runs. Fall back to sensible defaults instead of crashing.
    nodes = list(graph.nodes())
    colours = [community_of.get(gene, -1) for gene in nodes]
    sizes = [300 + degree_of.get(gene, 0.0) * 4000 for gene in nodes]

    # Spring layout treats `weight` as attraction: strongly interacting proteins
    # are pulled together, so communities end up visually clustered.
    positions = nx.spring_layout(graph, weight="weight", seed=seed, k=0.6)

    figure, axes = plt.subplots(figsize=(13, 10))

    # Edge transparency scaled by confidence: faint lines are weak evidence.
    edge_weights = [graph[u][v]["weight"] for u, v in graph.edges()]
    nx.draw_networkx_edges(
        graph, positions, ax=axes,
        width=[0.4 + weight * 2.2 for weight in edge_weights],
        alpha=0.35,
        edge_color="#5a5a5a",
    )

    nx.draw_networkx_nodes(
        graph, positions, ax=axes,
        node_color=colours,
        node_size=sizes,
        cmap=plt.cm.Set2,
        linewidths=1.0,
        edgecolors="white",
    )

    nx.draw_networkx_labels(
        graph, positions, ax=axes,
        font_size=9,
        font_weight="bold",
    )

    n_communities = len(set(colours))
    axes.set_title(
        "STRING PPI subnetwork - apoptosis / DNA damage response\n"
        f"{graph.number_of_nodes()} proteins, {graph.number_of_edges()} interactions, "
        f"{n_communities} communities "
        "(node size = degree centrality, colour = community)",
        fontsize=13,
    )
    axes.axis("off")
    figure.tight_layout()

    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    figure.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(figure)


def report_top_hubs(hubs, top_n=TOP_N):
    """Print the most connected genes to the console (and thus the SLURM log)."""
    print(f"\n[stage 3] Top {top_n} hub genes by degree centrality:")
    print(f"{'rank':<6}{'gene':<10}{'degree':>10}{'betweenness':>14}{'community':>12}")
    print("-" * 52)

    for rank, row in enumerate(hubs.head(top_n).itertuples(index=False), start=1):
        print(
            f"{rank:<6}{row.gene:<10}"
            f"{row.degree_centrality:>10.4f}"
            f"{row.betweenness_centrality:>14.4f}"
            f"{row.community:>12}"
        )
    print()


def main():
    args = parse_args()

    require_file(args.edges, "stage 1 (src/01_fetch_data.py)")
    require_file(args.hubs, "stage 2 (src/02_metrics.py)")

    print(f"[stage 3] Reading edges from {args.edges}")
    graph = load_graph(args.edges)

    print(f"[stage 3] Reading hub table from {args.hubs}")
    hubs = pd.read_csv(args.hubs)

    print("[stage 3] Drawing network...")
    draw_network(graph, hubs, args.output, args.seed)
    print(f"[stage 3] Wrote figure -> {args.output}")

    report_top_hubs(hubs)
    print("[stage 3] Done.")


if __name__ == "__main__":
    main()
