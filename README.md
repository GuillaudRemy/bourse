# Bourse

Analyse de cours de bourse et de fondamentaux, inspirée de la méthode des droites de régression
(échelle log, dividendes réinvestis, couloir à ±1 et ±2 écarts-types, trois vérifications avant
de prolonger la droite), avec les indicateurs techniques classiques.

- **Backend** : FastAPI · SQLModel · SQLite · pandas/numpy (dossier `backend/`)
- **Frontend** : React · Vite · react-router · lightweight-charts (dossier `frontend/`)
- **Données** (toutes gratuites) :
  - cours, dividendes, divisions : Yahoo Finance via [yfinance](https://github.com/ranaroussi/yfinance), avec un secours
    direct sur l'API « chart » de Yahoo si la bibliothèque casse ;
  - comptes officiels américains : **SEC EDGAR** (15–19 ans ; renseigner un e-mail de contact dans Réglages, exigé par la SEC) ;
  - comptes officiels européens : **ESEF** via filings.xbrl.org (depuis 2020) ;
  - taux de change : **BCE** ;
  - et pour le reste : import CSV, collage depuis un tableur, extraction assistée de rapports annuels PDF.
  Chaque chiffre garde sa provenance ; une saisie manuelle n'est jamais écrasée.

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
Chaque publication est aussi testée en mise à jour (version précédente → nouvelle, données
conservées, mise à jour falsifiée refusée, version défaillante abandonnée).

**Version bêta** : `outils/publier.sh 0.6.0-beta.1 "…"` crée une pré-version GitHub, installée
uniquement là où le réglage « Recevoir les versions bêta » vaut « oui ».

### Sécurité des mises à jour

- Chaque publication contient `SHA256SUMS` et sa signature Ed25519 `SHA256SUMS.sig`, faite par la
  CI avec le secret GitHub `CLE_SIGNATURE`. L'application ne connaît que la clé publique
  (`backend/mise_a_jour.py`) : un fichier non signé par cette clé n'est jamais installé.
  Vérification manuelle : `python outils/signer.py --verifier <dossier contenant les fichiers>`.
- **La clé privée** est aussi gardée dans `~/.config/bourse-publication/cle_signature.txt` sur le
  PC de développement. **Sauvegardez-la** (gestionnaire de mots de passe) : sans elle, plus aucune
  mise à jour ne pourra être publiée vers les installations existantes.
- **Retour arrière** : avant sa première migration, la nouvelle version copie la base. Si elle ne
  démarre pas, la base est restaurée et l'ancienne version réinstallée ; la version fautive n'est
  plus proposée. Sous Linux, la nouvelle version est d'abord essayée sur une copie des données,
  avant de remplacer l'ancienne.

### Signature de code Windows (facultative)

Sans signature, Windows affiche « Windows a protégé votre ordinateur » au premier lancement de
l'installateur téléchargé (les mises à jour automatiques ne sont pas concernées). L'étape est
prête dans `.github/workflows/publier.yml` et s'active ainsi, avec Azure Artifact Signing
(anciennement Trusted Signing, environ 10 $/mois, vérification d'identité) :

1. Créer le compte de signature et le profil de certificat dans Azure, et une application
   (App Registration) ayant le rôle « Artifact Signing Certificate Profile Signer ».
2. Secrets du dépôt : `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`.
3. Variables du dépôt : `SIGNATURE_ENDPOINT` (ex. `https://weu.codesigning.azure.net/`),
   `SIGNATURE_COMPTE`, `SIGNATURE_PROFIL`, puis `SIGNATURE_WINDOWS` = `oui`.

Alternative gratuite pour les projets libres : [SignPath Foundation](https://signpath.org/), sur candidature.


## Ce que calcule l'application

| Onglet | Contenu |
|---|---|
| Droite de régression | Moindres carrés de ln(cours) sur le temps, depuis 2003 (actions) ou 1992 (indices, banques, défense) ; pente, écart-type, position en σ, zone, projections, temps par zone vs loi normale ; robustesse : pente selon le point de départ, pente glissante sur 15 ans, détection de rupture ; option « en euros » |
| Fiabilité | 1. historique ≥ 20 ans · 2. pente portée par le BPA et non par la dérive du PER · 3. pas de rupture (pente récente vs pente longue, ou rupture signalée à la main) |
| Analyse technique | Bougies, MM20/50/200, Bollinger, volume, RSI 14, MACD 12/26/9, volatilité, perte maximale, croisements |
| Bénéfices | Cours face à BPA × PER médian, bande de PER historique, droite du BPA (vérification n°2) |
| Qualité | Marges, ROE, ROIC, ROCE, dette, FCF, dilution ; scores Piotroski, Altman, Beneish ; note de qualité détaillée |
| Fondamentaux | Compte de résultat, bilan et flux sur 20 ans, éditables case par case, provenance colorée |
| Valorisation | Multiples (PER, VE/EBITDA, P/FCF…) situés dans leur historique et face au secteur ; DCF, DCF inversé, Gordon, Graham, PEG avec hypothèses réglables |
| Journal | Thèse d'investissement, checklist, décisions et relecture, documents joints, alertes de la valeur, actualités |
| Données & réglages | Imports, identifiants (ISIN, LEI, CIK), contrôle qualité des cours, rupture signalée à la main |

## Pages

- **Aujourd'hui** : portefeuille du jour, valeurs sous leur droite ou tout en haut du couloir, plus fortes variations, alertes, événements à venir.
- **Portefeuille** : comptes (PEA, compte-titres…), opérations (saisie ou import du relevé du courtier), positions avec PRU,
  performance (TWR et TRI) face à un indice de référence, risque, corrélations, répartition, fiscalité (plafond et ancienneté du PEA, flat tax du CTO).
- **Calendrier** : publications de résultats et dividendes. **Alertes** : position dans le couloir, RSI, cours, croisements de moyennes,
  notifiées dans l'application, sur le bureau et par e-mail.

## Assistant local (facultatif, Ubuntu)

Un onglet « Assistant » apparaît dans chaque fiche si [Ollama](https://ollama.com) tourne sur le PC avec
au moins un modèle (`ollama pull qwen3.5:9b` conseillé ; une carte graphique de 8 Go ou plus le rend rapide).
Tout reste sur l'ordinateur : l'application refuse toute adresse d'Ollama non locale.

- **Lire un rapport annuel** (PDF, rangé dans le journal) : pages utiles repérées par mots-clés, points relevés
  avec leur page, résumé, risques, stratégie, perspectives, signaux à examiner pour la vérification n°3, et
  questions à vérifier soi-même. Environ 2 à 3 minutes pour un document de 400 pages.
- **Questions sur la fiche** : réponses à partir des seuls chiffres calculés par l'application.
- **Résumé des actualités** : à partir des titres des 60 derniers jours.

Choix délibérés, après essais sur de vrais rapports : pas de verdict de rupture produit par le modèle (il ne sait
pas juger la portée d'un fait), et pas de dépendance au format JSON (ignoré par certains modèles sur de longs
textes). Modèle réglable dans Réglages (« Assistant : modèle Ollama »).

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
