#!/usr/bin/env python3
"""
Stage 1 of the netbio-pipeline: fetch a protein-protein interaction (PPI)
subnetwork from the STRING database.

This stage is deliberately self-contained: it takes no input file, talks to the
STRING REST API, and writes exactly one output file (an edge list CSV). Later
stages read that file. Because the only contract between stages is "a file on
disk at a path you pass in", each stage can become its own SLURM job.

Example
-------
    python src/01_fetch_data.py --output data/edges.csv
"""

import argparse
import csv
import os
import sys

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Apoptosis / DNA-damage response genes. TP53 and MDM2 sit at the top of this
# regulatory network, so we expect them to show up as hubs in stage 2.
DEFAULT_GENES = [
    "TP53", "MDM2", "BAX", "BCL2", "CASP3", "CASP9", "CASP8", "CYCS",
    "APAF1", "BAD", "BID", "BAK1", "BCL2L1", "FADD", "TNF", "TRADD",
    "DIABLO", "XIAP", "PARP1", "ATM",
]

# STRING's REST API is built from three parts: base / output-format / method.
STRING_API_URL = "https://string-db.org/api"
OUTPUT_FORMAT = "tsv"
METHOD = "network"

# NCBI taxonomy identifier. 9606 == Homo sapiens.
DEFAULT_SPECIES = 9606


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

def parse_args():
    """Define every input and output as an explicit command-line argument."""
    parser = argparse.ArgumentParser(
        description="Stage 1: fetch a STRING PPI subnetwork and write an edge list CSV.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--output", "-o",
        default=os.path.join("data", "edges.csv"),
        help="Path of the edge list CSV to write.",
    )
    parser.add_argument(
        "--genes",
        nargs="+",
        default=DEFAULT_GENES,
        help="Gene symbols to query, separated by spaces.",
    )
    parser.add_argument(
        "--species",
        type=int,
        default=DEFAULT_SPECIES,
        help="NCBI taxonomy ID (9606 = human).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Seconds to wait for the STRING API before giving up.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def fetch_network(genes, species, timeout):
    """Ask STRING for the interactions among `genes` and return the raw TSV text.

    Any network problem (DNS failure, timeout, HTTP error) is turned into a
    readable message and a non-zero exit code, so a failed SLURM job is easy to
    diagnose from the log file.
    """
    request_url = "/".join([STRING_API_URL, OUTPUT_FORMAT, METHOD])

    params = {
        # STRING wants the identifiers separated by a carriage return.
        "identifiers": "\r".join(genes),
        "species": species,
        # Polite identification, requested by STRING's usage guidelines.
        "caller_identity": "netbio-pipeline",
    }

    print(f"[stage 1] Querying STRING for {len(genes)} genes (species {species})...")
    print(f"[stage 1] Endpoint: {request_url}")

    try:
        response = requests.post(request_url, data=params, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        sys.exit(
            f"ERROR: could not reach the STRING API at {request_url}\n"
            f"       {exc}\n"
            f"       Check your network connection and try again."
        )

    return response.text


def parse_edges(tsv_text):
    """Turn STRING's TSV response into a list of (protein1, protein2, score) rows.

    STRING returns each interaction once, but we de-duplicate on an unordered
    pair anyway so the edge list is guaranteed to be clean for stage 2.
    """
    lines = tsv_text.strip().splitlines()
    if len(lines) < 2:
        sys.exit(
            "ERROR: STRING returned no interactions.\n"
            "       Check that the gene symbols and species ID are correct."
        )

    reader = csv.DictReader(lines, delimiter="\t")

    edges = []
    seen = set()
    for row in reader:
        # preferredName_* are the human-readable gene symbols; the alternative
        # (stringId_*) would give us Ensembl protein IDs instead.
        protein1 = row["preferredName_A"]
        protein2 = row["preferredName_B"]
        # "score" here is STRING's combined score, reported on a 0-1 scale.
        combined_score = float(row["score"])

        pair = frozenset((protein1, protein2))
        if pair in seen:
            continue
        seen.add(pair)

        edges.append((protein1, protein2, combined_score))

    return edges


def write_edges(edges, output_path):
    """Write the edge list to CSV, creating the parent directory if needed."""
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["protein1", "protein2", "combined_score"])
        writer.writerows(edges)


def main():
    args = parse_args()

    tsv_text = fetch_network(args.genes, args.species, args.timeout)
    edges = parse_edges(tsv_text)

    nodes = {protein for edge in edges for protein in edge[:2]}
    print(f"[stage 1] Retrieved {len(edges)} interactions among {len(nodes)} proteins.")

    write_edges(edges, args.output)
    print(f"[stage 1] Wrote edge list -> {args.output}")
    print("[stage 1] Done.")


if __name__ == "__main__":
    main()
