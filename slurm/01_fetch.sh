#!/bin/bash
#SBATCH --job-name=netbio-fetch        # name shown in the queue
#SBATCH --output=slurm/logs/%x-%j.out  # log file: %x=job name, %j=job id
#SBATCH --cpus-per-task=1              # a single network call
#SBATCH --mem=1G                       # tiny memory footprint
#SBATCH --time=00:05:00                # killed if it runs longer than 5 min

cd "$SLURM_SUBMIT_DIR" || exit 1
echo "[fetch] on $(hostname) at $(date)"
apptainer run --bind ./data:/app/data netbio.sif src/01_fetch_data.py
echo "[fetch] done"
