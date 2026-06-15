# Exploitation Community v6.0.0

La distribution publique couvre uniquement SA et SA-CCR. Avant publication ou
installation, vérifier le manifeste de release puis exécuter le diagnostic :

```bash
python -m corep_crr3.release_integrity --root . --manifest RELEASE_MANIFEST.json --version 6.0.0
corep-community-health --output-dir output --min-free-mb 100
```

Pour PostgreSQL, fournir `DATABASE_URL` par secret d'environnement. Ne jamais
utiliser le fichier `.env.example` comme secret de production. Le reset du
schéma est réservé aux environnements locaux ou éphémères et exige les garde-fous
prévus par le bootstrap Community.
