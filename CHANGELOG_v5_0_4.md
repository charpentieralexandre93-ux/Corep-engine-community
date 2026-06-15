# Changelog v5.0.4 — Community

## Périmètre

La v5.0.4 est une version d'**alignement**. La correction fonctionnelle de cette
version porte uniquement sur le moteur **Market Risk (SA-FRTB)**, qui appartient
à l'édition Enterprise. L'édition Community reste limitée à **SA** et **SA-CCR**
et n'embarque aucun module Market Risk.

## Non-régression

- Aucun changement de code dans le périmètre Community : les noyaux de calcul
  partagés (SA, SA-CCR, CRM, `db`, `decision_engine`…) sont **byte-identiques** à
  ceux de l'édition Enterprise.
- Version technique alignée en 5.0.4 par `tools/bump_version.py` afin de préserver
  l'identité exacte des modules partagés entre les deux éditions (anti-drift).
