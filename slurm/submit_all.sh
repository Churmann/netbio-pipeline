#!/bin/bash
# Submit the three stages as a dependency chain:
# metrics starts only if fetch succeeds; downstream only if metrics succeeds.
set -euo pipefail
cd "$(dirname "$0")/.."          # run from the project root
mkdir -p slurm/logs             # SLURM needs the log dir to exist before jobs start

jid1=$(sbatch --parsable slurm/01_fetch.sh)
echo "submitted fetch      -> job $jid1"

jid2=$(sbatch --parsable --dependency=afterok:$jid1 slurm/02_metrics.sh)
echo "submitted metrics    -> job $jid2 (after $jid1)"

jid3=$(sbatch --parsable --dependency=afterok:$jid2 slurm/03_downstream.sh)
echo "submitted downstream -> job $jid3 (after $jid2)"

echo
echo "watch it with:  squeue -u $USER"
