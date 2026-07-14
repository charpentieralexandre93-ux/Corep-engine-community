# Changelog v6.8.0 — Hygiène du dépôt et alignement de version

- Racine allégée : `CHANGELOG_v*.md` → `changelogs/`, rapports de release →
  `releases/`, SBOM antérieurs → `releases/sbom/` (SBOM courant à la racine).
  Références (contrat de release, tests de surface, README, renvois) mises à jour.
- Version produit alignée sur l'Enterprise v6.8.0 (alignement Art.386 du
  moteur CVA côté Enterprise ; périmètre Community SA + SA-CCR inchangé).
- Premier run CI : `check_release_metrics.py --write` sur le leg 3.12 si le
  compte de tests évolue.
