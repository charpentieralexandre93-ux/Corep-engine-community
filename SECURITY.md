# Security policy — COREP CRR3 Engine Community

## Versions supportées
La dernière version mineure publiée reçoit les correctifs de sécurité.

## Signaler une vulnérabilité
Ne publiez jamais de jeton, mot de passe, clé privée ou fichier `.env` dans le
dépôt, et **n'ouvrez pas d'issue publique** pour une faille.

Utilisez le **signalement privé de vulnérabilité de GitHub** (onglet *Security*
du dépôt → *Report a vulnerability* / GitHub Security Advisories). Ce canal est
chiffré, privé et ne nécessite aucune adresse e-mail provisionnée. À défaut,
contactez de façon confidentielle le mainteneur via son profil GitHub.

Délai de première réponse visé : **72 heures** ; divulgation coordonnée.

## Périmètre prioritaire
Injection SQL, fuite de secrets, élévation de privilèges, dépendances vulnérables.

## Recommandations de déploiement sécurisé
- Secrets via coffre-fort : `PGPASSWORD_FILE` ou `PGPASSWORD_CMD` (jamais en clair).
- Rôles PostgreSQL en moindre privilège (lecture/écriture séparées).
- Chiffrement en transit (TLS) et au repos côté base.
- `pip-audit` / Dependabot activés ; mises à jour de sécurité appliquées.
