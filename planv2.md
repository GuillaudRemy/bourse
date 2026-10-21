# Plan v2 — Recette de la 0.5.0, puis fiabilité des données

Version de référence : **0.5.0** (21/10/2026).

Deux parties :

- **A. Recette** : tout ce qu'il faut tester à la main pour valider la 0.5.0, avec le résultat attendu.
  Chaque point indique ce que les tests automatiques couvrent déjà, pour concentrer l'effort sur le reste.
- **B. Améliorations**, en commençant par **la récupération des données**. Tout le reste en dépend : une
  droite tracée sur des cours faux est fausse, un score calculé sur des comptes incomplets ment.

Légende :

- 🤖 couvert par les tests automatiques (pytest, Playwright, test de mise à jour en CI) ;
- 👤 à tester à la main ;
- ⚠️ jamais testé en conditions réelles : à tester en priorité ;
- ⏱ estimation de l'effort.

---

## A. Recette de la 0.5.0

Cocher au fur et à mesure. En cas d'écart : noter la valeur, l'écran, le message exact, puis
télécharger le **diagnostic** (À propos → « Télécharger le diagnostic »). Il ne contient aucune donnée
personnelle.

### A.1 Installation et mises à jour — le plus important pour le PC de papa

| | Test | Comment | Attendu |
|---|---|---|---|
| [ ] | ⚠️👤 Mise à jour 0.4.0 → 0.5.0 sous **Windows** (PC de papa) | Lancer Bourse comme d'habitude | Téléchargement, installation silencieuse, relance en 0.5.0 (À propos). Données intactes : valeurs, portefeuille, journal |
| [ ] | ⚠️👤 Même chose sous **Ubuntu** (ton PC, actuellement en 0.3.0) | Lancer Bourse | 0.3.0 → 0.5.0 directement, données intactes |
| [ ] | 👤 Sauvegarde avant mise à jour | Dossier `sauvegardes` | Un fichier `avant-mise-a-jour-0.5.0.db` |
| [ ] | 🤖 Mise à jour falsifiée refusée | (couvert en CI, Windows et Linux) | — |
| [ ] | 🤖 Version défaillante abandonnée (Linux) | (couvert en CI) | — |
| [ ] | ⚠️👤 Retour arrière **Windows** si la nouvelle version plante au démarrage | Impossible à provoquer simplement : à surveiller lors des prochaines mises à jour | L'ancienne version se réinstalle seule |
| [ ] | 👤 Canal bêta | Réglages → « Recevoir les versions bêta » = oui sur TON PC, puis publier une `X.Y.Z-beta.1` | Ton PC l'installe, celui de papa non |
| [ ] | 👤 Installation neuve Windows | Télécharger `Bourse-Setup.exe` depuis GitHub sur un autre PC | Avertissement SmartScreen (normal, non signé), installation, icône sur le bureau, valeurs d'exemple |
| [ ] | 👤 Double lancement | Double-cliquer deux fois sur l'icône | Le navigateur s'ouvre sur l'application déjà lancée, pas de second serveur |
| [ ] | 👤 Sans internet | Couper le Wi-Fi, lancer | Démarrage normal, message « vérification des mises à jour impossible » |

**À faire une fois** : sauvegarder la clé de signature `~/.config/bourse-publication/cle_signature.txt`
(gestionnaire de mots de passe). Sans elle, plus aucune mise à jour ne peut être publiée.

### A.2 Données — la base de tout (voir aussi la partie B)

Pour chaque test : comparer avec une source de référence (Boursorama, Zonebourse, rapport annuel).

