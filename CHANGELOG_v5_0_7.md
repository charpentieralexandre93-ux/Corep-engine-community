# COREP Engine Community v5.0.7 — Durcissement qualité

## Objet

Release de **durcissement qualité**, sans aucune modification des calculs
SA (Art.107–141) ni SA-CCR (Art.274–282) ni des contrats CSV. Non-régression
stricte : le jeu de tests Community passe à l'identique.

## Changements

- **Robustesse des modules de calcul partagés.** Les convertisseurs tolérants
  `standard_engine._maturity_bucket` et `decision_engine._as_float` resserrent
  leur capture d'exception à `except (TypeError, ValueError)`. Le comportement
  par défaut est **inchangé** (retour `None` sur entrée invalide) ; seules les
  exceptions réellement inattendues (bug, erreur système) ne sont plus masquées.
  Issu d'un audit complet des `except Exception` : aucune capture n'avalait
  silencieusement une erreur sur un chemin RWA.
- **Typage.** Marqueur PEP 561 `py.typed` maintenu dans le wheel ; posture mypy
  inchangée (report-only, à durcir progressivement).

## Non-régression

- Aucun coefficient réglementaire, SQL de calcul ou citation d'article modifié.
- Frontière open-core revérifiée par le builder (SA + SA-CCR uniquement).
- Version 5.0.7 cohérente.
