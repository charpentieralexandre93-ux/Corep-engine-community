# syntax=docker/dockerfile:1.7
# Corep Engine Community v6.10.0 — image one-shot non-root et reproductible.
FROM python:3.11-slim-bookworm@sha256:e2d3af735aff6eeee600b1933bedd99da6645fedf572cc12ef4cc1331f2ceebe AS builder
ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1 SOURCE_DATE_EPOCH=1781481600
WORKDIR /build
COPY requirements-dev-py311-linux.lock /build/requirements-dev-py311-linux.lock
RUN python -m pip install --no-cache-dir --require-hashes -r /build/requirements-dev-py311-linux.lock
COPY . /build
RUN PYTHONPATH=src python -m corep_crr3.release_integrity \
      --root /build --manifest RELEASE_MANIFEST.json --version "$(PYTHONPATH=src python -c 'from corep_crr3 import __version__; print(__version__)')" --edition COMMUNITY \
 && python -m build --wheel --no-isolation \
 && python tools/verify_public_wheel.py dist/*.whl

FROM python:3.11-slim-bookworm@sha256:e2d3af735aff6eeee600b1933bedd99da6645fedf572cc12ef4cc1331f2ceebe AS runtime
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --gid 10001 corep \
 && useradd --uid 10001 --gid corep --create-home --shell /usr/sbin/nologin corep
COPY --from=builder /build/dist/*.whl /tmp/wheels/
COPY requirements-runtime-py311-linux.lock /app/requirements-runtime-py311-linux.lock
RUN python -m pip install --no-cache-dir --require-hashes -r /app/requirements-runtime-py311-linux.lock \
 && python -m pip install --no-cache-dir --no-deps /tmp/wheels/*.whl \
 && rm -rf /tmp/wheels
WORKDIR /app
RUN mkdir -p /app/output && chown -R corep:corep /app
USER 10001:10001
CMD ["corep-community"]
