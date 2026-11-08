# Feux tricolores — investissement long terme

**Une application monopage** (`docs/index.html`, publiée par GitHub Pages) : Aujourd'hui · Actions Top 100 · Mon portefeuille · Journal · Validation · Règles & glossaire.

Un feu **vert / orange / rouge** par actif (S&P 500, Nasdaq-100, MSCI World, Bitcoin), calculé chaque soir
à partir de données publiques, **point-in-time** (aucune valeur n'est utilisée avant sa date de publication),
par du code Python déterministe. Aucun LLM dans la chaîne de décision.

Un feu mesure un **état**, pas une prévision :

| Couleur | Signification | Ce qu'elle gouverne |
|---|---|---|
| 🟢 Vert | décoté (valorisation ≤ 40e percentile) **ou** capitulation (baisse ≥ 25 % + peur extrême) | déploiement de la réserve par tiers ; levier autorisé si la tendance est OK |
| 🟠 Orange | état normal ou ambigu (y compris « cher mais pas euphorique ») | montants exceptionnels déployés par tiers ; levier maintenu, non renforcé |
| 🔴 Rouge | cher (≥ 80e percentile) **et** (tendu **ou** euphorique) | aucun montant exceptionnel ; levier plafonné à 5 % ; rééquilibrage |
| ⚑ Tendance cassée | clôture mensuelle sous la moyenne 10 mois (Bitcoin : sous la MM200 jours) | levier ramené à 0-5 % sous 5 jours, quelle que soit la couleur |

**Les versements réguliers ne s'arrêtent jamais.** Le feu ne dit pas « vendre » ; il dit comment acheter.

## Pourquoi ces règles (résumé des preuves)

- La valorisation (CAPE) prédit les rendements à 10 ans, pas le timing : elle ne déclenche jamais le rouge seule
  (sinon rouge quasi permanent depuis 1991). Le rouge exige une deuxième famille : extension de prix (écart à la MM200,
  momentum 12 mois, critère Greenwood-Shleifer-You « +100 % en 2 ans avec accélération ») ou euphorie (dette sur marge).
- La tendance (moyenne 10 mois, Faber 2007) est le seul signal dont la réduction des pertes extrêmes est robuste :
  elle pilote le levier. Simulation 1985-2026 d'un x2 quotidien sur le Nasdaq-100 : −98,5 % en 2000-2002 sans filtre,
  −88 % avec (l'indice lui-même : −81 %).
- Combinaison par **conjonction**, pas par moyenne pondérée (AQR « Sin a little » : les déviations doivent rester modestes).
- Bitcoin : seuils fixes abandonnés (ils ont manqué le sommet d'octobre 2025) ; z-scores glissants 4 ans en log du
  prix / MM200 semaines et du MVRV. Confiance assumée plus faible.

Cahier de conception, sources et désaccords : voir la recherche jointe au projet ; règles exactes : `rules.yaml` ;
historique des modifications : `CHANGELOG.md`.

## Résultats du backtest point-in-time (1990-2026 ; Bitcoin 2014-2026)

| Actif | Temps en rouge | Rendement médian 3 ans après **vert** | … après **rouge** | Baisse médiane 24 mois après rouge (vs vert) | Épisodes reproduits |
|---|---|---|---|---|---|
| S&P 500 | 11 % | +12,8 %/an | +8,5 %/an | 13 % (6 %) | 6/7 (octobre 2022 orange, pas vert) |
| Nasdaq-100 | 14 % | +16,7 %/an | +8,7 %/an | 20 % (8 %) | 6/7 |
| MSCI World | 8 % | +10,0 %/an | +5,2 %/an | 22 % (9 %) | 5/6 |
| Bitcoin | 9 % | +78 %/an | +33 %/an | 50 % (14 %) | 6/8 (nov. 2021 et oct. 2025 orange) |

Rendements de prix hors dividendes. Chaque jour est classé par sa couleur du jour. Rapport complet : `docs/backtest.html`.

**Robustesse** (`docs/robustness.html`, v0.2) : l'écart vert − rouge à 3 ans est statistiquement solide sur le MSCI World
(IC 90 % par bootstrap de blocs : [+4,5 ; +28,9] points) et le Bitcoin ([+16 ; +135]), **pas sur le S&P 500** ([−2,5 ; +11,6]) ;
sur le Nasdaq-100 il tient presque entièrement à 2000-2002. Ce qui est stable partout : après un rouge, les baisses des
24 mois suivants sont plus profondes. Les résultats bougent peu quand on déplace chaque seuil de ±5 points (tableau de
sensibilité, aucun seuil retouché). 1987 n'a pas été signalé (orange) : krach hors conception, assumé.

**Affichage confirmé** : une nouvelle couleur n'apparaît qu'après 5 jours de bourse consécutifs (changements par an
divisés par ~3, rendements par couleur inchangés). L'état brut reste visible sur la carte.

**Coût des faux positifs** (plan type 1 000 €/mois + 10 000 €/an, 1990-2026) : attendre le **vert** pour les montants
exceptionnels aurait coûté −6 % de capital final sur le S&P 500 et −25 % sur le Nasdaq-100 (0 % sur le World), avec
~95 000 € jamais déployés depuis 2020. Différer **seulement en rouge** : −0,3 % (neutre). D'où la règle de conduite retenue.

Le gain attendu de l'outil n'est **pas** sur le rendement des flux (≈ 0) ; il est sur (1) le contrôle du levier,
(2) le comportement (pas d'achat exceptionnel ni de levier dans l'euphorie, achats effectifs dans la capitulation),
(3) le Bitcoin, où la discrimination vert/rouge est forte.

## Pour qui ne lit pas les bilans

Le tableau de bord s'ouvre en **mode simple** : une phrase par feu (« Feu rouge sur les grandes entreprises américaines :
les actions se paient cher par rapport aux bénéfices des dix dernières années ; les investisseurs empruntent beaucoup pour
acheter… Ce n'est pas le moment de placer une grosse somme d'un coup. Les versements habituels continuent. »), un encadré
« Ce mois-ci, concrètement » et un glossaire où chaque indicateur est expliqué en langage courant avec ce que la règle en fait.
Le **mode détaillé** garde tous les chiffres, percentiles et z-scores. Le brief mensuel (Telegram) reprend la version simple.

## Modules (v0.3)

| Module | Commande | Données | État |
|---|---|---|---|
| Indices (S&P 500, Nasdaq-100, MSCI World) | `signals` | Shiller, FRED, Yahoo, FINRA | validé 1985-2026 |
| Bitcoin | `signals` | Coin Metrics, alternative.me, Deribit (financement) | validé 2014-2026, confiance moyenne |
| Actions : Top 100 mondial (MSCI ACWI) + `stocks.yaml` | `universe`, `stocks` | SPDR MSCI ACWI (positions), Yahoo, SEC EDGAR | prix seuls sans `SEC_USER_AGENT` ; valorisation et qualité avec |
| Mon portefeuille, Journal | dans l'application | navigateur (localStorage) | rien n'est transmis |
| Thèmes sectoriels (semis, logiciels, tech) | `signals` (ou `themes`) | Yahoo (^SOX, IGV, XLK) | drapeaux de bulle, pas de couleur |
| Brief mensuel | `brief` | — | Telegram le 1er du mois |
| Journal de décision (48 h) | `decide` | — | opérationnel, dossier `journal/` hors dépôt ; rappelle les statistiques historiques |
| Validation et robustesse | `backtest`, `robustness` | — | rapports HTML |

## Installation et usage

```bash
pip install -r requirements.txt
python -m feux update      # télécharge Shiller, FRED, Yahoo, FINRA, Coin Metrics, Fear & Greed
python -m feux signals     # indicateurs + couleurs -> data/signals/, docs/latest.json
python -m feux backtest    # validation -> docs/backtest.html
python -m feux universe    # Top 100 mondial -> data/universe.csv
python -m feux stocks      # actions : prix seuls, ou comptes EDGAR si SEC_USER_AGENT
python -m feux dashboard   # l'application : docs/index.html (un seul fichier)
python -m feux alert       # Telegram si une couleur ou un drapeau a changé (sinon journal)
python -m feux robustness  # sous-périodes, bootstrap, sensibilité -> docs/robustness.html
SEC_USER_AGENT="Prenom Nom prenom.nom@example.com" python -m feux stocks   # actions suivies
python -m feux decide new --asset ndx --action acheter --amount 5000 --thesis "..." --invalidation "..."
python -m pytest -q tests
```

## Déploiement (GitHub, gratuit)

1. Créer un dépôt (public pour des minutes Actions illimitées et GitHub Pages ; aucune donnée personnelle n'y figure).
2. Pousser ce dossier. Activer **Settings → Pages → Source : GitHub Actions**.
3. Secrets (`Settings → Secrets and variables → Actions`) : `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
   (créer un bot via @BotFather, récupérer l'identifiant de conversation via `getUpdates`) ; `SEC_USER_AGENT`
   (« Prénom Nom adresse@email », exigé par la politique d'accès de la SEC) pour le module actions.
4. Le workflow `daily.yml` tourne du lundi au vendredi à 22 h UTC, commite les données et le tableau de bord,
   envoie une alerte uniquement s'il y a un changement. `pages.yml` publie `docs/`.
5. Note GitHub : les workflows planifiés d'un dépôt public sont désactivés après 60 jours sans activité ;
   le commit quotidien du bot devrait suffire, à vérifier le premier mois.

## Sources de données

| Donnée | Source | Décalage point-in-time appliqué |
|---|---|---|
| Prix, dividendes, bénéfices, CPI, GS10 | Robert Shiller, `ie_data.xls` | bénéfices : +3 mois |
| VIX, spread Baa−T10 (BAA10Y), T-bill 3 mois, séries Z.1 (AIAE) | FRED (`fredgraph.csv`) | Z.1 : +70 jours ; T-bill : +7 jours |
| Prix quotidiens ^GSPC, ^NDX (+^IXIC avant 1985), ^990100-USD-STRD, ^VIX | Yahoo Finance (API chart, non officielle) | aucun |
| Dette sur marge | FINRA, `margin-statistics.xlsx` | +25 jours |
| Prix et MVRV Bitcoin | Coin Metrics Community API (CC BY-NC 4.0) | aucun |
| Fear & Greed crypto | alternative.me | aucun |
| Taux de financement du perpétuel BTC | Deribit (API publique, horaire depuis 06/2019) | aucun |
| Comptes des sociétés suivies | SEC EDGAR companyfacts (XBRL) | date de dépôt réelle (`filed`), première publication |

Limites connues : Yahoo est non officiel (prévoir EODHD ≈ 20 $/mois en secours si l'API change) ; `fredgraph.csv`
renvoie le dernier millésime (révisions Z.1 : approximées par le décalage de 70 jours ; ALFRED possible plus tard) ;
l'OAS haut rendement ICE n'est pas téléchargeable au-delà de 3 ans (remplacé par BAA10Y) ; Binance et Bybit refusent
les exécuteurs américains (Deribit utilisé à la place) ; le module actions ne couvre que les sociétés déposant à la SEC.

## Structure

```
rules.yaml          seuils gelés + règles de conduite      CHANGELOG.md   modifications des règles (datées, motivées)
feux/loaders/       téléchargement, dates de disponibilité  feux/store.py  stockage point-in-time (ref_date, available_date)
feux/indicators.py  percentiles, z-scores, GSY, CAPE PIT    feux/signals.py familles V/X/E/P et couleurs
feux/backtest.py    validation, plan type, levier x2        feux/robustness.py  sous-périodes, bootstrap, sensibilité
feux/stocks.py      module actions (EDGAR, DCF inversé)     feux/journal.py     journal de décision 48 h
feux/charts.py      graphiques SVG                          feux/dashboard.py, alerts.py, explain.py
docs/               index.html, backtest.html, latest.json, state.json (publié par Pages)
```

## Avertissement

Outil personnel d'aide à la discipline. Pas un conseil en investissement. Les performances passées, point-in-time ou
non, ne garantissent rien ; voir `runbook.md` pour les modes d'échec connus.
