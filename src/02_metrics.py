#!/usr/bin/env python3
"""
Stage 2 of the netbio-pipeline: turn an edge list into network metrics.

Reads the CSV written by stage 1, builds an undirected weighted graph, and
computes:
  * degree centrality      - how many partners a protein has (normalised)
  * betweenness centrality - how often a protein sits on shortest paths
  * community membership   - greedy modularity ("Clauset-Newman-Moore")

Example
-------
    python src/02_metrics.py --edges data/edges.csv --output outputs/hub_genes.csv
"""

import argparse
import os
import sys

import networkx as nx
import pandas as pd

DEFAULT_EDGES = os.path.join("data", "edges.csv")
DEFAULT_OUTPUT = os.path.join("outputs", "hub_genes.csv")


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Stage 2: compute centrality metrics and communities from an edge list.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--edges", "-e",
        default=DEFAULT_EDGES,
        help="Input edge list CSV produced by stage 1.",
    )
    parser.add_argument(
        "--output", "-o",
        default=DEFAULT_OUTPUT,
        help="Path of the hub gene table to write.",
    )
    return parser.parse_args()


def require_file(path, produced_by):
    """Exit with a readable message if an expected input file is missing.

    Each stage checks its own inputs so that a mis-ordered SLURM submission
    fails immediately with an explanation rather than a stack trace.
    """
    if not os.path.isfile(path):
        sys.exit(
            f"ERROR: required input file not found: {path}\n"
            f"       This file is produced by {produced_by}. Run that stage first,\n"
            f"       or pass the correct path on the command line."
        )


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def build_graph(edges_path):
    """Load the edge list and build an undirected weighted networkx graph."""
    frame = pd.read_csv(edges_path)

    expected = {"protein1", "protein2", "combined_score"}
    missing = expected - set(frame.columns)
    if missing:
        sys.exit(
            f"ERROR: {edges_path} is missing expected column(s): {', '.join(sorted(missing))}"
        )

    if frame.empty:
        sys.exit(f"ERROR: {edges_path} contains no interactions.")

    graph = nx.Graph()
    for row in frame.itertuples(index=False):
        score = float(row.combined_score)

        # STRING reports the combined score on a 0-1 scale, but some exports use
        # 0-1000. Normalise so the distance calculation below always behaves.
        confidence = score / 1000.0 if score > 1.0 else score

        graph.add_edge(
            row.protein1,
            row.protein2,
            # `weight` = confidence. Higher means a stronger interaction, which
            # is what modularity and the layout want.
            weight=confidence,
            # `distance` = the inverse notion, for shortest-path algorithms:
            # a strong interaction should be a SHORT hop, not a long one.
            # Clamped away from zero so no edge becomes free to traverse.
            distance=max(1.0 - confidence, 1e-6),
        )

    return graph


def compute_metrics(graph):
    """Compute per-node centralities and community assignments."""
    print("[stage 2] Computing degree centrality...")
    degree = nx.degree_centrality(graph)

    print("[stage 2] Computing betweenness centrality...")
    # Note the `distance` weight: betweenness is built on shortest paths, so the
    # edge attribute has to mean "cost to cross", not "confidence".
    betweenness = nx.betweenness_centrality(graph, weight="distance")

    print("[stage 2] Detecting communities (greedy modularity)...")
    communities = nx.community.greedy_modularity_communities(graph, weight="weight")

    # Flatten the list-of-sets into a {gene: community_index} lookup.
    community_of = {}
    for index, members in enumerate(communities):
        for gene in members:
            community_of[gene] = index

    print(f"[stage 2] Found {len(communities)} communities.")

    return degree, betweenness, community_of


def build_table(graph, degree, betweenness, community_of):
    """Assemble the results into a tidy table sorted by degree centrality."""
    table = pd.DataFrame(
        {
            "gene": list(graph.nodes()),
            "degree_centrality": [degree[gene] for gene in graph.nodes()],
            "betweenness_centrality": [betweenness[gene] for gene in graph.nodes()],
            "community": [community_of[gene] for gene in graph.nodes()],
        }
    )

    return table.sort_values("degree_centrality", ascending=False).reset_index(drop=True)


def main():
    args = parse_args()

    require_file(args.edges, "stage 1 (src/01_fetch_data.py)")

    print(f"[stage 2] Reading edges from {args.edges}")
    graph = build_graph(args.edges)
    print(
        f"[stage 2] Built graph with {graph.number_of_nodes()} nodes "
        f"and {graph.number_of_edges()} edges."
    )

    degree, betweenness, community_of = compute_metrics(graph)
    table = build_table(graph, degree, betweenness, community_of)

    parent = os.path.dirname(args.output)
    if parent:
        os.makedirs(parent, exist_ok=True)
    table.to_csv(args.output, index=False)

    print(f"[stage 2] Wrote hub gene table -> {args.output}")
    print("[stage 2] Done.")


if __name__ == "__main__":
    main()
