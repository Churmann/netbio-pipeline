# Snakefile
#
# The same three-stage DAG as slurm/submit_all.sh, expressed as a workflow so
# Snakemake works out the order, skips stages whose outputs are up to date, and
# (with profiles/slurm) submits each stage as its own SLURM job.
#
#     snakemake --cores 1                         # plain local run
#     snakemake --cores 1 --sdm apptainer \
#         --apptainer-args "--bind ./data:/app/data,./outputs:/app/outputs"
#     snakemake --profile profiles/slurm          # one SLURM job per rule
#
# Every stage is still just its script, called with the same CLI flags as
# before. Resources mirror the #SBATCH lines in slurm/*.sh.

# Gene list, species and STRING request parameters stay in config.yaml; nothing
# here repeats them. Stage 1 reads the same file, and listing it as an input
# means editing it re-runs the whole chain.
configfile: "config.yaml"

# Only used with --sdm apptainer: the same image the SLURM job scripts run.
# Without it, each rule runs with whatever python is on PATH (e.g. the venv).
container: "netbio.sif"

# `all` only collects the final output; no point queueing it as a SLURM job.
localrules: all


rule all:
    input:
        "outputs/network.png",


rule fetch:
    input:
        config="config.yaml",
    output:
        edges="data/edges.csv",
    threads: 1
    resources:
        cpus_per_task=1,
        mem_mb=1024,
        runtime=5,
    shell:
        "python src/01_fetch_data.py --config {input.config} --output {output.edges}"


rule metrics:
    input:
        edges="data/edges.csv",
    output:
        hubs="outputs/hub_genes.csv",
    threads: 2
    resources:
        cpus_per_task=2,
        mem_mb=2048,
        runtime=10,
    shell:
        "python src/02_metrics.py --edges {input.edges} --output {output.hubs}"


rule downstream:
    input:
        edges="data/edges.csv",
        hubs="outputs/hub_genes.csv",
    output:
        figure="outputs/network.png",
    params:
        seed=42,
    threads: 1
    resources:
        cpus_per_task=1,
        mem_mb=2048,
        runtime=10,
    shell:
        "python src/03_downstream.py --edges {input.edges} --hubs {input.hubs}"
        " --output {output.figure} --seed {params.seed}"
