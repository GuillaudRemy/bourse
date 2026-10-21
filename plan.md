# Plan de développement — Bourse

Objectif : passer d'un outil de lecture de la droite de régression à une application
complète et sérieuse d'**analyse d'entreprise en vue d'investir en bourse**.

Le principe directeur reste celui de la méthode : **« la droite donne le cadre, les comptes
la valident »**. Aujourd'hui, la droite est solide, mais les comptes sont le maillon faible.
La priorité est donc là.

Légende : 🔴 indispensable · 🟠 important · 🟢 confort · ⏱ effort estimé (j = jour de travail)

---

## 0. État actuel (v0.1.1)

**Ce qui marche :**
- régression log avec dividendes réinvestis, couloir ±1/±2σ, zones, répartition observée vs théorique ;
- les 3 vérifications (historique, PER, rupture) ;
- MM20/50/200, RSI, MACD, Bollinger ;
- import CSV ;
- applis Windows et Ubuntu avec mise à jour automatique, testées en CI.

**Limites connues, à traiter en premier :**

| Limite | Conséquence |
|---|---|
| Yahoo ne donne que **4–5 ans de comptes** | la vérification n°2 (PER) n'est presque jamais concluante sans import manuel |
| Une **seule source de données**, non officielle (yfinance) | si Yahoo change son site, plus d'actualisation |
| Les **indices sont « prix »** (^FCHI, ^GSPC) et non dividendes réinvestis | pente du CAC 40 sous-estimée (3,3 %/an au lieu d'environ 6–7 %) |
| Aucune **conversion de devises** | impossible de comparer une action US et une action française en euros |
| La **régression utilise tout l'historique**, futur compris | toute stratégie testée dessus serait biaisée (voir §6) |
| Mise à jour automatique Windows **non testée de bout en bout** | risque à la première vraie mise à jour |
| L'analyse est **recalculée à chaque affichage** | lent dès qu'on suit plus de 50 valeurs |

---

## 1. Fiabiliser les données 🔴

### 1.1 Plusieurs sources, une seule interface — ⏱ 3 j
- [ ] Créer une interface `Source` (cours, dividendes, comptes, fiche) ; `yahoo.py` en devient une implémentation.
- [ ] **SEC EDGAR – companyfacts** (gratuit, officiel, sans clé) : comptes XBRL des sociétés US depuis environ 2009 (BPA, résultat, CA, flux de trésorerie, dette…). Cela règle le problème des 4 ans pour les actions US.
- [ ] **filings.xbrl.org (ESEF)** : rapports annuels européens au format XBRL, obligatoires depuis 2020 (2021 pour certains), gratuits. Couvre les sociétés françaises.
- [ ] **Stooq** ou une autre source de cours de secours, si Yahoo tombe.
- [ ] Cascade de sources par donnée, avec la provenance affichée (« BPA 2015 : import manuel », « BPA 2023 : SEC »).

### 1.2 Historique long des comptes — ⏱ 3–5 j
- [ ] Import des **rapports annuels PDF** (tableaux du compte de résultat), avec correction manuelle assistée.
- [ ] Modèle de saisie « 20 ans d'un coup » : un tableur à coller, ou un CSV pré-rempli à compléter.
- [ ] Ajustement automatique du **BPA aux divisions d'actions** (split, actions gratuites) pour que la série reste comparable.

### 1.3 Contrôle qualité des données — ⏱ 2 j
- [ ] Détection des trous (séances manquantes), des sauts anormaux (split mal ajusté, erreur de cotation) et des cours à zéro.
- [ ] Rapport de qualité par valeur (« 3 anomalies détectées ») avant de tracer la droite.
- [ ] Indices **dividendes réinvestis** (CAC 40 GR, S&P 500 Total Return) proposés par défaut, avec un avertissement si l'utilisateur choisit un indice « prix ».

### 1.4 Devises — ⏱ 1–2 j
- [ ] Taux de change quotidiens (BCE, gratuit) stockés en base.
- [ ] Affichage au choix en devise d'origine ou en EUR ; pente « en euros » pour un investisseur français.

### 1.5 Robustesse réseau — ⏱ 1 j
- [ ] Nouvelles tentatives avec attente croissante, limitation du débit, délai d'expiration sur chaque appel Yahoo.
- [ ] Actualisation **en tâche de fond** avec barre de progression (aujourd'hui, « Tout actualiser » bloque l'écran).
- [ ] Actualisation automatique quotidienne au lancement si les données ont plus d'un jour.

---

## 2. Analyse fondamentale complète 🔴

C'est le cœur d'une application « sérieuse » : il faut les **trois états financiers sur 10–20 ans**.

### 2.1 États financiers — ⏱ 4 j
- [ ] **Compte de résultat** : CA, EBITDA, EBIT, résultat net, BPA dilué, nombre d'actions.
- [ ] **Bilan** : capitaux propres, dette financière, trésorerie, actifs incorporels/goodwill, BFR.
- [ ] **Flux de trésorerie** : flux opérationnel, capex, **free cash flow**, dividendes versés, rachats d'actions.
- [ ] Tableaux pluriannuels avec graphiques en barres et croissance annuelle.

### 2.2 Ratios de qualité — ⏱ 2 j
- [ ] Marges brute, opérationnelle et nette, et leur **stabilité** (écart-type sur 10 ans).
- [ ] **ROE, ROIC, ROCE** : création de valeur au-dessus du coût du capital.
- [ ] Dette nette / EBITDA, gearing, couverture des intérêts.
- [ ] **FCF / résultat net** (qualité des bénéfices), capex / CA.
- [ ] Taux de distribution (payout), croissance du dividende, années consécutives sans baisse.
- [ ] **Dilution** : évolution du nombre d'actions (rachats ou émissions).
- [ ] Croissances annualisées sur 5 et 10 ans : CA, BPA, FCF, dividende.

### 2.3 Scores synthétiques — ⏱ 1–2 j
- [ ] **Piotroski F-score** (solidité, 0–9).
- [ ] **Altman Z-score** (risque de faillite).
- [ ] **Beneish M-score** (risque de manipulation comptable).
- [ ] Note de qualité maison, transparente et détaillée critère par critère.

### 2.4 Renforcer les 3 vérifications de la méthode — ⏱ 3 j
- [ ] **Graphique « cours vs BPA × PER médian »** : on voit immédiatement si le cours suit les bénéfices ou s'en écarte (renotation).
- [ ] **Droite de régression du BPA** (même méthode, appliquée aux bénéfices), à comparer à la pente du cours.
- [ ] **Bande de PER historique** (PER min / médian / max sur 20 ans) superposée au cours.
- [ ] **Détection de rupture statistique** (test de Chow, bibliothèque `ruptures`) en complément de la comparaison pente récente / pente longue.
- [ ] **Sensibilité au point de départ** : pente recalculée pour chaque année de départ possible (2000 → 2010). Si elle varie beaucoup, la droite est fragile.
- [ ] **Pente glissante** : pente sur 15 ans recalculée chaque année, en graphique, pour voir si le « rythme de croisière » ralentit.
- [ ] Exceptions sectorielles du transcript : banques et défense avec un départ plus ancien par défaut (paramétrable par secteur).

---

## 3. Valorisation 🟠

### 3.1 Multiples — ⏱ 2 j
- [ ] PER, PER prévisionnel, **VE/EBITDA, VE/EBIT**, P/B, P/FCF, rendement du FCF, rendement du dividende.
- [ ] Chaque multiple comparé à **son propre historique** (percentile sur 10–20 ans), comme la droite le fait pour le cours.
- [ ] Comparaison aux **pairs du secteur** (médiane sectorielle).

### 3.2 Modèles — ⏱ 3 j
- [ ] **DCF simple** (FCF, croissance, taux d'actualisation, valeur terminale), avec curseurs.
- [ ] **DCF inversé** : « quelle croissance le cours actuel suppose-t-il ? ». C'est le plus utile en pratique.
- [ ] Modèle de dividendes (Gordon) pour les valeurs de rendement.
- [ ] Nombre de Graham, PEG.
- [ ] **Marge de sécurité** : écart entre le cours et les différentes valeurs estimées, présentées ensemble (fourchette, pas un chiffre unique).

### 3.3 Projection probabiliste — ⏱ 2 j
- [ ] Cône de projection de la droite (±1σ, ±2σ dans le futur) au lieu d'une simple ligne.
- [ ] **Simulation de Monte-Carlo** log-normale, puis à queues épaisses (loi de Student) : distribution des rendements à 5 et 10 ans.
- [ ] Probabilité estimée de retour à la droite selon l'horizon, mesurée sur l'historique de la valeur.

---

## 4. Screener et comparaison 🟠

### 4.1 Univers de valeurs — ⏱ 2 j
- [ ] Import en un clic des composants du CAC 40, du SBF 120, du Stoxx 600, du S&P 500.
- [ ] Recherche par ISIN (indispensable pour un investisseur français : PEA, relevés de courtier).
- [ ] Listes personnelles (« À surveiller », « PEA », « Rendement »…).

### 4.2 Filtres et classement — ⏱ 3 j
- [ ] Filtres combinables : zone (≤ −1σ), pente ≥ 8 %, écart-type ≤ 30 %, fiabilité « Fiable », ROIC ≥ 12 %, dette nette/EBITDA ≤ 2…
- [ ] Filtres enregistrés (« Belles entreprises sous leur droite »).
- [ ] Score composite configurable : tendance + qualité + valorisation.

### 4.3 Comparaison — ⏱ 2 j
- [ ] Plusieurs valeurs sur un même graphique (base 100, échelle log).
- [ ] Force relative vs indice ou vs secteur.
- [ ] Tableau côte à côte de 2 à 5 entreprises (ratios, croissance, valorisation).

---

## 5. Portefeuille 🟠

### 5.1 Suivi des positions — ⏱ 4 j
- [ ] Transactions : achat, vente, dividende, frais, division d'actions.
- [ ] Prix de revient unitaire (PRU), plus-values latentes et réalisées, dividendes encaissés.
- [ ] **Import des relevés de courtier** (Boursorama, Fortuneo, Degiro, Trade Republic, Bourse Direct).
- [ ] Plusieurs comptes : **PEA, CTO**, assurance-vie.

### 5.2 Performance et risque — ⏱ 3 j
- [ ] Performance pondérée par le temps (TWR) et par l'argent (TRI / XIRR).
- [ ] Comparaison à un indice dividendes réinvestis.
- [ ] Répartition par secteur, pays et devise ; concentration (poids de la 1ʳᵉ ligne, des 5 premières).
- [ ] Volatilité, perte maximale, bêta, corrélations entre lignes.
- [ ] Position de chaque ligne dans son couloir (« 3 lignes en surévaluation manifeste »).

### 5.3 Fiscalité française 🟢 — ⏱ 2 j
- [ ] Plafond PEA (150 000 €), date d'ouverture et ancienneté (5 ans), éligibilité des titres au PEA.
- [ ] Estimation de l'imposition à la flat tax (31,4 % depuis 2026 : 12,8 % d'impôt + 18,6 % de prélèvements sociaux ; 30 % jusqu'en 2025) sur le CTO, avec l'option du barème progressif ; PEA : prélèvements sociaux seuls après 5 ans.
- [ ] Récapitulatif annuel pour aider à vérifier l'IFU.

---

## 6. Backtesting 🟢 — ⏱ 4 j

Pour **vérifier que la méthode fonctionne** avant d'y croire.

- [ ] Règles simples : acheter sous −1σ ou −2σ, alléger au-dessus de +1σ ou +2σ, conserver sinon.
- [ ] ⚠️ **Sans biais d'anticipation** : la droite doit être recalculée **uniquement avec les données disponibles à chaque date** (fenêtre croissante). La droite actuelle « connaît le futur » ; un backtest naïf serait faussé.
- [ ] Frais de courtage, taxes, dividendes réinvestis.
- [ ] Comparaison à « acheter et conserver » et à l'indice.
- [ ] Résultats sur tout un univers (CAC 40 historique), pas sur une valeur choisie après coup (biais du survivant : inclure les sociétés sorties de l'indice).

---

## 7. Alertes, calendrier, informations 🟠

- [ ] **Alertes** : passage sous −1σ / −2σ, RSI < 30, croisement MM50/MM200, cours cible atteint. ⏱ 2 j
- [ ] Notification : bureau (Windows / Ubuntu), et e-mail en option.
- [ ] **Calendrier** : dates de résultats, de détachement et de paiement des dividendes, assemblées générales. ⏱ 1 j
- [ ] **Actualités** par valeur (flux RSS, communiqués, publications AMF). ⏱ 2 j
- [ ] Résumé du jour au lancement : ce qui a bougé dans la liste suivie, alertes déclenchées.

---

## 8. Journal d'investissement 🟠 — ⏱ 3 j

Ce qui distingue l'investisseur méthodique : **écrire sa thèse avant d'acheter**.

- [ ] Fiche « thèse » par valeur : pourquoi j'achète, avantage concurrentiel, risques, prix d'achat visé, conditions de vente.
- [ ] **Checklist qualitative** inspirée du transcript : avantage concurrentiel durable ? Position concurrentielle menacée ? Changement de nature de l'entreprise (rupture) ? Management ?
- [ ] Pièces jointes : rapports annuels, présentations (reprendre le module « pièces » du projet exemple).
- [ ] Historique des décisions, avec relecture a posteriori (« ma thèse s'est-elle vérifiée ? »).

---

## 9. Analyse technique (compléments) 🟢 — ⏱ 2–3 j

- [ ] Stochastique, ATR, ADX, Ichimoku, OBV, volume moyen.
- [ ] Unités de temps hebdomadaire et mensuelle (indispensable pour le long terme).
- [ ] Outils de tracé : lignes de tendance, supports et résistances, annotations enregistrées.
- [ ] Paramètres modifiables (périodes des moyennes, du RSI…).

---

## 10. Interface et confort 🟢

- [ ] **Mode sombre** (les jetons CSS sont déjà en place). ⏱ 0,5 j
- [ ] Barre de recherche globale (Ctrl+K) pour ouvrir n'importe quelle valeur. ⏱ 0,5 j
- [ ] **Aide contextuelle** : un « ? » à côté de chaque indicateur qui explique ce qu'il mesure et comment le lire, plus un glossaire. ⏱ 2 j
- [ ] Première utilisation guidée (pour ton père). ⏱ 1 j
- [ ] **Export PDF de la fiche** d'une valeur, et export Excel des tableaux. ⏱ 2 j
- [ ] Taille de police réglable, pour le confort de lecture. ⏱ 0,5 j
- [ ] Graphiques en vue réduite (hebdomadaire) au-delà de 10 ans affichés, pour alléger. ⏱ 0,5 j

---

## 11. Qualité logicielle 🔴

### 11.1 Tests — ⏱ 3 j
- [ ] Couverture de l'analyse (régression, fiabilité, indicateurs) avec cas de référence chiffrés (Air Liquide ≈ 11 %/an, ≈ 10 % d'écart-type).
- [ ] Tests sur données réelles figées (fichiers de référence), sans réseau.
- [ ] Tests de l'interface (Playwright) : ajout d'une valeur, import, navigation.
- [ ] **Test de mise à jour en CI** : installer la version N−1, publier N, vérifier la bascule (Windows et Linux).

### 11.2 Code — ⏱ 2 j
- [ ] Linter et formatage : `ruff` (Python), `eslint` + `prettier` (JS), vérifiés en CI.
- [ ] Typage : `mypy` côté backend ; passage progressif du frontend en TypeScript.
- [ ] **Migrations Alembic** à la place du script maison, dès que le schéma évolue (états financiers, portefeuille).

### 11.3 Performance — ⏱ 2 j
- [ ] **Cache des analyses** (recalcul seulement quand les cours changent).
- [ ] Mode WAL de SQLite, index revus.
- [ ] Tableau de synthèse calculé une fois après l'actualisation, pas à chaque affichage.

### 11.4 Diagnostic — ⏱ 1 j
- [ ] Journal d'événements dans un fichier (dossier de données), avec rotation.
- [ ] Bouton « Envoyer le diagnostic » qui prépare un zip (journal + versions, sans données personnelles) : indispensable pour dépanner ton père à distance.
- [ ] Page « À propos » : version, dossier des données, date de la dernière actualisation.

---

## 12. Distribution et sécurité 🔴

- [ ] **Vérification d'intégrité des mises à jour** : publier une somme SHA-256 (idéalement une signature) avec chaque version, et la vérifier avant d'installer. Aujourd'hui, l'appli exécute ce qu'elle télécharge ; seul le HTTPS de GitHub la protège. ⏱ 1 j
- [ ] **Signature de code Windows** : supprime l'avertissement SmartScreen. Payant (certificat, ou Azure Trusted Signing pour environ 10 $/mois). ⏱ 1 j + coût
- [ ] **Retour arrière** : garder la version précédente et y revenir automatiquement si la nouvelle ne démarre pas. ⏱ 1 j
- [ ] Canal « bêta » : tu testes une version avant qu'elle n'arrive chez ton père. ⏱ 0,5 j
- [ ] Sauvegarde externe facultative (dossier synchronisé : Google Drive, OneDrive…) en plus des copies locales. ⏱ 1 j
- [ ] Version **macOS** si besoin (même principe, Python autonome). ⏱ 2 j
- [ ] Mention légale visible : outil d'aide à l'analyse, pas un conseil en investissement ; données Yahoo pour un usage personnel.

---

## 13. Pistes avancées 🟢

- [ ] **Assistant IA** (Claude) qui lit un rapport annuel et en résume les risques, les changements de stratégie ou les signaux de rupture. Cela sert directement la vérification n°3. À garder comme aide, jamais comme décision.
- [ ] Données de consensus des analystes (BPA prévisionnels, révisions).
- [ ] Données ESG.
- [ ] Synchronisation entre plusieurs PC (toi et ton père qui partagez les mêmes fiches).

---

## Ordre de réalisation proposé

| Phase | Contenu | Durée indicative |
|---|---|---|
| **1. Fondations fiables** | §1.1 SEC + ESEF · §1.3 qualité · §1.5 réseau · §11.4 diagnostic · §12 intégrité + retour arrière · test de mise à jour en CI | 2–3 semaines |
| **2. Les comptes** | §2.1 états financiers · §2.2 ratios · §2.4 vérifications renforcées · §1.2 import long historique | 3 semaines |
| **3. Décider** | §3 valorisation · §8 journal / thèse · §1.4 devises | 2–3 semaines |
| **4. Suivre** | §5 portefeuille · §7 alertes et calendrier | 3 semaines |
| **5. Chercher** | §4 screener · §6 backtesting | 3 semaines |
| **6. Finitions** | §9 technique · §10 interface · §11.2–11.3 · §13 | au fil de l'eau |

**Gains rapides** (moins d'une journée chacun, à glisser entre deux phases) : indices dividendes
réinvestis par défaut, mode sombre, recherche Ctrl+K, page « À propos », sommes SHA-256 des
publications, unité de temps hebdomadaire.
