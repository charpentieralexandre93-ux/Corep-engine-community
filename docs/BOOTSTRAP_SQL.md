# Bootstrap SQL Community — v6.10.0

L'édition Community expose uniquement le périmètre public : SA et SA-CCR.
Le bootstrap applique une base PostgreSQL commune avec :

```text
socle commun public + schema/seed/mapping des moteurs publics actifs + post-seed
```

## Commandes recommandées

Lister tout le bootstrap public :

```bash
python -m corep_crr3.community_bootstrap --list
```

Lister un moteur public isolé :

```bash
python -m corep_crr3.community_bootstrap --engine run_sa --list
python -m corep_crr3.community_bootstrap --engine run_saccr --list
```

Générer un manifeste moteur sans toucher à la base :

```bash
python -m corep_crr3.community_bootstrap --engine run_saccr --write-manifest
```

## Règle d'architecture

Community reste stricte : aucune seed, table ou mapping Enterprise ne doit être
référencé dans son contrat SQL. Le contrat distribué est :

```text
src/corep_crr3/sql/COMMUNITY_SQL_CONTRACT.json
```

Un moteur public activé correspond à son triptyque SQL :

```text
schema + seed + mapping
```

Les groupes `always` et `post_seed` sont communs et restent appliqués pour tout
bootstrap moteur.
