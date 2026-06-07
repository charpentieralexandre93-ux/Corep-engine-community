# SQL Community — SA et SA-CCR

Ce répertoire contient uniquement le bootstrap PostgreSQL requis par les deux
moteurs publics :

- **SA** : staging expositions/protections, règles CCF/RW, CRM, supporting factors,
  résultats et traces ;
- **SA-CCR** : staging des transactions, règles de pondération, résultats et traces.

Le manifeste `ACTIVE_SQL_MANIFEST.txt` est généré depuis le contrat
`COMMUNITY_SQL_CONTRACT.json`. Aucun schéma, seed ou mapping d'un moteur
Enterprise n'est distribué.

Les quatre couches transverses publiées (`schema_common_community`,
`domain_normalization_community`, `seed_common_reference_community` et
`mapping_credit_standard_community`) sont des variantes dédiées. Elles ne sont
pas des copies aveugles du socle Enterprise : les objets et mappings hors
périmètre public en ont été retirés.

## Initialisation

```bash
python -m pip install -e ".[postgres]"
python -m corep_crr3.community_bootstrap --list
python -m corep_crr3.community_bootstrap
```

Reset destructif, réservé à une base locale de développement :

```bash
python -m corep_crr3.community_bootstrap --reset --confirm-reset RESET
```

La table `meta.schema_migrations` conserve le checksum de chaque script. Un
bootstrap rejoué avec des scripts inchangés les ignore proprement.
