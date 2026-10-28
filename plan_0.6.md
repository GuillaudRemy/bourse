# Plan des versions 0.6.0 et 0.7.0

Décidé le 29/10/2026 à partir des propositions de `planv2.md` (parties B et C) et des demandes faites depuis.
Version publiée au moment de la décision : **0.5.3**.

---

## Version 0.6.0 — ≈ 5,5 jours

### 0. Colonnes de largeur fixe dans le tableau des valeurs — ≈ 0,5 j

Aujourd'hui, chaque colonne prend la largeur de son contenu le plus long **sur la page affichée**.
En changeant de page, ou en triant (par PER, par nom…), les lignes affichées changent, les colonnes
s'élargissent ou rétrécissent, et les en-têtes se déplacent sous la souris.

- Largeur **fixe** pour chaque colonne (`table-layout: fixed`), calculée pour le contenu le plus large
  possible : « 1 260 EUR », « Opportunité manifeste », « −42,8 % »…
- Rien ne doit bouger quand on trie, change de page, filtre ou recherche : vérifié automatiquement par un
  test d'interface qui compare la position des en-têtes avant et après chaque action.
- Un nom de société trop long est coupé proprement (« … »), avec le nom complet au survol.
- Même traitement pour le Screener et les tableaux du portefeuille.

### 1. Réorganiser le menu — ≈ 1 j

Le menu compte 9 entrées, et la 0.6.0 en ajouterait encore : il passe à 5 entrées.

| Entrée | Contenu |
|---|---|
| **Aujourd'hui** | Résumé du jour, alertes, calendrier |
| **Marchés** | Valeurs suivies, Screener, Comparer, puis les nouveaux types (point 2), par onglets |
| **Portefeuille** | Positions, performance, fiscalité |
| **Outils** | Backtest (et plus tard le simulateur de patrimoine) |
| **Aide** | Méthode, glossaire, à propos |

- Les **Réglages** passent derrière une icône, à côté du thème et de la taille du texte.
- Les adresses actuelles (`/valeurs`, `/screener`…) continuent de fonctionner : favoris et liens intacts.
- La recherche Ctrl+K couvre toutes les pages.
- À valider par une capture avant de figer : ordre des entrées, libellés.

### 2. Obligations, devises, cryptomonnaies — ≈ 2 j

Même mécanique que les matières premières de la 0.5.2 : un type par famille, ajout en un clic depuis
un catalogue, onglets d'entreprise masqués, avertissement de lecture adapté.

| Type | Exemples (symboles Yahoo) | Ce que la droite de régression vaut |
|---|---|---|
| **Devises** | EUR/USD, EUR/GBP, EUR/CHF, EUR/JPY | **Rien** : une devise n'a pas de tendance de fond. La droite est masquée ; on garde l'analyse technique et les comparaisons |
| **Taux (obligations d'État)** | Taux américains à 10 ans (^TNX) et 30 ans (^TYX) ; Bund et OAT à vérifier chez Yahoo | **Rien** pour un taux. On affiche le niveau et son évolution |
| **Obligations (via ETF obligataires)** | ETF d'obligations d'État et d'entreprises en euros | Utile, comme pour un ETF actions |
| **Cryptomonnaies** | BTC-EUR, ETH-EUR | **Avec prudence** : historique court (depuis 2014 pour le bitcoin), volatilité extrême. Avertissement fort |

À vérifier en début de chantier : quels taux européens Yahoo fournit réellement, et sur quelle profondeur.
Les obligations « en direct » (une ligne par émission) ne sont pas disponibles gratuitement : on passe par les
taux de référence et les ETF.

### 3. Taux, consensus, traçabilité — ≈ 2 j

- **Taux sans risque** : rendement des emprunts d'État à 10 ans (BCE, gratuit, quotidien). Il sert de taux de
  référence dans le DCF de l'onglet Valorisation, au lieu d'une valeur fixe. Il est aussi affiché comme repère
  (« le DCF suppose 8 % ; le taux sans risque est de 3,1 % »).
- **Historique du consensus** : les BPA attendus par les analystes sont enregistrés à chaque actualisation
  complète. Cela permet de voir leurs révisions sur des mois, au lieu des 90 jours fournis par Yahoo.
- **Réponses brutes conservées 30 jours** (compressées) : permet de comprendre une anomalie après coup et de
  rejouer un calcul. Taille estimée et purge automatique à mesurer.

### Recette de la 0.6.0

- Le menu à 5 entrées sur le PC de papa : tout se retrouve-t-il sans chercher ?
- Une devise, un taux, une cryptomonnaie ajoutés depuis le catalogue ; chiffres comparés à Boursorama.
- Le DCF d'une valeur avant et après le taux sans risque : écart expliqué.

---

## Version 0.7.0 — reportés

### Vos demandes

- **Simulateur de patrimoine** : versement mensuel de X €, répartition (ex. 25 % actions, obligations, or et
  fonds en euros), courbes sur 10, 15 et 20 ans, fourchette pessimiste / médiane / optimiste. ≈ 3 j.
  *Il s'appuiera sur les obligations et l'or arrivés en 0.5.2 et 0.6.0, et trouvera sa place dans « Outils ».*

### Données

| Amélioration | ⏱ |
|---|---|
| Comptes européens 2003-2019 (rapports archivés par l'AMF, tableaux « chiffres clés sur 5 ans ») | 5 j |
| Seconde source de cours pour contre-vérifier Yahoo | 2-3 j |
| Dividendes conservés, rendement total recalculé et comparé à Yahoo | 2 j |
| Contrôle qualité des comptes et score de confiance | 2-3 j |
| Page « Couverture des données » | 1-2 j |
| Actualisation robuste : valeurs « mortes », reprise automatique des échecs, journal des corrections | 1 j |
| Identifiants fiables (OpenFIGI, GLEIF) | 1 j |

### Divers

| Amélioration | ⏱ |
|---|---|
| Relevés de courtiers : Boursorama, Fortuneo, Trade Republic, Bourse Direct (vrais relevés anonymisés nécessaires) | 2 j |
| Assistant sous Windows, et récupération automatique du rapport annuel | 2 j |
| Signature de code Windows (candidature SignPath) | 0,5 j + délai |
| Qualité logicielle : test du retour arrière Windows, typage complet, proportions dans le résumé de l'assistant | 4 j |

---

## Point d'attention

`planv2.md` désigne la récupération des données comme la priorité absolue, et aucun des grands chantiers de
données n'est dans la 0.6.0. C'est un choix possible : la 0.6.0 élargit ce que l'application suit, et la 0.7.0
pourra être la version « données ». Mais si l'historique des comptes européens compte pour les valeurs
françaises de papa, il gagnerait à ne pas trop attendre.
