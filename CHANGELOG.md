# Journal des modifications des règles

## 2026-11-08 — amendement pré-backtest (aucun backtest exécuté avant cette modification)
- Famille « peur » : l'OAS haut rendement ICE BofA (BAMLH0A0HYM2) n'est téléchargeable sur FRED que
  sur les 3 dernières années (restriction de licence). Remplacé par le spread Baa − Treasury 10 ans
  (BAA10Y, quotidien depuis 1986). Même rôle (stress de crédit), seuils inchangés (percentile ≥ 80).
- Loader FRED : les séries Z.1 sont toutes en millions de dollars ; correction du calcul AIAE.

## 2026-11-08 — après le premier backtest (ajustement unique autorisé par le protocole, et conduite)
1. **Bitcoin, seuil rouge 1,5σ → 1,0σ** (famille valorisation, z-score 4 ans en log). Motif : avec 1,5σ, seul
   le sommet de décembre 2017 était rouge (V = 2,85) ; avril 2021 (V = 1,42), novembre 2021 (0,99) et
   octobre 2025 (0,99) restaient orange, conformément à l'amplitude décroissante des cycles. Avec 1,0σ : avril 2021
   devient rouge ; la part du temps en rouge passe de 5 % à 9 % ; le rendement médian à 1 an après un jour rouge
   passe de +17,7 % à +9,7 % (meilleure discrimination). **Re-test sur une période non utilisée pour la décision** :
   le sommet du 4 décembre 2013 (V = 1,17, critère GSY vrai) est rouge avec 1,0σ et orange avec 1,5σ.
   Limite assumée : novembre 2021 et octobre 2025 restent orange (0,99 < 1,0) ; aucun autre ajustement ne sera fait
   pour « attraper » ces deux dates. L'orange interdit déjà tout achat exceptionnel de Bitcoin.
2. **Conduite — montants exceptionnels** : la règle « déployer la réserve seulement en vert » est remplacée par
   « déployer par tiers en vert et en orange, différer seulement en rouge ». Motif (simulation 1990-2026, plan type
   1 000 €/mois + 10 000 €/an, réserve rémunérée au taux des bons du Trésor 3 mois) : attendre le vert a coûté
   −6,2 % de capital final sur le S&P 500 et −24,8 % sur le Nasdaq-100 (0 % sur le MSCI World), avec ~95 000 €
   jamais déployés depuis 2020 ; différer seulement en rouge coûte −0,3 % (neutre). Le vert est rare (12-16 % du temps)
   et groupé sur quelques épisodes : on ne peut pas bâtir une politique de flux dessus.
   Les seuils des indicateurs n'ont PAS été modifiés par cette décision.

## 2026-11-08 — v0.2 (approfondissement ; aucun seuil de règle modifié)
- **Bitcoin — taux de financement** : implémentation de l'indicateur pré-enregistré (`funding_30d_pct_red_min: 90`)
  avec l'historique Deribit (horaire depuis juin 2019 ; Binance et Bybit refusent les exécuteurs américains).
  Résultat : confirme le rouge de janvier-avril 2021 (financement au 94-96e percentile) ; **ne change rien** pour
  novembre 2021 (72e percentile) ni octobre 2025 (67e) : ces sommets se sont faits sans euphorie de levier.
- **Couche de confirmation** (`confirmation_days: 5`) : une nouvelle couleur n'est affichée et alertée qu'après
  5 jours de bourse consécutifs. Effet mesuré : changements par an divisés par ~3 (S&P 500 4,6 → 1,4 ; Nasdaq 5,2 → 1,5 ;
  World 3,2 → 1,1 ; Bitcoin 8,5 → 3,0), rendements médians par couleur inchangés. La règle (`color`) n'est pas touchée ;
  la colonne `color_confirmed` sert à l'affichage, aux alertes et au journal.
- **Robustesse** (`docs/robustness.html`) : sous-périodes, bootstrap de blocs, sensibilité des seuils, 1985-1989.
  Constats : l'écart vert − rouge à 3 ans est statistiquement robuste sur le MSCI World (IC 90 % [+4,5 ; +28,9] pts)
  et le Bitcoin ([+16 ; +135]), **pas sur le S&P 500** ([−2,5 ; +11,6]) ; sur le Nasdaq-100 il dépend presque
  entièrement de 2000-2002. La profondeur des baisses après un rouge est, elle, cohérente partout. 1987 : orange (CAPE à 18,
  sous le 80e percentile de la fenêtre 1962-1987) — un krach non signalé, hors conception, assumé.
- **Levier** : variantes de référence (Faber) et filtre 10 mois seul sur les trois indices ; graphique des courbes.
- **Module actions (prototype)** : `stocks.yaml`, EDGAR companyfacts point-in-time (première publication, datée du dépôt),
  EV/EBIT et P/FCF en percentile 10 ans, DCF inversé, filtre qualité éliminatoire, proxys crypto routés vers le feu Bitcoin.
  Nécessite `SEC_USER_AGENT`. Non validé par backtest (10 ans de données, ≤ 10 valeurs : anecdotique).
- **Journal de décision** (`python -m feux decide`) : intention écrite + cinq questions, confirmation refusée avant 48 h,
  instantané des feux à l'intention et à la confirmation. Dossier `journal/` exclu du dépôt (personnel).

## 2026-11-08 — v0.3 (expérience utilisateur et valeur concrète ; aucun seuil de règle modifié)
- **Mode simple / mode détaillé** dans le tableau de bord : mêmes chiffres, mêmes règles, mais chaque feu est d'abord
  expliqué en une phrase de langage courant ; « En une phrase » et « Ce mois-ci, concrètement » en tête ; glossaire de tous
  les indicateurs avec ce que la règle en fait ; infobulles sur chaque chiffre. Les alertes commencent par la version simple.
- **Thèmes sectoriels** (semi-conducteurs ^SOX, éditeurs de logiciels IGV, technologie XLK) : drapeaux de bulle
  (critère GSY, établi sur des secteurs), extension et tendance. Pas de couleur : sans valorisation, jamais « rouge ».
- **Brief mensuel** (`python -m feux brief`, workflow `monthly.yml` le 1er du mois) : le point en langage courant + actions du mois.
- **Journal** : à l'enregistrement d'une intention, rappel de ce qui s'est passé historiquement après la couleur du jour.
- **EDGAR** : concepts IFRS (déposants de 20-F : ASML, Novo Nordisk, TotalEnergies) et devises ; valeurs annuelles acceptées.
- **Liste de suivi proposée** (`stocks.yaml`, à valider) : Oracle, Microsoft, Nvidia, Salesforce (à remplacer par l'éditeur détenu),
  Alphabet, ASML (PEA), Novo Nordisk (PEA), Visa, Strategy (proxy), SoftBank (prix seul).