| | Test | Comment | Attendu |
|---|---|---|---|
| [ ] | 👤 Cours d'une action française | Ajouter TotalEnergies (TTE.PA), comparer le dernier cours et celui du 2 janvier 2015 avec Boursorama | Écart < 0,5 % (le cours non ajusté est la référence) |
| [ ] | 👤 Dividendes réinvestis | Droite de TTE.PA, cases « dividendes réinvestis » cochée puis décochée | Pente plus forte d'environ le rendement moyen (~5 %/an pour TotalEnergies) |
| [ ] | ⚠️👤 Division d'actions | Une valeur avec division récente (ex. NVDA 2024, LVMH non) : graphique sans marche d'escalier, BPA anciens divisés d'autant | Pas d'alerte « saut suspect » ; BPA cohérents avec le cours |
| [ ] | 👤 Comptes américains (SEC) | Apple : onglet Fondamentaux, années 2009 → aujourd'hui | Source « SEC » sur la plupart des cases ; CA 2025 = 416,2 Md$ |
| [ ] | ⚠️👤 Comptes européens (ESEF) | Air Liquide, L'Oréal, une petite valeur (ex. Manitou) | Années depuis 2020 avec source « ESEF » ; signaler toute case aberrante (×1000, signe inversé) |
| [ ] | 👤 Comptes anciens d'une valeur européenne | Importer un rapport annuel PDF de 2010 (onglet Fondamentaux → PDF) | Relecture proposée, chiffres corrects, provenance « pdf » |
| [ ] | 👤 Valeur cotée en pence (Londres) | Ajouter Unilever (ULVR.L) | Cours affichés en GBp, conversions en euros justes (÷100 puis taux BCE) |
| [ ] | 👤 Valeur en dollars + case « en euros » | Apple, case « en euros » | Courbe convertie au taux BCE de chaque jour |
| [ ] | 👤 Indice | CAC 40 (^FCHI) | Affiché en **points**, départ par défaut 1992, avertissement « indice hors dividendes » |
| [ ] | 👤 ETF | Amundi CAC 40 (CAC.PA) | Affiché en **euros** |
| [ ] | 👤 Import CSV de cours | Fiche → Données → importer un CSV de Boursorama ou d'Investing | Colonnes reconnues, séances importées |
| [ ] | 👤 Collage depuis un tableur | Fondamentaux → coller un tableau (années en colonnes) | Années et postes reconnus |
| [ ] | 👤 Contrôle qualité | Onglet Données & réglages | Liste des anomalies (trous, sauts, cours figés) compréhensible |
| [ ] | 👤 Actualisation de toutes les valeurs | Bouton Actualiser du tableau, avec 30 valeurs ou plus | Barre de progression, aucune valeur bloquée, échecs listés clairement |
| [ ] | ⚠️👤 Import d'un indice entier | Screener → importer le CAC 40, puis le S&P 500 (500 valeurs) | Toutes ajoutées ; Yahoo peut limiter le débit : noter le temps et les échecs |
| [ ] | 👤 Fraîcheur | Lendemain matin | Actualisation automatique au premier lancement de la journée |

### A.3 Analyse

| | Test | Comment | Attendu |
|---|---|---|---|
| [ ] | 🤖👤 Droite de régression | Air Liquide depuis 2003 | Pente ≈ 11 %/an, écart-type ≈ 10 %, couloir ±1/±2 σ, zone cohérente avec le graphique |
| [ ] | 👤 Date de début | Changer le début (2010) | Pente et couloir recalculés, la date est mémorisée |
| [ ] | 👤 Trois vérifications | Une valeur saine (Air Liquide) et une valeur cassée (Atos, Orpea/Emeis, Casino) | Verdict « fiable » pour l'une ; rupture détectée pour l'autre |
| [ ] | 👤 Projection | Case Projection | Cône qui s'élargit, probabilités de retour à la droite plausibles |
| [ ] | 👤 Analyse technique | Jour/semaine/mois, Ichimoku, ADX, stochastique, tracés (niveau, ligne de tendance, note) | Indicateurs justes (comparer le RSI avec Boursorama), tracés conservés après rechargement |
| [ ] | 👤 Bénéfices | Cours = BPA × PER médian | La ligne verte suit le cours pour une valeur saine |
| [ ] | 🤖👤 Qualité | Note /100, Piotroski, Altman, Beneish | Apple ≈ 90+ ; une valeur en difficulté nettement plus bas |
| [ ] | 👤 Valorisation | DCF, DCF inversé, Graham, Gordon, multiples historiques | Hypothèses modifiables, résultats qui réagissent |
| [ ] | 👤 Consensus des analystes | Onglet Bénéfices, une grande valeur et une petite | BPA attendus présents pour les grandes ; message clair pour les petites |
| [ ] | 👤 Screener | Filtres, score, filtres enregistrés | Résultats triables, filtre retrouvé au rechargement |
| [ ] | 👤 Comparer | 3 valeurs + indice, base 100 et force relative | Courbes alignées sur la même date de départ |
| [ ] | 🤖👤 Backtest | Règle −1σ / +1σ, frais automatiques | Pas de biais d'anticipation (couvert) ; résultats plausibles |

