# Bourse

Analyse de cours de bourse et de fondamentaux, inspirée de la méthode des droites de régression
(échelle log, dividendes réinvestis, couloir à ±1 et ±2 écarts-types, trois vérifications avant
de prolonger la droite), avec les indicateurs techniques classiques.

- **Backend** : FastAPI · SQLModel · SQLite · pandas/numpy (dossier `backend/`)
- **Frontend** : React · Vite · react-router · lightweight-charts (dossier `frontend/`)
- **Données** : Yahoo Finance via [yfinance](https://github.com/ranaroussi/yfinance) — libre, gratuit, sans clé.
  Import CSV pour tout ce qu'aucune API ne couvre (cours d'une valeur absente, historique long de BPA).

## Lancer en développement

```bash
# backend (port 8010)
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/python -m backend.migrate
.venv/bin/python -m backend.seed          # facultatif : valeurs de la vidéo (Air Liquide, Dassault, OPmobility…)
.venv/bin/uvicorn backend.main:app --port 8010 --reload

# frontend (port 5173, /api relayé vers le backend)
cd frontend && npm install && npm run dev
```

Puis http://localhost:5173

## Version de bureau (Windows et Ubuntu) avec mise à jour automatique

Téléchargement : https://github.com/GuillaudRemy/bourse/releases/latest

- **Windows 10/11 (64 bits)** : `Bourse-Setup.exe`, puis l'icône « Bourse » du bureau.
  Au premier lancement, SmartScreen peut demander « Informations complémentaires » → « Exécuter quand même ».
- **Ubuntu 24.04 (x86_64)** : `tar xzf bourse-linux-x86_64.tar.gz && ./bourse/installer.sh`, puis l'icône « Bourse ».

À chaque lancement, l'application vérifie la dernière version publiée et se met à jour seule.
Les données sont rangées hors du programme (`%LOCALAPPDATA%\Bourse`, `~/.local/share/bourse`) :
une mise à jour ne les touche jamais.

**Publier une nouvelle version** :

```bash
git commit -am "…"
outils/publier.sh 0.2.0 "Ce qui change"
```

GitHub Actions construit alors les deux versions, les installe et les teste sur un vrai Windows et
un vrai Ubuntu 24.04 ; la publication n'est créée que si tout est vert.

## Lancer avec Docker

```bash
docker compose up -d --build
```

Puis http://localhost:8081. La base vit dans `donnees/`, une copie par jour va dans `sauvegardes/`.

## Ce que calcule l'application

| Onglet | Contenu |
|---|---|
| Droite de régression | Moindres carrés de ln(cours) sur le temps, depuis 2003 (actions) ou 1992 (indices) ; pente annuelle, écart-type, position en σ, zone, retour à la droite, projections, temps passé par zone vs loi normale |
| Fiabilité | 1. historique ≥ 20 ans · 2. pente portée par le BPA et non par la dérive du PER · 3. pas de rupture (pente récente vs pente longue, ou rupture signalée à la main) |
| Analyse technique | Bougies, MM20/50/200, Bollinger, volume, RSI 14, MACD 12/26/9, volatilité, perte maximale, croisements |
| Fondamentaux | Ratios Yahoo, tableau annuel éditable (BPA, bénéfice, CA, dividende, PER moyen calculé), import CSV |

## Formats CSV acceptés

Séparateur `;` `,` ou tabulation, virgule décimale, dates ISO ou JJ/MM/AAAA, en-têtes FR ou EN.

Cours (date + clôture obligatoires) :
```
date;ouverture;haut;bas;cloture;cloture_ajustee;volume
02/01/2003;31,20;31,85;31,02;31,70;12,41;1523400
```

Fondamentaux (année + au moins une colonne) :
```
annee;bpa;benefice_net;chiffre_affaires;dividende
2005;1,85;933M;10400M;0,75
```

Outil d'aide à l'analyse, pas un conseil en investissement.
