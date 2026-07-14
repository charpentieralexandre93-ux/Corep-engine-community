# Matrice de sign-off réglementaire v6.7.0 — Community

Cette matrice est le point de contrôle P1 avant production de KPI CRR3. Elle ne remplace pas le sign-off superviseur : elle rend explicites les preuves externes attendues, la qualité des KPI et les sorties interdites en remise officielle.

## Gates externes obligatoires

| Gate | Statut v6.7.0 | Preuve minimale attendue |
|---|---|---|
| Taxonomie officielle | NOT_EXECUTED | Archive taxonomie + SHA-256 + source + date de remise + reviewer |
| Filing rules profile | NOT_EXECUTED | Profil NCA/BCE applicable + note d'applicabilité + reviewer |
| Known issues review | NOT_EXECUTED | Registre d'issues + hash + décision release manager |
| Mapping DPM signé | NOT_EXECUTED | Workbook de mapping + hash + maker/checker + exceptions |
| Golden dataset externe | NOT_EXECUTED | Inputs + outputs attendus produits hors moteur + hash |
| Legal review | NOT_EXECUTED | Mémo juridique signé avant vente/remise officielle |
| CI GitHub live verte | NOT_EXECUTED | URL Actions + SHA commit/tag + synthèse checks verts |

## Couverture fonctionnelle tracée

Périmètre tracé : **SA, SA-CCR**.

Le fichier d'evidence actif `evidence/regulatory_dossier_v6_7_0.json` contient la matrice détaillée avec les colonnes : référence réglementaire, template/table, module moteur, KPI/datapoint, source SQL ou input, formule/règle, test de contrôle, statut qualité, preuve externe et statut de revue.

## Statuts qualité KPI

| Statut | Utilisation |
|---|---|
| OFFICIAL | Calcul utilisable après sign-off externe complet |
| ESTIMATED | Sortie indicative, interdite pour un GO officiel |
| PRECALCULATED_SOURCE | Entrée pré-calculée hors moteur, interdite sans réconciliation signée |
| DEMO_ONLY | Sortie de démonstration ou export interne, interdite pour remise officielle |

Le validateur `corep_crr3.regulatory_dossier` bloque automatiquement un dossier `GO` si une ligne `ESTIMATED`, `PRECALCULATED_SOURCE` ou `DEMO_ONLY` reste dans la matrice.

## Scope officiel de remise vs scope interne

Le scope Enterprise complet peut contenir des moteurs internes, de démonstration ou reposant sur des sources pré-calculées. Le scope officiel de remise est donc calculé automatiquement dans `evidence/regulatory_dossier_v6_7_0.json` sous `official_submission_scope`.

Règle v6.7.0 : seuls les modules dont `quality_status = OFFICIAL` peuvent être activés dans un profil `official_submission`. Les lignes `ESTIMATED`, `PRECALCULATED_SOURCE` et `DEMO_ONLY` restent traçables mais sont exclues des remises officielles jusqu'à signature d'une preuve externe indépendante.