### A.4 Portefeuille et fiscalité

| | Test | Comment | Attendu |
|---|---|---|---|
| [ ] | 👤 Comptes PEA, CTO | Créer un PEA et un CTO, avec les frais de ton courtier (ex. 1 € + 0,1 %, minimum) | Frais proposés automatiquement à chaque achat |
| [ ] | 🤖👤 TTF | Achat d'une action française de plus d'1 Md€ (Air Liquide) dans le CTO | TTF de 0,4 % ajoutée ; pas de TTF sur un ETF ni sur une action étrangère |
| [ ] | 👤 PRU, plus-values, dividendes | Saisir quelques opérations réelles | Comparer avec le relevé du courtier |
| [ ] | 🤖👤 Import de relevé Degiro | Relevé réel | Opérations reconnues, valeurs retrouvées par ISIN |
| [ ] | ⚠️👤 Import de relevé d'un autre courtier | Boursorama, Fortuneo, Trade Republic, Bourse Direct… | Les formats n'ont jamais été testés avec de vrais fichiers : noter les colonnes non reconnues |
| [ ] | 👤 Performance | TWR, TRI, comparaison à l'indice de référence | Cohérent avec le relevé annuel du courtier |
| [ ] | 👤 Fiscalité | CTO : flat tax 31,4 % (2026) ; PEA > 5 ans : 18,6 % de prélèvements sociaux seulement | Montants cohérents avec la simulation de service-public.fr |
| [ ] | 👤 Exports | Excel du portefeuille, Excel et rapport PDF d'une fiche | Fichiers lisibles dans LibreOffice / Excel |

### A.5 Suivi au quotidien

| | Test | Comment | Attendu |
|---|---|---|---|
| [ ] | 👤 Page Aujourd'hui | Ouvrir après une actualisation | Hausses, baisses, opportunités sous la droite, événements à venir |
| [ ] | 👤 Alertes | Règle « cours sous X » proche du cours actuel, puis Actualiser | Alerte dans la cloche |
| [ ] | ⚠️👤 Notification de bureau **Windows** | Réglages → notifications de bureau = oui | Bulle Windows. Jamais testé sous Windows |
| [ ] | 👤 Notification de bureau Ubuntu | Idem | Notification GNOME |
| [ ] | ⚠️👤 E-mail d'alerte | Réglages SMTP (ex. Gmail avec mot de passe d'application) | E-mail reçu. Jamais testé avec un vrai serveur |
| [ ] | 👤 Calendrier | Page Calendrier | Résultats et dividendes à venir des valeurs suivies |
| [ ] | 👤 Actualités | Fiche → Journal / Assistant | Titres récents en français, liens qui s'ouvrent |
| [ ] | 👤 Journal | Thèse, décisions, pièces jointes (PDF de 50 Mo ou plus) | Tout est conservé ; PDF rouvrable |

### A.6 Confort, sauvegardes, partage

