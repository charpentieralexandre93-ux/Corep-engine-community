# Registre des findings sécurité — Corep Engine v6.10.1
**Revue : audit bank-readiness v6.10.1 (18/07/2026, session d'ingénierie). Prochaine revue : à chaque release.**
Outils : bandit 1.9.4 (toutes sévérités), semgrep 1.170.0 (règles locales `.semgrep/rules.yml`), pip-audit 2.10.1.
Résultat global : **0 HIGH, 0 MEDIUM** (bandit) ; **0 finding** semgrep après statuts ; **0 vulnérabilité de dépendance connue** (pip-audit sur lock runtime, 18/07/2026).

## Findings bandit LOW (14) — Enterprise, tous statués
| # | Code | Localisation | Analyse | Décision |
|---|---|---|---|---|
| 1-10 | B110 try_except_pass (×10) | frontières externes documentées (chargements optionnels, sondes readiness — chaque site porte un commentaire `boundary:`) | Silences volontaires aux frontières : l'échec externe bascule sur un statut contrôlé fail-closed, jamais sur un résultat calculé | **Accepté** — pattern de frontière documenté dans le code |
| 11 | B105 hardcoded_password_string | `quality_gate.py:8` — `PASS = "PASS"` | Faux positif : libellé de statut de gate, aucun secret | **Accepté** (faux positif) |
| 12 | B404 import subprocess | `config_gui.py:49` | Lanceur GUI local : ouverture d'outils par l'utilisateur | **Accepté** — usage local assumé, arguments non issus de données externes |
| 13 | B603 subprocess sans shell | `config_gui.py:1398` | `Popen` en liste d'arguments (pas de shell) — c'est la forme sûre | **Accepté** — conforme à la règle `corep-no-shell-true` |
| 14 | B405 import xml.etree | `dpm_xbrl_exporter.py:32` | `ElementTree` utilisé pour la **construction** XBRL uniquement ; tout **parsing** entrant passe par `defusedxml` (imports ligne 34 et `eba_xbrl_csv.py`) — verrouillé par la règle semgrep `corep-xml-parse-stdlib` | **Accepté** — écriture seule ; parsing interdit par gate |

## Findings semgrep `corep-sql-fstring-execute` (2) — statués et annotés
| Localisation | Analyse | Décision |
|---|---|---|
| `ingestion.py:1265` — `TRUNCATE TABLE {current_table}` | `current_table` issu d'une liste interne fermée (tables staging du module), aucun input externe ; identifiant non paramétrable en SQL | **Accepté** — annoté `# nosemgrep` + `# nosec B608`, whitelist interne |
| `mapping_engine.py:149` — `SELECT * FROM {qualified}` | Table validée par whitelist en amont, `batch_id` paramétré (`%s`) | **Accepté** — annoté `# nosemgrep` + `# nosec B608`, commentaire whitelist en place |

## Édition Community
Sous-ensemble strict du périmètre ci-dessus (2 × B110 sur `sql_migrations.py`, mêmes justifications de frontière) ; semgrep : 0 finding ; pip-audit lock runtime Community : 0 vulnérabilité connue (18/07/2026).

## Règle de tenue du registre
Toute nouvelle annotation `# nosec` ou `# nosemgrep` dans le code DOIT être accompagnée d'une entrée ici (localisation, analyse, décision, date). Les entrées sont revues à chaque release ; une annotation sans entrée au registre est traitée comme une non-conformité de revue.
