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
    python src/01_fetch_data.py --config config.yaml

The gene list, species ID and STRING request parameters are read from a YAML
config file (config.yaml at the project root by default) so the pipeline can be
pointed at a different biological question without editing this code. The
existing command-line arguments still work and take precedence over the config
file.
"""

import argparse
import csv
import os
import sys

import requests
import yaml

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Path to the YAML config file, relative to the current working directory
# (the project root, matching how every stage is invoked).
DEFAULT_CONFIG_PATH = "config.yaml"

# Fallback values. These are used only when a key is missing from the config
# file; config.yaml is the intended source of truth.

# Apoptosis / DNA-damage response genes. TP53 and MDM2 sit at the top of this
# regulatory network, so we expect them to show up as hubs in stage 2.
DEFAULT_GENES = [
    "TP53", "MDM2", "BAX", "BCL2", "CASP3", "CASP9", "CASP8", "CYCS",
    "APAF1", "BAD", "BID", "BAK1", "BCL2L1", "FADD", "TNF", "TRADD",
    "DIABLO", "XIAP", "PARP1", "ATM",
]

# NCBI taxonomy identifier. 9606 == Homo sapiens.
DEFAULT_SPECIES = 9606

# STRING's REST API is built from three parts: base / output-format / method.
# `required_score` is STRING's confidence cut-off (0-1000); None sends none.
DEFAULT_STRING_API = {
    "base_url": "https://string-db.org/api",
    "output_format": "tsv",
    "method": "network",
    "required_score": None,
    "caller_identity": "netbio-pipeline",
}


def load_config(path):
    """Read the YAML config file and return it as a dict.

    A missing file is a hard error: the pipeline's inputs now live in config.yaml,
    so running without it is almost certainly a mistake rather than an intent to
    fall back to the built-in defaults.
    """
    if not os.path.exists(path):
        sys.exit(
            f"ERROR: config file not found: {path}\n"
            f"       Pass --config with the path to your config.yaml."
        )
    with open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data or {}


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
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help="Path to the YAML config file holding the gene list, species ID "
             "and STRING request parameters.",
    )
    parser.add_argument(
        "--output", "-o",
        default=os.path.join("data", "edges.csv"),
        help="Path of the edge list CSV to write.",
    )
    parser.add_argument(
        "--genes",
        nargs="+",
        default=None,
        help="Gene symbols to query, separated by spaces. "
             "Overrides 'genes' in the config file.",
    )
    parser.add_argument(
        "--species",
        type=int,
        default=None,
        help="NCBI taxonomy ID (9606 = human). "
             "Overrides 'species' in the config file.",
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

def fetch_network(genes, species, timeout, string_api):
    """Ask STRING for the interactions among `genes` and return the raw TSV text.

    Any network problem (DNS failure, timeout, HTTP error) is turned into a
    readable message and a non-zero exit code, so a failed SLURM job is easy to
    diagnose from the log file.
    """
    request_url = "/".join([
        string_api["base_url"],
        string_api["output_format"],
        string_api["method"],
    ])

    params = {
        # STRING wants the identifiers separated by a carriage return.
        "identifiers": "\r".join(genes),
        "species": species,
        # Polite identification, requested by STRING's usage guidelines.
        "caller_identity": string_api["caller_identity"],
    }

    # Only send a confidence cut-off if one is configured; otherwise STRING
    # applies its own default and the request is byte-for-byte as before.
    required_score = string_api.get("required_score")
    if required_score is not None:
        params["required_score"] = required_score

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
    config = load_config(args.config)

    # Precedence for each input: command-line argument > config file > built-in
    # fallback.
    genes = args.genes or config.get("genes") or DEFAULT_GENES
    species = (
        args.species if args.species is not None
        else config.get("species", DEFAULT_SPECIES)
    )
    string_api = {**DEFAULT_STRING_API, **(config.get("string_api") or {})}

    tsv_text = fetch_network(genes, species, args.timeout, string_api)
    edges = parse_edges(tsv_text)

    nodes = {protein for edge in edges for protein in edge[:2]}
    print(f"[stage 1] Retrieved {len(edges)} interactions among {len(nodes)} proteins.")

    write_edges(edges, args.output)
    print(f"[stage 1] Wrote edge list -> {args.output}")
    print("[stage 1] Done.")


if __name__ == "__main__":
    main()