| | Test | Comment | Attendu |
|---|---|---|---|
| [ ] | 🤖👤 Ctrl+K | Taper un nom, Entrée | Fiche ouverte (même en tapant très vite) |
| [ ] | 👤 Thème sombre, taille du texte | Boutons en haut à droite | Tout est lisible, graphiques compris |
| [ ] | 👤 Aide et glossaire | « ? » à côté des chiffres | Définitions claires pour papa |
| [ ] | 👤 Visite guidée | Méthode → « Revoir la visite guidée » | 5 écrans compréhensibles |
| [ ] | 🤖👤 Sauvegarde externe | Réglages → dossier Google Drive ou clé USB ; À propos → Sauvegarder maintenant | Fichier dans `<dossier>/Bourse/` |
| [ ] | 🤖👤 Restauration | À propos → Restaurer une copie d'hier | Données d'hier ; copie « avant-restauration » créée |
| [ ] | 🤖👤 Partage entre PC | Exporter sur ton PC (sans portefeuille), importer sur celui de papa | Valeurs, thèses, listes ajoutées ; rien d'écrasé ; cours téléchargés ensuite |

### A.7 Assistant local (Ubuntu, avec Ollama)

| | Test | Comment | Attendu |
|---|---|---|---|
| [ ] | 👤 Visibilité | Avec puis sans Ollama lancé (`systemctl stop ollama`) | Onglet présent puis absent |
| [ ] | 👤 Rapport annuel | Un document d'enregistrement universel récent (≈ 2 à 3 min) | Points avec pages exactes : **vérifier 5 pages citées au hasard** |
| [ ] | 👤 Questions | « Pourquoi la note de qualité est-elle à ce niveau ? » | Chiffres identiques à ceux de l'onglet Qualité |
| [ ] | 👤 Actualités | Résumer | Synthèse fidèle aux titres (les ouvrir) |
| [ ] | 👤 Autre modèle | Réglages → `gemma4:e4b` | Fonctionne aussi (format plus approximatif) |

---

## B. Améliorations

### B.1 Récupération des données 🔴 — priorité absolue

**État actuel :**

| Donnée | Source | Couverture | Faiblesse |
|---|---|---|---|
| Cours quotidiens | Yahoo (yfinance) ; secours : API Yahoo directe | Monde, depuis l'introduction | **Une seule source réelle** : le secours, c'est encore Yahoo. Pas de contre-vérification |
| Cours ajusté (dividendes réinvestis) | Yahoo (colonne « adj close ») | Idem | Méthode de Yahoo, invérifiable ; retéléchargée en entier à chaque fois ; **les dividendes eux-mêmes ne sont pas conservés** |
| Divisions d'actions | Yahoo | Idem | Une division manquante crée une « marche » dans la courbe |
| Comptes USA | SEC companyfacts | 2009 → aujourd'hui | Bonne qualité ; postes parfois nommés autrement selon les sociétés |
| Comptes Europe | ESEF (filings.xbrl.org) | **2020 → aujourd'hui seulement** | Trou 2003-2019 : **la vérification n°2 (pente portée par les bénéfices) manque d'historique pour les valeurs européennes** |
| Comptes récents | Yahoo | 4-5 ans | Utilisés en dernier recours |
| Change | BCE | 1999 → aujourd'hui | Fiable |
| Indices | Wikipédia | Composition actuelle | Biais du survivant |
| Consensus | Yahoo | 2 exercices | Pas d'historique conservé |

**Améliorations, par ordre d'impact :**

#### B.1.1 Historique long des comptes européens (2003-2019) — ⏱ 4-6 j

C'est le plus gros manque pour la méthode. Pistes, de la plus fiable à la plus fragile :

1. **Rapports annuels officiels archivés par l'AMF**, en données ouvertes (echanges.dila.gouv.fr/OPENDATA/AMF,
   accessible, vérifié le 21/10/2026) : documents réglementés gratuits et officiels des sociétés cotées à Paris.
   Profondeur exacte de l'historique et format des index à étudier avant de chiffrer précisément.
