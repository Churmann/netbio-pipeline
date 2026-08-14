# netbio-pipeline

A small, reproducible network-biology pipeline over a human protein-protein
interaction (PPI) subnetwork from [STRING](https://string-db.org/).

The pipeline is split into **discrete stages**. Every stage is a standalone
script whose inputs and outputs are explicit command-line arguments, so each one
can later run as its own containerised SLURM job.

## Stages

| Stage | Script | Reads | Writes |
|-------|--------|-------|--------|
| 1 | `src/01_fetch_data.py` | STRING API | `data/edges.csv` |
| 2 | `src/02_metrics.py` | `data/edges.csv` | `outputs/hub_genes.csv` |
| 3 | `src/03_downstream.py` | `data/edges.csv`, `outputs/hub_genes.csv` | `outputs/network.png` |

Stage 1 queries a 20-gene apoptosis / DNA-damage-response set (TP53, MDM2, BAX,
BCL2, CASP3, ...). Stage 2 computes degree and betweenness centrality and
detects communities by greedy modularity. Stage 3 draws the network, colouring
nodes by community and sizing them by degree centrality.

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run

With default paths, in order:

```bash
python src/01_fetch_data.py
python src/02_metrics.py
python src/03_downstream.py
```

Every path is overridable, which is how the stages stay portable across
container and scheduler boundaries:

```bash
python src/02_metrics.py --edges data/edges.csv --output outputs/hub_genes.csv
```

Pass `--help` to any stage to see its full interface.

### Local note: TLS interception on this Windows machine

AVG Antivirus ("Web/Mail Shield") intercepts HTTPS on this machine and re-signs
certificates with its own root CA. That root is trusted by the Windows
certificate store but is absent from the `certifi` bundle Python uses, so stage 1
fails with `CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`.

The workaround keeps certificate verification fully enabled: `venv/ca-bundle.pem`
is certifi's bundle plus that AVG root. Point `requests` at it before stage 1:

```powershell
$env:REQUESTS_CA_BUNDLE = "$PWD\venv\ca-bundle.pem"   # PowerShell
```
```bash
export REQUESTS_CA_BUNDLE="$PWD/venv/ca-bundle.pem"    # bash
```

This is a host-environment quirk, not part of the pipeline: no stage script
contains a certificate workaround, and none is needed inside the Linux
container. Regenerate the bundle if AVG rotates its root certificate.

## Layout

```
data/      input and intermediate data (git-ignored)
outputs/   final results (git-ignored)
src/       the three stage scripts
slurm/     job submission scripts (to be added)
```

## Roadmap

- [ ] `slurm/` job scripts, one per stage
- [ ] Dockerfile
- [ ] Apptainer/Singularity conversion
