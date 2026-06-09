# Corep Engine Community — image de démonstration SA / SA-CCR
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 \
 && rm -rf /var/lib/apt/lists/*
COPY . /app
# [postgres] = psycopg2 pour le bootstrap réel ; les fonctions pures n'en ont pas besoin.
RUN python -m pip install --upgrade pip && pip install -e ".[postgres]"
RUN useradd -m appuser && chown -R appuser /app
USER appuser
# Démo des fonctions pures (sans base) :
#   docker compose run --rm app python examples/sa_pure_functions.py
# Par défaut : bootstrap du schéma public SA / SA-CCR (nécessite la base).
CMD ["python", "-m", "corep_crr3.community_bootstrap"]
