# Runbook — feux tricolores

## 1. Routine

| Quand | Quoi | Qui |
|---|---|---|
| Chaque soir (22 h UTC, lun-ven) | `update → signals → dashboard → alert` ; commit des données | GitHub Actions |
| Chaque vendredi | `backtest` (rapport `docs/backtest.html` régénéré) | GitHub Actions |
| Fin de mois | lire le **drapeau tendance** de chaque indice (clôture mensuelle vs moyenne 10 mois) ; appliquer la règle levier sous 5 jours de bourse | vous |
| Trimestre | relire `CHANGELOG.md`, vérifier qu'aucune source n'a changé de format (le workflow échoue bruyamment sinon) | vous |
| 3 premiers mois | **mode fantôme** : journaliser les couleurs et les décisions hypothétiques, sans argent réel | vous |

## 2. Quand une alerte arrive

1. Lire la couleur, le motif et le drapeau de tendance dans l'alerte ou sur le tableau de bord.
2. Appliquer la ligne correspondante de « Ce que chaque couleur autorise » (`rules.yaml → conduct`).
3. Pour tout ordre exceptionnel (hors versement régulier) : **check-list des 48 heures**, réponses écrites dans le journal :
   - Quelle couleur, et depuis quand ?
   - Quel drapeau de tendance ?
   - Le montant respecte-t-il le plafond de la couleur ?
   - Ai-je lu l'explication générée ?
   - Agirais-je identiquement si le marché avait baissé de 10 % demain ?
4. Un ordre n'est passé qu'après les 48 heures et les cinq réponses. L'outil l'impose :
   `python -m feux decide new --asset ndx --action acheter --amount 5000 --thesis "..." --invalidation "..."`
   enregistre l'intention avec l'état des feux du moment ; `python -m feux decide confirm --id <id>` est **refusé avant 48 h**
   et redemande les cinq réponses ; `cancel` annule. Journal : `journal/decisions.md` (hors dépôt, personnel).

Rappels : le vert signifie « décoté », pas « plus bas ». Sur le Nasdaq-100, après un jour vert, le rendement à 1 an a été
négatif dans 32 % des cas (2000-2002) : d'où les tranches. Le rouge signifie « cher et tendu », pas « krach imminent » :
le S&P 500 a été rouge 57 % de 2024 et a continué de monter. On ne déduit d'une couleur ni une vente, ni un arrêt des versements.

## 3. Règles de conduite (copie de rules.yaml, à jour au 2026-11-08)

- **Versement régulier** : maintenu en toute couleur.
- **Montants exceptionnels** : vert et orange → par tiers sur 3 mois (vert + couteau qui tombe → par sixièmes sur 6 mois) ;
  rouge → en réserve rémunérée (fonds euros, livret, monétaire), déployée dès le retour à l'orange.
- **Levier (ETF x2)** : plafond 15 % de la poche actions en vert (si tendance OK), 10 % en orange, 5 % en rouge ;
  tendance cassée → 0-5 % sous 5 jours de bourse, quelle que soit la couleur. En PEA, l'arbitrage x2 → ETF non levier ne crée pas d'impôt.
- **Bitcoin et proxys (type Strategy)** : achat exceptionnel seulement en vert, par tiers ; aucun proxy à levier sous la MM200 jours.
- **Rééquilibrage** : bandes ±10 points en vert, ±5 en orange et rouge ; vendre les excédents d'abord dans le PEA.

## 4. Pannes de données

Le workflow est en `--strict` : un chargeur en échec fait échouer le job (mail GitHub). Diagnostic :

| Symptôme | Cause probable | Action |
|---|---|---|
| Shiller : lien introuvable | la page a changé | corriger `loaders/shiller.py::_find_url` ; le fichier de secours `FALLBACK` reste valable quelques mois |
| FRED : erreurs réseau | hoquet FRED ou proxy | relancer ; le chargeur réessaie 3 fois (et via curl --http1.1 derrière certains proxies) |
| FRED : `AIAE hors plage plausible` | changement d'unités des séries Z.1 | vérifier `AIAE_NUM/AIAE_DEN` et leurs unités sur FRED |
| Yahoo : 401/429 ou JSON vide | API non officielle modifiée | passer à EODHD (clé API, ~20 $/mois) : écrire `loaders/eodhd.py` sur le modèle de `yahoo.py` |
| Coin Metrics : 403 | métrique retirée de l'offre communautaire | ne garder que `PriceUSD,CapMVRVCur` ; sinon Blockchain.com / CoinGecko pour le prix seul (le z MVRV devient n.d.) |
| FINRA : 404 | nom de fichier modifié | la page `margin-statistics` est relue à chaque exécution ; corriger la regex si besoin |

