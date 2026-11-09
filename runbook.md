# Runbook — feux tricolores (règles v1.0)

## 1. Routine

| Quand | Quoi | Qui |
|---|---|---|
| Chaque soir (22 h 17 UTC, lun-ven) | `update → signals → universe/stocks → check → dashboard → archive/prereg → alert` ; commit ; publication | GitHub Actions |
| Chaque vendredi | `backtest` (rapport `docs/backtest.html` régénéré) | GitHub Actions |
| 1er du mois | brief mensuel ; la première exécution du mois pré-inscrit l'état des règles (`prereg/AAAA-MM-JJ.json`, haché) | GitHub Actions |
| Fin de mois | lire le **drapeau tendance** de chaque indice (clôture mensuelle vs moyenne 10 mois) ; appliquer la règle levier sous 5 jours de bourse | vous |
| Chaque mois | onglet Journal : faire les **revues à 90 jours** signalées ; Mon portefeuille : relire les points d'attention | vous |
| Trimestre | relire `CHANGELOG.md` et l'onglet Validation (témoins, pré-inscriptions) | vous |
| 3 premiers mois | **mode fantôme** : journaliser les décisions hypothétiques, sans argent réel | vous |

## 2. Quand une alerte arrive

1. **« Publication annulée »** : un contrôle bloquant a échoué (données trop anciennes ou incomplètes, ou témoin en échec). Le site
   garde la dernière version sûre. Ouvrir le lien de l'alerte (journal GitHub Actions, étape « Contrôles avant publication ») :
   une source en panne → section 4 ; un témoin en échec → un défaut de code ou de données à corriger avant de relancer.
