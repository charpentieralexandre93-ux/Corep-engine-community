# Release report v5.0.6

## Résultat de recette

- Enterprise : 833 tests réussis, 8 ignorés selon environnement.
- Community : 129 tests réussis, 1 ignoré selon environnement.
- Compilation Python : réussie.
- Wheel Enterprise et Community : construits.
- Frontière open-core : vérifiée par le builder (SA + SA-CCR uniquement).
- Version critique : 5.0.6 cohérente.
- Manifeste SQL : régénéré depuis le registry.

## Périmètres complétés

1. Large Exposures enrichi : groupes liés, CCF, indirect, exemptions,
   immobilier, CRM/substitution, seuils et limites.
2. Own Funds / Leverage : éligibilité instrument, amortissement T2,
   déductions/seuils et mesure d'exposition détaillée.
3. Operational Risk : composantes annuelles sur trois exercices et BIC CRR3.
4. CVA : approche simplifiée Art.385 en complément BA-CVA / SA-CVA.
5. Market Risk IMA : ES empirique, horizons de liquidité, calibration stress.
6. FRTB Controls : add-on monétaire sur assiette ES.
7. Stress testing : moteur transverse de scénarios et chocs.
8. DPM/XBRL : instance XBRL 2.1 auditée et checksum.

## Architecture de données

La v5.0.6 ajoute des relations canoniques quasi-3NF/BCNF pour les règles et
paramètres, les groupes de clients liés, les instruments de capital, les
métadonnées DPM, les scénarios IMA et le stress testing. Les anciens CSV restent
acceptés comme contrat d'interface rétrocompatible.

## Limites externes

Les modèles de pricing, scénarios macro/satellites, packages taxonomiques EBA et
validateurs de filing rules ne sont pas inventés par le moteur. Ils sont fournis
par les systèmes amont ou chargés comme référentiels versionnés.