Une donnée manquante produit `n.d.` et une famille calculée sur les indicateurs restants (médiane) ; si **V** est
inconnu, l'actif ne peut pas être rouge (orange par défaut) et cela apparaît dans l'explication.

## 5. Modifier une règle

1. Jamais pour « attraper » un épisode manqué a posteriori. Les seuils sont gelés ; l'unique ajustement autorisé a été
   utilisé le 2026-11-08 (Bitcoin, 1,5σ → 1,0σ, re-testé sur décembre 2013).
2. Toute modification = commit séparé + entrée datée et motivée dans `CHANGELOG.md` + re-test sur une période non
   utilisée pour la décision + mise à jour de cette section.
3. On **simplifie** une règle qui échoue ; on ne l'affine pas.

## 6. Modes d'échec connus et acceptés

- **Rouge prolongé en marché haussier** (1995-1999, 2024-2026) : seuls les montants exceptionnels sont retardés ; coût mesuré ≈ −0,3 % de capital final sur 1990-2026.
- **Baisse ordonnée sans panique** (2022) : le feu reste orange, pas vert ; on n'a pas acheté « la capitulation » parce qu'il n'y en a pas eu au sens des indicateurs (VIX et spreads modérés).
- **Vert dans une baisse structurelle** (2000-2002 sur le Nasdaq) : « cheap » peut devenir « cheaper » ; parade = tranches + interdiction du levier sous la MM10.
- **Bitcoin** : amplitude des cycles décroissante ; novembre 2021 et octobre 2025 sont restés orange (0,99σ). L'orange interdit déjà tout achat exceptionnel : l'échec est « conservateur ». Si le Bitcoin cesse d'avoir des cycles, le module dégénère en orange quasi permanent.
- **Données** : Yahoo non officiel ; `fredgraph` = dernier millésime (révisions) ; FINRA depuis 1997 seulement (la famille E est inconnue avant 2002 : le rouge de 2000 sur le S&P 500 n'est apparu qu'en mars 2000).

## 7. Module actions (prototype v0.2)

- Liste dans `stocks.yaml` (≤ 10). Types : `operating` (comptes EDGAR), `crypto_proxy` (suit le feu Bitcoin et sa propre
  tendance ; la prime sur la trésorerie BTC n'est pas calculée), `price_only` (société non américaine : extension seulement).
- Valorisation = médiane des percentiles 10 ans d'EV/EBIT et P/FCF (TTM, première publication, datée du dépôt).
  Rouge si ≥ 80 ET (GSY ou écart MM200 ≥ p90) ; vert si ≤ 30 ET solidité (moyennes 5 ans : ROIC ≥ 10 %, FCF/RN ≥ 0,7, DN/EBITDA ≤ 2,5 ; v0.5).
- DCF inversé : croissance du FCF implicite sur 10 ans (WACC 9 %, terminal 2,5 %) comparée à la croissance réalisée 5 ans ;
  un écart > 1,5× est un signal de prudence, pas une couleur.
- Limites : concepts XBRL variables selon les sociétés (le chargeur essaie plusieurs noms ; vérifier `concepts` dans
  `docs/stocks_latest.json`) ; pas d'achats d'initiés (formulaires 4) en v0.2 ; pas de backtest (anecdotique sur 10 ans).

## 8. Prochaines étapes

1. Achats groupés d'initiés (formulaires 4) comme drapeau d'information sur les actions suivies.
2. Prime mNAV des proxys crypto (trésorerie BTC déclarée / capitalisation).
3. ALFRED (millésimes) pour l'AIAE si l'on veut un point-in-time strict sur les révisions.
4. Explication par LLM (option) : entrée = `docs/latest.json`, sortie ≤ 150 mots, validée par `explain.check_numbers`.
5. Revue de portefeuille : exports CSV Trade Republic / Fortuneo → exposition réelle (x2 compté double), part thématique, écart aux bandes.
