# Feux tricolores — investissement long terme

**Une application monopage** (`docs/index.html`, publiée par GitHub Pages) : Aujourd'hui · Actions Top 100 · Mon portefeuille ·
Journal · Validation · Règles & glossaire.

Un feu par actif (S&P 500, Nasdaq-100, MSCI World, Bitcoin), calculé chaque soir à partir de données publiques,
**point-in-time** (aucune valeur n'est utilisée avant sa date de publication), par du code Python déterministe.
Aucun LLM dans la chaîne de décision. Version des règles : **v1.0** (`rules.yaml`, gelées le 9 novembre 2026).

Un feu mesure un **état**, pas une prévision :

| Couleur | Signification | Ce qu'elle gouverne |
|---|---|---|
| 🟢 Vert | indices : décoté (CAPE ≤ 40e percentile depuis 1881) **ou** capitulation (baisse ≥ 25 % et peur ≥ 80e percentile) ; Bitcoin : MVRV < 1 ou prix sous sa moyenne 200 semaines | la réserve est déployée ; levier jusqu'à 15 % si la tendance est OK |
| 🟠 Orange | tout le reste, y compris **« cher »** (CAPE ≥ 80e percentile), affiché comme information | versements ; montants exceptionnels en trois tranches mensuelles ; levier ≤ 10 % |
| 🔴 Rouge | **Bitcoin seulement** : MVRV ≥ 3 | aucun montant exceptionnel ; levier ≤ 5 % |
| ⚑ Tendance cassée | clôture mensuelle sous la moyenne 10 mois (Bitcoin : sous la MM200 jours) | levier ramené à 5 % |

**Les versements réguliers ne s'arrêtent jamais.** Le feu ne dit pas « vendre » ; il dit comment acheter.

## Pourquoi ces règles : un protocole écrit avant les calculs

La v1.0 vient d'un protocole pré-enregistré (`research/v1_protocol.md`, poussé avant tout calcul, empreinte dans
`research/PROTOCOL_HASHES.txt`) et de ses résultats publiés tels quels (`research/v1_results.md`) :

- **Rouge des indices abandonné.** Trois définitions candidates (« cher et tendu », « cher et tendance cassée », « très cher »)
  passent largement sur un hors-échantillon jamais utilisé (S&P Composite 1920-1989, écart de rendement vert − rouge à 3 ans de
  +13 à +19 points) mais **aucune ne passe sur le S&P 500 depuis 1990** (+2 à +4 points). Raison : le CAPE a été au-dessus de son
  80e percentile historique 88 % du temps depuis 1990 (20 % avant) ; attendre parce que le marché était cher a coûté cher.
  « Cher » reste affiché, avec le rendement réel attendu à 10 ans, sa fourchette et son biais (trop pessimiste de 5,2 points par an
  depuis 1990 en hors-échantillon).
- **Vert conservé** : décote ou capitulation ont été suivies de meilleurs rendements que l'orange (écart à 3 ans : +2,6 points sur le
  S&P 500, +1,2 sur le Nasdaq-100, +3,2 sur le MSCI World, 1990-2026) ; c'est le moment de déployer une réserve, pas un signal de timing.