2. **Lecture des tableaux « chiffres clés sur 5 ans »** présents dans chaque rapport : 4 rapports
   (2008, 2013, 2018, 2023) couvrent 20 ans. Extraction par l'outil PDF existant, puis par l'assistant local
   en secours (Ubuntu). **Relecture obligatoire avant enregistrement** (déjà le cas pour les imports PDF).
3. Repérer les **ruptures de normes comptables** (passage aux IFRS en 2005, IFRS 16 en 2019) : les
   signaler sur le graphique des BPA plutôt que de mélanger sans le dire.

#### B.1.2 Seconde source de cours, indépendante de Yahoo — ⏱ 2-3 j

1. **Choisir la seconde source** après un essai sur les valeurs suivies par papa. Ces sources demandent une
   clé gratuite (à saisir dans Réglages) et ont des quotas quotidiens, d'où leur rôle de contre-vérification
   plutôt que de source principale :
   - **Twelve Data** : bonne couverture européenne annoncée ;
   - **Alpha Vantage** : quota très bas ;
   - **Tiingo** : surtout les États-Unis.

   *Stooq, souvent cité, est écarté : vérifié le 21/10/2026, il impose désormais une vérification anti-robot.*
2. **Contrôle croisé automatique** à chaque actualisation : écart de plus de 1 % sur une séance entre les
   deux sources → anomalie signalée (souvent une division mal appliquée ou une erreur de Yahoo).
