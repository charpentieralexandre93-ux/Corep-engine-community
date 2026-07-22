# Changelog v6.9.0 — Alignement global et correctif du contrat de release

- **Correctif latent** : le contrat de release Community référençait encore
  `coverage_baseline_v6_5_0.json` contre un littéral de version bumpé (le
  correctif v6_8_1 n'avait été appliqué qu'à l'Enterprise) — la CI Community
  aurait échoué. Référence désormais dérivée de `__version__`.
- Hygiène : jeux de preuves historiques archivés sous `releases/evidence/`,
  `evidence/` ne porte que la version courante.
- Tampons « Version moteur » des notes alignés sur la release (6.9.0).
- Côté Enterprise : SOT NII à horizon un an à bilan constant et refactor des
  validateurs SA-CCR/SFT ; périmètre Community (SA + SA-CCR) inchangé.
