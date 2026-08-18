# netbio-pipeline: reproducible image for the three pipeline stages.
#
# Build:
#     docker build -t netbio:latest .
#
# Run any stage by naming its script (the entrypoint is `python`):
#     docker run --rm netbio:latest src/02_metrics.py --help
#
# The interpreter is pinned to 3.12 to match the venv the project was developed
# and locked on; the slim variant keeps the image small and the wheel set is
# pure manylinux, so no compiler toolchain is needed.
FROM python:3.12-slim

# PYTHONDONTWRITEBYTECODE - no .pyc litter in the image layers.
# PYTHONUNBUFFERED       - stdout reaches the SLURM log as the stage runs,
#                          instead of being buffered until the process exits.
# MPLCONFIGDIR           - matplotlib needs a writable config dir; HOME is not
#                          guaranteed writable under Apptainer on the cluster.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /app

# Dependencies are copied and installed before the source, so that editing a
# stage script does not invalidate the (slow) dependency layer.
#
# requirements.txt is carried along for provenance only - it documents the four
# direct dependencies for anyone reading the image. The install itself uses the
# lock file, with --no-deps so pip installs exactly what is pinned there and
# resolves nothing at build time. `pip check` then verifies that the frozen set
# is internally consistent, turning a lock file with a missing transitive
# dependency into a build failure rather than a runtime ImportError.
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir --no-deps -r requirements.lock \
    && pip check

COPY src/ ./src/

# Default mount points. Both are bind-mounted in normal use; creating them here
# means the image still runs (writing into the container's own filesystem) when
# they are not.
RUN mkdir -p data outputs

# No USER directive on purpose: the image's real target is Apptainer on the
# cluster, which runs the container as the invoking user regardless. Adding a
# fixed non-root UID here would gain nothing there and would break writes into
# host bind mounts under plain Docker.

# `python` as the entrypoint keeps all three stages reachable from one image -
# the stage is an argument, not baked into the image.
ENTRYPOINT ["python"]

# Bare `docker run netbio:latest` explains itself rather than picking a stage.
CMD ["-c", "print('netbio-pipeline image'); print(); print('Stages:'); print('  src/01_fetch_data.py   fetch the STRING edge list (needs network access)'); print('  src/02_metrics.py      centrality + communities -> hub_genes.csv'); print('  src/03_downstream.py   network figure -> network.png'); print(); print('Run one by naming it, e.g.:'); print('  docker run --rm -v ./data:/app/data -v ./outputs:/app/outputs \\\\'); print('      netbio:latest src/02_metrics.py --edges data/edges.csv --output outputs/hub_genes.csv'); print(); print('Pass --help to any stage for its full argument list.')"]