3. Option payante si le gratuit ne suffit pas : **EODHD** (monde entier, comptes sur 30 ans, dividendes et
   divisions propres ; tarif à vérifier selon l'offre). À n'envisager qu'après mesure des écarts réels.

#### B.1.3 Calculer nous-mêmes le rendement total — ⏱ 2 j

- **Conserver les dividendes** (nouvelle table : date de détachement, montant, devise) et les cours **non
  ajustés**.
- Calculer le cours « dividendes réinvestis » nous-mêmes, puis le comparer à celui de Yahoo : écart → anomalie.
- Bénéfices :
  - résultat reproductible et indépendant d'un changement de méthode de Yahoo ;
  - historique des dividendes affiché dans la fiche ;
  - rendement sur prix de revient dans le portefeuille ;
  - contrôle de cohérence avec le taux de distribution des comptes.

#### B.1.4 Actualisation incrémentale et traçable — ⏱ 2 j

- Ne télécharger que les **séances manquantes**, plus un recouvrement de 10 jours (contrôle). Aujourd'hui,
  tout l'historique est retéléchargé à chaque fois : lent, et cause des limitations de débit sur 500 valeurs.
- **Détecter les révisions** : un cours passé modifié par la source → journal des corrections et alerte
  si l'écart dépasse 0,5 %.
- **File d'attente avec reprise** : une valeur en échec (limitation de débit Yahoo) est réessayée plus tard,
  automatiquement.
- **Valeur « morte »** (aucune nouvelle séance depuis 10 jours de bourse : radiation, fusion, changement de
  symbole) → alerte et proposition de nouveau symbole (recherche par ISIN).

#### B.1.5 Contrôle qualité des comptes — ⏱ 2-3 j

Aujourd'hui, seuls les cours sont contrôlés. À ajouter :

- **Cohérences internes** :
  - BPA ≈ résultat net ÷ nombre d'actions (écart > 10 % → anomalie) ;
  - actif = passif ;
  - dividende ≤ BPA durablement (sinon : distribution non couverte).
- **Unités** : une case 1 000 fois plus grande ou plus petite que ses voisines (mélange milliers / millions
  entre sources) → anomalie.
- **Nombre d'actions** qui saute d'un facteur entier (×2, ×10) → division probablement non appliquée.
- **Désaccord entre sources** : SEC/ESEF contre Yahoo sur la même case, écart > 5 % → affiché, avec les
  deux valeurs, dans l'onglet Fondamentaux.
- **Score de confiance** des données (cours et comptes) affiché dans la fiche, et pris en compte par le
  verdict des trois vérifications.

#### B.1.6 Page « Couverture des données » — ⏱ 1-2 j

Un tableau de toutes les valeurs suivies, avec pour chacune :

- années de cours ;
- années de BPA ;
- sources utilisées ;
- dernière actualisation ;
- nombre d'anomalies ;
- score de confiance.

Pour voir d'un coup d'œil ce qui manque avant de se fier à une analyse, et trier par « le moins fiable d'abord ».

#### B.1.7 Identifiants fiables — ⏱ 1 j

- **ISIN → symbole** via OpenFIGI (gratuit) quand la recherche Yahoo échoue (fréquent pour les petites
  valeurs et les relevés de courtier).
- **LEI** via GLEIF (gratuit, officiel) au lieu de la comparaison de noms actuelle pour trouver les rapports ESEF.

#### B.1.8 Données complémentaires — ⏱ 1-2 j

- **Taux sans risque** (obligations d'État à 10 ans, BCE ; gratuit) pour un taux d'actualisation du DCF à jour,
  au lieu d'une valeur fixe.
- **Historique du consensus** : enregistrer chaque jour les BPA attendus, pour suivre les révisions au-delà
  des 90 jours fournis par Yahoo.
- **Compositions historiques des indices** (pour un backtest sans biais du survivant) : sources gratuites rares ;
  au minimum, conserver chaque mois la composition importée pour construire l'historique à partir de maintenant.

#### B.1.9 Reproductibilité — ⏱ 1 j

- Conserver les **réponses brutes** des sources (compressées, 30 jours) : permet de comprendre une
  anomalie après coup et de rejouer un calcul.
- Étendre les **cas de référence figés** (aujourd'hui : Apple/SEC) à une valeur européenne (ESEF) et à une
  série de cours avec division et dividendes connus.

### B.2 Autres améliorations

| Priorité | Amélioration | ⏱ |
|---|---|---|
| 🟠 | Formats de relevés de courtiers : collecter de vrais fichiers (anonymisés) de Boursorama, Fortuneo, Trade Republic, Bourse Direct, et en faire des tests | 2 j |
| 🟠 | Assistant sous Windows (Ollama existe sous Windows ; à tester sur le PC de papa : mémoire, carte graphique) | 1 j |
| 🟠 | Assistant : récupération automatique du rapport annuel (AMF, SEC), mutualisée avec B.1.1 | 1 j |
| 🟠 | Retour arrière Windows : test automatique avec une version volontairement défaillante | 1 j |
| 🟢 | Signature de code Windows (supprime SmartScreen) : candidature SignPath (gratuit) | 0,5 j + délai |
| 🟢 | Typage : retirer les 14 modules de la liste d'exceptions mypy, et les 5 fichiers sans `@ts-check` | 3 j |
| 🟢 | Résumé de l'assistant : mieux rendre les proportions (une dépréciation de 1 % du bilan n'est pas « majeure ») | 0,5 j |

---

## Ordre proposé

1. **Recette A.1 et A.2** dès maintenant : mises à jour sur les deux PC, et contrôle des données sur 5 à
   10 valeurs que papa suit vraiment.
2. **B.1.2 + B.1.3 + B.1.4** (seconde source, dividendes conservés, actualisation incrémentale) : la fiabilité
   des cours est la base de la droite.
3. **B.1.5 + B.1.6** (contrôle des comptes, page de couverture) : savoir ce qu'on peut croire.
4. **B.1.1** (historique long européen) : le chantier le plus long, mais celui qui rend la vérification n°2
   possible pour les valeurs françaises.
5. Le reste de la recette (A.3 à A.7) en parallèle, au fil de l'usage.
