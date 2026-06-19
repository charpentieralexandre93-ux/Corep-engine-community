# Validation Corep Engine Community v6.1.0

Date de validation : 15 juin 2026

## Correctifs P0/P1

- contrat Python porté à `>=3.11,<3.14` ; Python 3.9 retiré de la matrice CI ;
- contrôles Ruff, mypy et Bandit centralisés dans un job qualité Python 3.11 verrouillé ;
- audit supply-chain séparé entre dépendances runtime bloquantes et outillage de développement informatif ;
- E2E PostgreSQL rendu bloquant avec conservation systématique des journaux et preuves ;
- manifeste de release régénérable après normalisation Git des fins de ligne ;
- workflows de release verrouillés et collecte des artefacts en cas d'échec ;
- contrat Community vérifié : Apache-2.0, SA et SA-CCR uniquement.

## Non-régression locale

- pytest : **163 réussis, 1 ignoré conditionnellement** ;
- couverture lignes globale : **71,50 %** (seuil 65 %) ;
- Ruff 0.15.17 : succès ;
- mypy 1.20.2 : succès sur 16 fichiers source ;
- Bandit 1.9.4 : aucune anomalie moyenne ou élevée ;
- 13 scripts SQL analysés syntaxiquement avec pglast : succès ;
- 4 fichiers YAML analysés : succès ;
- garde-fous version, licence, périmètre public, exceptions et docstrings : succès ;
- édition Community autonome identique à celle générée depuis Enterprise, hors manifeste régénéré ;
- wheel public reproductible : `f8c8946a7fceb8a57ebe78340938758865f9947668de3f6f2c7e59943faddb14` ;
- vérification du wheel public : succès.

## Limites de l'environnement de validation

La recette PostgreSQL réelle et l'interrogation en ligne de la base d'advisories de `pip-audit` n'ont pas pu être exécutées dans l'environnement local de génération. Les workflows GitHub les conservent comme contrôles bloquants et publient désormais leurs journaux et rapports même en cas d'échec.
