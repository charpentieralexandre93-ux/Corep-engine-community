# Changelog v6.7.0 — Gate de preuves et alignement toolchain

## CI / Preuves

### Fixed — Cohérence des métriques publiées
- `tools/check_release_metrics.py` dérive désormais `tests_collected` du rapport
  JUnit et le valide strictement ; garde de cohérence interne
  (`collected = passed + skipped`) rejetant toute preuve auto-contradictoire.
- `release_metrics_v6_7_0.json` réconcilié (248 collectés / 247 réussis / 1 ignoré) ;
  champ narratif sans chiffres codés en dur.

### Fixed — Gate exécutée sur la toolchain verrouillée
- La gate « Valider les métriques publiées » s'exécute sur le leg **3.12**
  (toolchain verrouillée 3.12.3) au lieu de 3.13 : la couverture publiée est à
  nouveau vérifiée strictement.

## Notes
- Le périmètre Community (SA crédit + SA-CCR) est inchangé ; les correctifs
  réglementaires v6.7.0 (BA-CVA, IRRBB SOT) concernent l'édition Enterprise.
- Le premier run CI recalculera `tests_passed` : mettre à jour les preuves via
  `check_release_metrics.py --write` sur le leg 3.12.