2. Changement de couleur ou de drapeau : lire la couleur, le motif et le drapeau de tendance sur l'application.
3. Appliquer la ligne correspondante de « Ce que chaque couleur autorise » (`rules.yaml → conduct`, onglet Règles).
4. Pour tout ordre exceptionnel (hors versement régulier) : intention écrite dans l'onglet **Journal** (ou `python -m feux decide new`),
   cinq questions, **48 heures** avant confirmation ; **vente ou arbitrage en période de stress** (feu vert, couteau qui tombe, ou baisse
   d'au moins 20 % depuis le plus haut) : trois questions de plus et **7 jours**. Chaque décision confirmée revient à **90 jours**
   pour une revue écrite (thèse vérifiée ? invalidation atteinte ? la referais-je ?).

Rappels : le vert signifie « décoté » ou « capitulation », pas « plus bas » : sur le Nasdaq-100, les verts de 2000-2002 ont été
suivis de nouvelles baisses (90e percentile de la baisse sur 24 mois après un vert : 61 %) : d'où les tranches et le drapeau
« couteau qui tombe ». « Cher » n'est pas un signal de vente : depuis 1990, le marché américain a été cher 88 % du temps.

## 3. Règles de conduite (copie de rules.yaml v1.0, gelées le 2026-11-09)

- **Versement régulier** : maintenu en toute couleur.
- **Montants exceptionnels** : vert → réserve déployée par tiers sur 3 mois (sixièmes sur 6 mois si couteau qui tombe) ;
  orange, « cher » compris → trois tranches mensuelles, sans attendre un meilleur moment.
- **Levier (ETF x2)** : plafond 15 % de la poche actions en vert (si tendance OK), 10 % en orange (« cher » compris) ;
  tendance cassée → 5 % sous 5 jours de bourse, quelle que soit la couleur. En PEA, l'arbitrage x2 → ETF non levier ne crée pas d'impôt.
- **Bitcoin (B1)** : vert → achat exceptionnel possible, par tiers ; orange → versements seulement ; rouge (MVRV ≥ 3) → aucun achat
  exceptionnel ; jamais de société « proxy » à levier sous la MM200 jours.
- **Rééquilibrage** : bandes ±10 points en vert, ±5 en orange et rouge ; vendre les excédents d'abord dans le PEA.
- **Concentration** : une action au-delà de 12 % de la poche risquée → alerte dans Mon portefeuille (ramener par les versements).

## 4. Pannes de données

Le chargement est en `--strict` (un chargeur en échec fait échouer le job), puis `python -m feux check` vérifie fraîcheur et
complétude avant toute publication. Diagnostic :

| Symptôme | Cause probable | Action |
|---|---|---|
| Shiller : lien introuvable | la page a changé | corriger `loaders/shiller.py::_find_url` ; le fichier de secours `FALLBACK` reste valable quelques mois |
| FRED : erreurs réseau | hoquet FRED ou proxy | relancer ; le chargeur réessaie 3 fois |
| FRED : `AIAE hors plage plausible` | changement d'unités des séries Z.1 | vérifier `AIAE_NUM/AIAE_DEN` et leurs unités sur FRED |
| Yahoo : 401/429 ou JSON vide | API non officielle modifiée | passer à EODHD (clé API, ~20 $/mois) : écrire `loaders/eodhd.py` sur le modèle de `yahoo.py` |
| Coin Metrics : 403 | métrique retirée de l'offre communautaire | ne garder que `PriceUSD,CapMVRVCur` ; sinon prix seul (la règle B1 devient inapplicable : orange) |
| FINRA : 404 | nom de fichier modifié | la page `margin-statistics` est relue à chaque exécution ; corriger la regex si besoin |
| `check` : « actions : au moins 60 valorisées » | `SEC_USER_AGENT` absent ou SEC indisponible | vérifier le secret ; relancer |
| `check` : témoin « nombre d'actions » en échec | division d'actions mal datée ou donnée SEC à la mauvaise échelle | lire la société citée ; corriger `stocks.py` (`split_adjust_shares`, `clean_share_counts`) |

Les rapports annuels IFRS récents de TSMC, Toyota, Sony et BHP sont déposés à la SEC mais leurs chiffres n'apparaissent pas dans
l'API `companyfacts` : ces sociétés restent en « comptes anciens » (orange) jusqu'à ce que l'API les intègre.

## 5. Modifier une règle

1. Jamais pour « attraper » un épisode manqué a posteriori. Une modification de règle suit le chemin de la v1.0 : protocole écrit
   et poussé **avant** les calculs (critères chiffrés, règle de décision), hors-échantillon jamais utilisé, résultats publiés tels quels.
2. Commit séparé + entrée datée et motivée dans `CHANGELOG.md` + archive des règles précédentes (`archive/`).
3. On **simplifie** une règle qui échoue ; on ne l'affine pas.
4. Les pré-inscriptions (`prereg/`) et l'archive (`history/`) ne sont jamais modifiées : ajout seul.

## 6. Modes d'échec connus et acceptés

- **Marché cher pendant des années** (1995-1999, 2024-2026) : orange « cher » ; les montants exceptionnels partent en trois tranches,
  sans attendre (attendre le vert aurait coûté 9 % de capital final sur le S&P 500 et 26 % sur le Nasdaq-100 depuis 1990).
- **Baisse ordonnée sans panique** (2022) : le feu reste orange, pas vert (VIX et écarts de crédit modérés).
- **Vert dans une baisse structurelle** (2000-2002 sur le Nasdaq) : « décoté » peut le devenir davantage ; parade = tranches, couteau
  qui tombe, levier interdit sous la MM10.
- **Bitcoin** : sommets de moins en moins extrêmes ; B1 n'a pas allumé le rouge en novembre 2021, mars 2024 et octobre 2025.
  L'orange interdit déjà tout achat exceptionnel : l'échec est « conservateur ».
- **Rendement attendu à 10 ans** : bon pour classer les périodes, trop pessimiste de 5 points par an depuis 1990 ; affiché, jamais une règle.
- **Données** : Yahoo non officiel ; `fredgraph` = dernier millésime (révisions) ; valorisation du Nasdaq-100 et du MSCI World = celle
  du S&P 500 (proxy, faute d'historique long).

## 7. Module actions (indicatif, non backtesté)

- Univers : Top 100 du MSCI ACWI + `stocks.yaml` (surcharges : `cik`, `extra_ciks`, type `crypto_proxy` ou `price_only`).
- Deux lentilles : V (médiane des percentiles 10 ans d'EV/EBIT et P/FCF, première publication, datée du dépôt ; banques et assureurs :
  P/E et P/B) et V_cross (rang parmi les sociétés du même mode). FCF net de la rémunération en actions.
- Rouge si V ≥ 80 **et** V_cross ≥ 80 **et** tendu (écart MM200 ≥ p90 ou GSY) ; vert si V ≤ 30 **et** V_cross ≤ 30 **et** solide
  (moyennes 5 ans : rentabilité ≥ 10 %, FCF/RN ≥ 0,7, dette nette/EBITDA ≤ 2,5) ; comptes de plus de 15 mois → orange.
- Nombres d'actions : divisions appliquées selon la date de **dépôt** ; valeurs en milliers ou millions corrigées ; aberrations écartées
  (détail affiché dans la fiche de la société).
- DCF inversé : croissance du FCF implicite sur 10 ans (WACC 9 %, terminal 2,5 %) contre la croissance réalisée 5 ans.

## 8. Prochaines étapes

1. 9 novembre 2027 : premier verdict à un an des pré-inscriptions ; 2029 : à trois ans. Ne rien changer aux règles d'ici là sans protocole.
2. Hypothèse inscrite : « cher et tendu » sur le Nasdaq-100 (R1) — à juger en avant, pas sur le passé.
3. Achats groupés d'initiés (formulaires 4) comme drapeau d'information.
4. Sources des comptes IFRS (TSMC, Toyota, Sony, BHP) si l'API de la SEC ne les intègre pas.
