# CHANGELOG — Community v4.3.0

> v4.3.0 = v4.2.9 + licence Apache-2.0, SBOM, gating renforcé. Aucune formule modifiée.

## Licence (changement majeur)
- L'édition Community passe en **Apache-2.0** (open source permissive + clause de
  brevet), en remplacement de la précédente licence d'évaluation restrictive —
  pour favoriser l'adoption. Voir `LICENSE` et `NOTICE` ; `LICENSE-COMMUNITY.md`
  redirige désormais vers `LICENSE`. Métadonnées `pyproject.toml` mises à jour.

## SBOM (P1 #4)
- Étape CI **SBOM CycloneDX** publiée en artefact `sbom-cyclonedx`.

## Gating renforcé (P1 #6)
- **ruff** et **bandit** bloquants (depuis v4.2.9) ; plancher de couverture
  relevé **60 → 64 %**. **mypy** report-only prêt à basculer.

## Note
Édition **générée** depuis l'enterprise via `tools/build_community_edition.py`
(frontière Python + contrat SQL vérifiés, version contrôlée dynamiquement).