- **Tendance (moyenne 10 mois, Faber 2007)** : réduit les pertes extrêmes (S&P 500 1990-2026 : perte maximale 33 % au lieu de 57 %) au
  prix d'un rendement plus faible ; elle pilote donc le levier, pas les achats. Nasdaq-100 x2 quotidien : −98,5 % en 2000-2002 sans
  filtre, −89 % avec (l'indice : −81 %).
- **Bitcoin, règle B1 en niveaux** : écart de rendement à 3 ans vert − rouge de +116 points (2014-2026, pas de hors-échantillon
  possible). Le seuil d'origine (MVRV 3,7) n'a jamais été atteint depuis 2014 : **le rouge peut manquer le prochain sommet**.

## Résultats, règles en vigueur (point-in-time, 1990-2026 ; Bitcoin 2014-2026)

| Actif | Temps en vert | Rendement médian 3 ans après **vert** | … après **orange** | Baisse 24 mois, 90e percentile (vert / orange) |
|---|---|---|---|---|
| S&P 500 | 8 % | +12,3 %/an | +9,7 %/an | 29 % / 34 % |
| Nasdaq-100 | 13 % | +16,8 %/an | +15,7 %/an | 61 % / 35 % |
| MSCI World | 9 % | +10,9 %/an | +7,7 %/an | 30 % / 37 % |
| Bitcoin (rouge 4 % du temps) | 17 % | +126 %/an | +50 %/an (rouge : +9 %/an) | 25 % / 69 % (rouge : 79 %) |

Rendements de prix hors dividendes ; chaque jour est classé par sa couleur du jour. Sur le Nasdaq-100, les verts de 2000-2002
(capitulations trop précoces) expliquent la baisse de 61 % : d'où le drapeau « couteau qui tombe » et les tranches.
**Plan type** (1 000 €/mois + 10 000 €/an) : trois tranches mensuelles contre tout investir tout de suite, −0,3 % de capital final ;
attendre le vert, −9,1 % (S&P 500) et −26,5 % (Nasdaq-100).

Le gain attendu de l'outil n'est **pas** sur le rendement des flux (≈ 0) ; il est sur (1) le contrôle du levier, (2) le comportement
(pas de levier ni de montant exceptionnel d'un coup ; achats effectifs dans la capitulation ; ventes ralenties), (3) le Bitcoin.

**Test en avant.** Chaque jour, l'état est archivé (`history/`) ; chaque mois, ce que les règles affirment est inscrit, haché
(SHA-256) et commité (`prereg/`), puis confronté au réalisé à un an et trois ans (onglet Validation). Premiers verdicts :
9 novembre 2027 et 9 novembre 2029.

## Actions : le Top 100 mondial

Univers = 100 premières pondérations du MSCI ACWI (positions de l'ETF SPDR), comptes SEC EDGAR point-in-time. Chaque société est
jugée sous **deux lentilles** : son multiple contre **son passé** (EV/EBIT et P/FCF, percentile 10 ans) et contre **les autres
grandes sociétés**. Flux libre **net de la rémunération en actions**. Feu **indicatif, non backtesté** : rouge seulement si chère
sous les deux lentilles **et** tendue ; vert seulement si bon marché sous les deux **et** solide (rentabilité, cash, dette sur 5 ans) ;
comptes de plus de 15 mois → orange. Les données SEC sont nettoyées (divisions d'actions selon la date de dépôt, nombres déclarés
en milliers ou en millions, valeurs aberrantes) et un témoin vérifie chaque jour qu'aucun nombre d'actions ne saute de plus de 50 %.
Secteurs et thèmes : drapeaux de prix et valorisation médiane, **sans couleur**.

## Garde-fous de publication et de comportement

- `python -m feux check` : contrôles de fraîcheur et de complétude, et **témoins** (ce que le code doit faire, vérifié sur les données
  du jour : pas de rouge sur les indices, règle B1 respectée, banques en P/E, comptes anciens jamais colorés, FCF net ≤ brut, nombre
  d'actions continu…). Un contrôle bloquant en échec arrête la mise à jour : le site garde la dernière version sûre et une alerte part.
- Mon portefeuille (navigateur seulement) : exposition réelle avec levier, test de résistance, plafond de levier du jour, écart aux
  cibles, versement du mois, **points d'attention par ligne et test d'échange**, **alerte de concentration** (> 12 % de la poche risquée).
- Journal : intention écrite, cinq questions, 48 h avant confirmation ; **vente en période de stress : trois questions de plus et
  7 jours** ; **revue écrite à 90 jours** avec la performance depuis l'intention.

## Installation et usage

```bash
pip install -r requirements.txt
python -m feux update      # Shiller, FRED, Yahoo, FINRA, Coin Metrics, Fear & Greed, Deribit
python -m feux signals     # indicateurs + couleurs -> data/signals/, docs/latest.json
python -m feux universe    # Top 100 mondial -> data/universe.csv
SEC_USER_AGENT="Prénom Nom adresse@email" python -m feux stocks   # actions (sans la variable : prix seuls)
python -m feux check       # contrôles et témoins -> docs/checks.json (code 1 si un contrôle bloquant échoue)
python -m feux dashboard   # l'application : docs/index.html (un seul fichier)
python -m feux archive     # ajoute l'état du jour à history/
python -m feux prereg --monthly   # pré-inscription du mois (une seule fois par mois)
python -m feux alert       # alerte si une couleur ou un drapeau a changé
python -m feux backtest    # validation -> docs/backtest.html, docs/backtest_summary.json
python -m feux longrun     # protocole v1.0 (1920-1989 et 1990-aujourd'hui) -> docs/longrun_summary.json
python -m feux decide new --asset ndx --action acheter --amount 5000 --thesis "..." --invalidation "..."
python -m pytest -q tests
```

## Déploiement (GitHub, gratuit)

1. Dépôt public (minutes Actions illimitées et GitHub Pages ; aucune donnée personnelle n'y figure).
2. **Settings → Pages → Source : GitHub Actions**.
3. Secrets (`Settings → Secrets and variables → Actions`) :
   - `SEC_USER_AGENT` : « Prénom Nom adresse@email » (exigé par la SEC, envoyé seulement à sec.gov) ;
   - `NTFY_TOPIC` : le sujet ntfy.sh auquel vous êtes abonné (alertes, échecs de publication, brief mensuel) ;
   - ou `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`.
4. `daily.yml` tourne du lundi au vendredi à 22 h 17 UTC : données → signaux → actions → **contrôles (bloquants)** → application →
   archive et pré-inscription → alertes → backtest le vendredi → commit → publication. Lancement manuel : Actions → Feux quotidiens →
   Run workflow. `monthly.yml` envoie le brief le 1er du mois.
5. Les workflows planifiés d'un dépôt public sont désactivés après 60 jours sans activité ; le commit quotidien du bot suffit.

## Sources de données

| Donnée | Source | Décalage point-in-time appliqué |
|---|---|---|
| Prix, dividendes, bénéfices, CPI | Robert Shiller, `ie_data.xls` | bénéfices : +3 mois |
| VIX, écart de crédit (BAA10Y, BAA−AAA), T-bill 3 mois, séries Z.1 | FRED | Z.1 : +70 jours ; T-bill : +7 jours |
| Prix quotidiens des indices, des ETF sectoriels et des actions | Yahoo Finance (API chart, non officielle) | aucun |
| Dette sur marge | FINRA | +25 jours |
| Prix et MVRV Bitcoin | Coin Metrics Community API (CC BY-NC 4.0) | aucun |
| Fear & Greed crypto ; financement du perpétuel BTC | alternative.me ; Deribit | aucun |
| Univers Top 100 ; S&P 500 | positions SPDR MSCI ACWI et SPY (State Street) | date de publication |
| Comptes des sociétés | SEC EDGAR companyfacts (XBRL) | date de dépôt réelle, première publication |

Limites connues : Yahoo est non officiel ; FRED renvoie le dernier millésime (révisions Z.1 approximées par le décalage) ; les
sociétés qui ne déposent pas à la SEC sont suivies en prix seul ; pour plusieurs déposants IFRS (TSMC, Toyota, Sony, BHP), les
chiffres des rapports 2026 n'apparaissent pas dans l'API de la SEC : comptes anciens, donc orange.

## Structure

```
rules.yaml            règles gelées v1.0             CHANGELOG.md     modifications (datées, motivées)
research/             protocole v1.0, empreintes, résultats       archive/   règles et résultats v0.6
feux/loaders/         téléchargement, dates de disponibilité      feux/store.py    stockage point-in-time
feux/signals.py       valorisation, rendement attendu, couleurs   feux/longrun.py  protocole 1881-2026
feux/backtest.py      validation, plan type, levier x2            feux/stocks.py   module actions (EDGAR)
feux/check.py         contrôles avant publication, témoins        feux/prereg.py   archive et pré-inscription
feux/app.py, dashboard.py, plain.py, explain.py   application    feux/alerts.py, brief.py   alertes et brief
history/, prereg/     archive quotidienne, pré-inscriptions hachées (ajout seul)
docs/                 index.html, latest.json, checks.json, backtest.html (publié par Pages)
```

## Avertissement

Outil personnel d'aide à la discipline. Pas un conseil en investissement. Les performances passées, point-in-time ou non,
ne garantissent rien ; voir `runbook.md` pour les modes d'échec connus.
