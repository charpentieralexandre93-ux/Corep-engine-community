# COREP v6.7.1 — Correctif packaging utilisateur Windows

## Objet

Ajout d'un parcours utilisateur final par doubles-clics, sans bump applicatif.

## Ajouts

- `INSTALL_WINDOWS.bat` : installation locale dans `.venv`.
- `RUN_GUI_WINDOWS.bat` : lancement GUI via venv.
- `BOOTSTRAP_SQL_WINDOWS.bat` : vérification et manifeste SQL.
- `RUN_PHASE1_WINDOWS.bat` : lancement direct Enterprise Phase 1.
- `docs/INSTALLATION_UTILISATEUR.md` : guide utilisateur final.

## Nettoyage

- Suppression des anciens `PATCH_REPORT_v*`.
- Suppression des anciens `RELEASE_REPORT_v*` sauf `v6_7_1`.
- Suppression des anciens `VALIDATION_v*` sauf `v6_7_1`.
- Suppression des anciens SBOM sauf `v6.7.1`.
- Les changelogs historiques sont conservés comme historique produit.

## Version

La version reste `6.7.1`.
