# Changelog v6.8.1 — SBOM outillé et alignement de version

- SBOM Community généré par `tools/generate_sbom_from_lock.py` (reproductible
  hors-ligne depuis le lockfile runtime, mode `--check` pour la CI), plus une
  copie de release en release. Périmètre exact : le SBOM Community ne liste
  désormais que ses dépendances runtime réelles (psycopg2-binary), au lieu
  des 8 composants hérités de l'édition Enterprise.
- Références du contrat de release dérivées de `__version__` (correction d'un
  échec latent depuis v6_7_0 détecté par le filet offline).
- Version alignée sur l'Enterprise v6.8.1 (LCR Annexe I côté Enterprise ;
  périmètre Community SA + SA-CCR inchangé).
