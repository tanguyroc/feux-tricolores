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
