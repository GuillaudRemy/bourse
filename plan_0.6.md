# Plan des versions 0.6.0 et 0.7.0

Décidé le 29/10/2026 à partir des propositions de `planv2.md` (parties B et C) et des demandes faites depuis.
Version publiée au moment de la décision : **0.5.3**.

---

## Version 0.6.0 — ≈ 5,5 jours · codée le 29/10/2026

Ce qui a été fait, et ce qui diffère du plan :

- **Colonnes fixes** : tableau des valeurs, Screener, positions et opérations du portefeuille. Un test d'interface
  vérifie que les en-têtes ne bougent pas après un tri, un changement de page ou une recherche.
- **Menu** : 5 entrées (Aujourd'hui, Marchés, Portefeuille, Outils, Aide) avec des sous-onglets sous la barre ;
  Réglages derrière l'icône d'engrenage. Pas de capture préalable : à valider pendant la recette, l'ordre et les
  libellés se changent en une ligne.
- **Taux européens** : Yahoo ne les fournit pas (Bund, OAT, BTP introuvables). Ils viennent de la **BCE** :
  taux de dépôt et taux à 10 ans de la zone euro (quotidiens), OAT, Bund, BTP et Bono 10 ans (moyennes
  **mensuelles**, seule série gratuite par pays). Taux américains 3 mois, 5, 10 et 30 ans par Yahoo.
- **Types ajoutés** : Devise (9 paires), Taux (11 séries), Obligations (6 ETF), Cryptomonnaie (4). Devises et taux
  n'ont pas de droite : leur fiche s'ouvre sur l'analyse technique ; un taux varie en **points** (« +0,30 pt »).
- **Taux sans risque** : zone euro AAA à 10 ans (BCE) pour des comptes en euros et autres devises, Trésor américain à
  10 ans pour des comptes en dollars. DCF par défaut = taux sans risque + prime de risque (réglage, 5 %), arrondi
  au demi-point, entre 6 et 15 %. Exemple au 28/10/2026 : 3,39 % + 5 % = 8,5 %.
- **Consensus** : un relevé par jour au plus, à chaque mise à jour complète et à l'ouverture de l'onglet Bénéfices ;
  historique par semaine sous le tableau des prévisions.
- **Réponses brutes** : dossier `brut/` à côté de la base, un sous-dossier par jour, purge à 30 jours et plafond de
  500 Mo. Taille visible dans À propos ; à mesurer pendant la recette (elle n'était pas connue d'avance).

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
- Valeurs : trier par PER, par nom, changer de page : les colonnes restent en place.
- Fiche d'une action, onglet Bénéfices : la ligne « Historique des prévisions » apparaît (premier relevé).
- À propos : taille des réponses brutes après une journée, puis après une « Tout mettre à jour ».

---

## Version 0.6.1 — le contenu prévu pour la 0.7.0 · codée le 29/10/2026, publiée en bêta (0.6.1-beta.1)

Publiée d'abord pour le seul PC où « Recevoir les versions bêta » vaut « oui » ; 0.6.1 pour tous ensuite, sur feu vert.

| Fait | Détail |
|---|---|
| **Simulateur de patrimoine** (Outils) | Versement mensuel, capital de départ, 5 à 40 ans, 5 placements (actions, obligations, or, fonds en euros, livret), modèles de répartition, 3 000 trajectoires, fourchette pessimiste / médiane / optimiste, option « euros d'aujourd'hui ». Chaque hypothèse peut être **mesurée sur une valeur suivie** (rendement réel sur 20 ans, dividendes réinvestis, en euros). |
| **Comptes européens d'avant 2020** | Archives de l'AMF (documents de référence depuis 2005 pour les sociétés cotées à Paris) : onglet Fondamentaux, une année = un clic, lecture assistée du PDF puis **relecture** avant enregistrement (≈ 40 s par document, 3 à 5 exercices chacun). Le PDF est rangé dans le journal, où l'assistant peut le lire. Autres pays européens : non couverts (pas d'archive gratuite équivalente trouvée). |
| **Seconde source de cours** | Euronext (Paris, Amsterdam, Bruxelles, Lisbonne, Milan, Oslo, Dublin) et Nasdaq (États-Unis) : clôtures des 2 dernières années comparées à Yahoo à chaque mise à jour complète. Stooq bloque désormais les téléchargements automatisés : écarté. Sur 11 actions de test : 10 vérifiées, 0 désaccord. |
| **Dividendes conservés** | Chaque dividende est gardé ; le rendement total est recalculé et comparé au cours ajusté de Yahoo (écart LVMH : 0,06 %). |
| **Contrôle qualité des comptes** | BPA ≠ bénéfice ÷ actions, bilan déséquilibré, variation × 5 d'une année sur l'autre, années manquantes ; score de confiance sur 100. A trouvé dès le premier essai une vraie erreur du dépôt ESEF 2022 de Capgemini (BPA et nombre d'actions × 1 000 000), désormais corrigée automatiquement à la lecture. |
| **Page « Couverture des données »** (Outils) | Profondeur des cours et des comptes, sources, ISIN / LEI, dividendes, incidents, corrections, par valeur. |
| **Actualisation robuste** | Nouvel essai automatique des échecs en fin de lot ; échecs d'affilée comptés ; après 5, une valeur « morte » n'est plus réessayée que par « Tout mettre à jour » ; badge « cotation arrêtée ? » dans Valeurs ; **journal des corrections** (séances retouchées par Yahoo, comptes révisés par leur source). |
| **Identifiants** | ISIN retrouvé par Euronext ; LEI exact par l'ISIN (GLEIF) avant la comparaison des noms. OpenFIGI : inutile pour l'instant. |
| **Assistant** | Connaît la taille de l'entreprise (CA, résultat, bilan) et ne qualifie de « majeur » qu'un fait de plus de 5 % environ. |
| **Typage** | 9 modules sur 14 sortis de la liste d'exceptions mypy ; plus aucun fichier d'interface sans `@ts-check`. |

**Reportés** (dépendent de vous ou d'un PC Windows) : relevés de courtiers (vrais relevés anonymisés nécessaires),
signature SignPath (candidature à votre nom), assistant sous Windows, test automatique du retour arrière Windows
(ne s'exécute que dans la chaîne de publication). Restent aussi 5 gros modules à typer (stockage, analyse, valeurs,
portefeuille, SEC : environ 250 corrections mécaniques).

## Ajouts de la 0.6.1-beta.3 (30/10/2026)

- **Cryptomonnaies en dollars** : BTC-USD, ETH-USD, SOL-USD, XRP-USD au catalogue ; toute crypto ajoutée dans une autre
  devise passe en dollars ; celles déjà suivies en euros sont converties à la mise à jour (cours retéléchargés).
  Si la paire en dollars était déjà suivie aussi, la paire en euros reste, à supprimer à la main.
- **Plus de type « Obligations »** : ce sont des ETF. Les valeurs passent en « ETF », et les ETF obligataires du
  catalogue s'ajoutent depuis la famille ETF ; leur mise en garde de lecture est conservée.
- **Menu** : Aujourd'hui et Marchés n'ont plus de sous-pages ; Outils (Screener, Comparer, Calendrier, Alertes,
  Simulateur, Backtest, Couverture des données) et Aide (Méthode, Glossaire, À propos) sont des **listes déroulantes** ;
  plus de seconde barre horizontale.
- **Correctif** : la contre-vérification faisait échouer l'ajout et la mise à jour complète des ETF cotés sur
  Euronext (fichier au format différent, ex. CAC.PA). Une panne de ce contrôle reste désormais un simple avertissement.

## Ajouts de la 0.6.1 (31/10/2026)

- **Fiche** : l'onglet Fondamentaux vient juste après Valorisation.
- **Aujourd'hui** : « À venir » passe au-dessus de « Dernières alertes ».
- **Favoris** : une étoile sur chaque valeur, tous types confondus (tableau et fiche). Les favoris passent en tête quand
  on trie par Valeur, dans les deux sens ; les autres tris les ignorent. Le tableau s'ouvre désormais trié par Valeur.

## Version 0.6.2 (31/10/2026)

- **Aujourd'hui ne parle que d'actions** : le logiciel est fait pour les actions individuelles, le reste est un bonus qui
  se suit dans Marchés et les Outils. Seul le portefeuille reste entier. Affiche les 10 prochaines échéances (sans limite
  de date), les 5 dernières alertes, les 5 actions les plus sous et les plus au-dessus de leur droite, les 5 plus fortes
  hausses et baisses.
- **Marchés** : étoile des favoris plus grande.

## Version 0.7.0 — reportés (état avant la 0.6.1)

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
