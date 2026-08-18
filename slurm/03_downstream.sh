#!/bin/bash
#SBATCH --job-name=netbio-downstream
#SBATCH --output=slurm/logs/%x-%j.out
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00

cd "$SLURM_SUBMIT_DIR" || exit 1
echo "[downstream] on $(hostname) at $(date)"
apptainer run --bind ./data:/app/data,./outputs:/app/outputs netbio.sif src/03_downstream.py
echo "[downstream] done"
