#!/bin/bash
#SBATCH --job-name=netbio-metrics
#SBATCH --output=slurm/logs/%x-%j.out
#SBATCH --cpus-per-task=2              # betweenness centrality is the heaviest step
#SBATCH --mem=2G
#SBATCH --time=00:10:00

cd "$SLURM_SUBMIT_DIR" || exit 1
echo "[metrics] on $(hostname) at $(date)"
apptainer run --bind ./data:/app/data,./outputs:/app/outputs netbio.sif src/02_metrics.py
echo "[metrics] done"
