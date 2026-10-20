# TODO — mise en œuvre de plan.md

Coché = fait, testé et commité. Les numéros renvoient aux sections de `plan.md`.

## Phase 0 — Préparation
- [x] 0.1 Ranger le dépôt (ignorer `bourse/` extrait, `liens.txt` laissé tel quel)
- [x] 0.2 Linters en CI : ruff (Python), eslint (JS) — §11.2
- [x] 0.3 Migrations Alembic (base existante reprise sans perte) — §11.2

## Phase 1 — Données fiables
- [x] 1.1 Interface `Source` commune + registre des sources — §1.1
- [x] 1.2 SEC EDGAR companyfacts : comptes US sur 15 ans — §1.1
- [x] 1.3 ESEF (filings.xbrl.org + GLEIF) : comptes européens depuis 2020 — §1.1
- [x] 1.4 Source de cours de secours si Yahoo tombe — §1.1
- [x] 1.5 Provenance affichée pour chaque donnée annuelle — §1.1
- [x] 1.6 Ajustement du BPA aux divisions d'actions — §1.2
- [x] 1.7 Collage « 20 ans d'un coup » depuis un tableur — §1.2
- [x] 1.8 Import assisté de rapports annuels PDF — §1.2
- [x] 1.9 Contrôle qualité des cours (trous, sauts, zéros) + rapport — §1.3
- [x] 1.10 Indices dividendes réinvestis par défaut + avertissement indice « prix » — §1.3
- [x] 1.11 Taux de change BCE + affichage en EUR — §1.4
- [x] 1.12 Réseau : nouvelles tentatives, délais, limitation de débit — §1.5
- [ ] 1.13 Actualisation en tâche de fond avec progression + auto quotidienne — §1.5 — EN COURS : backend + barre de progression écrits et testés, reste la vérification visuelle

## Phase 2 — Les comptes
- [x] 2.1 États financiers complets (résultat, bilan, flux) en base et depuis les sources — §2.1
- [x] 2.2 Tableaux pluriannuels + graphiques en barres — §2.1
- [ ] 2.3 Ratios de qualité (marges, ROE, ROIC, ROCE, dette, FCF, payout, dilution, CAGR) — §2.2
- [ ] 2.4 Scores Piotroski, Altman, Beneish + note maison détaillée — §2.3
- [ ] 2.5 Graphique cours vs BPA × PER médian + bande de PER — §2.4
- [ ] 2.6 Droite de régression du BPA — §2.4
- [ ] 2.7 Détection de rupture statistique — §2.4
- [ ] 2.8 Sensibilité au point de départ + pente glissante — §2.4
- [ ] 2.9 Départ par défaut selon le secteur (banques, défense) — §2.4

## Phase 3 — Décider
- [ ] 3.1 Multiples (VE/EBITDA, VE/EBIT, P/B, P/FCF…) + percentile historique + médiane du secteur — §3.1
- [ ] 3.2 DCF, DCF inversé, Gordon, Graham, PEG, marge de sécurité — §3.2
- [ ] 3.3 Cône de projection, Monte-Carlo (normale, Student), probabilité de retour — §3.3
- [ ] 3.4 Journal : thèse, checklist, pièces jointes, décisions et relecture — §8

## Phase 4 — Suivre
- [ ] 4.1 Portefeuille : comptes, transactions, PRU, plus-values, dividendes — §5.1
- [ ] 4.2 Import des relevés de courtier — §5.1
- [ ] 4.3 Performance TWR / XIRR, indice de référence, répartition, risque — §5.2
- [ ] 4.4 Fiscalité PEA / CTO — §5.3
- [ ] 4.5 Alertes + notifications bureau / e-mail — §7
- [ ] 4.6 Calendrier (résultats, dividendes) — §7
- [ ] 4.7 Actualités par valeur — §7
- [ ] 4.8 Résumé du jour — §7

## Phase 5 — Chercher
- [ ] 5.1 Univers : import des indices (CAC 40, SBF 120, S&P 500…), recherche ISIN, listes — §4.1
- [ ] 5.2 Screener : filtres, filtres enregistrés, score composite — §4.2
- [ ] 5.3 Comparaison : base 100, force relative, côte à côte — §4.3
- [ ] 5.4 Backtesting sans biais d'anticipation — §6

## Phase 6 — Finitions
- [ ] 6.1 Indicateurs techniques supplémentaires + paramètres — §9
- [ ] 6.2 Unités de temps hebdo / mensuelle + vue réduite au-delà de 10 ans — §9, §10
- [ ] 6.3 Tracés et annotations enregistrés — §9
- [ ] 6.4 Mode sombre + taille de police — §10
- [ ] 6.5 Recherche globale Ctrl+K — §10
- [ ] 6.6 Aide contextuelle, glossaire, première utilisation guidée — §10
- [ ] 6.7 Export PDF de la fiche + export Excel — §10
- [ ] 6.8 Cache des analyses, WAL, synthèse précalculée — §11.3
- [ ] 6.9 Journal fichier, bouton diagnostic, page « À propos » — §11.4
- [ ] 6.10 Tests : cas de référence figés, tests d'interface Playwright en CI — §11.1
- [ ] 6.11 Typage : mypy + TypeScript progressif — §11.2

## Phase 7 — Distribution et sécurité
- [ ] 7.1 Empreintes SHA-256 publiées et vérifiées avant toute mise à jour — §12
- [ ] 7.2 Retour arrière automatique si la nouvelle version ne démarre pas — §12
- [ ] 7.3 Test de mise à jour N−1 → N en CI (Windows et Linux) — §11.1
- [ ] 7.4 Canal bêta — §12
- [ ] 7.5 Sauvegarde externe vers un dossier synchronisé — §12
- [ ] 7.6 Version macOS — §12
- [ ] 7.7 Signature de code Windows (prête, activée par un secret) — §12
- [ ] 7.8 Mention légale visible — §12

## Phase 8 — Pistes avancées
- [ ] 8.1 Assistant IA (Claude) sur rapports annuels, clé API facultative — §13
- [ ] 8.2 Consensus des analystes — §13
- [ ] 8.3 Données ESG — §13
- [ ] 8.4 Partage entre plusieurs PC (export / import des fiches) — §13
