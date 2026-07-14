# Changelog v6.2.0 — COREP Engine Community

Date : 19 juin 2026

Release majeure de qualité interne générée depuis Enterprise. Le périmètre public reste strictement limité à SA et SA-CCR ; aucune formule réglementaire ni aucun schéma SQL public n’est modifié volontairement.

## Qualité et maintenabilité

- Ruff complet `E/F/W/I/C90` et seuil cyclomatique maximal de 20 ;
- formatage déterministe bloquant ;
- Mypy strict étendu au socle partagé SA/SA-CCR et à ses contrats ;
- baseline de couverture de branche sur SA, SA-CCR et le GUI Community.

## Couverture produit

- GUI Community maintenu dans le dénominateur officiel ;
- tests headless des configurations PostgreSQL, journaux, files d’événements et contrôle des processus ;
- couverture combinée du GUI portée à environ 55 % ;
- seuil global officiel maintenu au-dessus de 65 % avec le GUI inclus.

## Performance

- benchmark machine-readable des noyaux SA/SA-CCR/CRM ;
- seuil minimal bloquant et preuve JSON publiée par la CI.

## Industrialisation

- publication toujours dépendante de la CI complète ;
- Docker/PostgreSQL bloquants ;
- ZIP source et wheel reproductibles ;
- frontière SA/SA-CCR vérifiée à chaque génération.
