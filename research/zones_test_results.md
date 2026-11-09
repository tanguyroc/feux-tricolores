# Test de la mesure « dividendes lissés » des zones — résultats (9 novembre 2026)

Protocole : `research/zones_test_protocol.md` (écrit avant calcul). Code : `research/zones_test.py`.
Données : Jordà-Schularick-Taylor Macrohistory Database R6, 16 pays avec données actions, 1870-2020, monnaie locale.
Résultats bruts : `research/zones_test_results.json`.

## Verdict : la variante « comme l'application » échoue (critère 2), la valorisation des zones devient une information

| Critère (variante A, 20 ans de comparaison, rendement réel à 5 ans) | Seuil | Résultat | |
|---|---|---|---|
| 1. Corrélation de rang percentile / rendement | négative, IC 90 % hors de zéro | −0,13 [−0,20 ; −0,07] | ✓ |
| 2. Vert (percentile ≤ 40) − autres, médianes | ≥ +2 points par an | **+1,9** (6,2 % contre 4,3 %) | ✗ |
| 3. Pays où vert > autres | ≥ deux tiers | 13 sur 16 | ✓ |

Échec de justesse, mais échec : la règle écrite avant le calcul s'applique. Les zones, secteurs et thèmes affichent leur
valorisation contre leur passé comme une information (très bon marché … très cher), sans feu (règles v1.1).

## Détail (rendement total réel annualisé, médianes ; n = années-pays, qui se chevauchent)

| Mesure | Horizon | n | Corrélation de rang | Vert | Autres | Chère (≥ 80) | Cas négatifs vert / cher |
|---|---|---|---|---|---|---|---|
| A — P/D10, 20 dernières années | 3 ans | 1 851 | −0,09 | +6,4 % | +4,5 % | +3,4 % | 29 % / 38 % |
| | 5 ans | 1 819 | −0,13 | +6,2 % | +4,3 % | +3,3 % | 26 % / 34 % |
| | 10 ans | 1 739 | −0,12 | +6,1 % | +4,4 % | +3,9 % | 21 % / 24 % |
| B — P/D10, tout le passé du pays | 5 ans | 1 429 | −0,16 [−0,25 ; −0,08] | +6,7 % | +4,2 % | +2,8 % | 28 % / 39 % |
| Témoin — prix / moyenne 10 ans, sans dividendes | 5 ans | 1 826 | −0,09 [−0,15 ; −0,03] | +5,6 % | +4,4 % | +3,8 % | 26 % / 35 % |

Sous-périodes (A, 5 ans) : avant 1950, +1,9 point (corrélation −0,17) ; 1950-1989, +0,4 point (−0,08, intervalle incluant zéro,
9 pays sur 15) ; depuis 1990, +2,3 points (−0,17, 9 pays sur 15).

Écart vert − autres à 5 ans par pays (A) : Espagne +6,9 ; Finlande +6,3 ; Japon +5,7 ; Australie +4,1 ; Suisse +3,6 ;
Belgique +3,1 ; Royaume-Uni +2,4 ; Danemark +2,3 ; Allemagne +1,9 ; Norvège +1,6 ; France +0,7 ; États-Unis +0,5 ; Suède +0,1 ;
Portugal −1,1 ; Italie −5,0 ; Pays-Bas −6,3.

## Lecture

- **La mesure contient de l'information, peu.** Une corrélation de −0,13 explique environ 2 % des écarts de rendement à cinq ans.
  C'est l'ordre de grandeur du vert des indices depuis 1990 (+1 à +3 points à 3 ans), mais le seuil fixé d'avance n'est pas atteint.
- **Les dividendes apportent un peu plus que le prix seul** (+1,9 contre +1,2 point ; corrélation −0,13 contre −0,09).
- **C'est la longueur de l'historique qui manque** : avec tout le passé du pays (variante B), +2,5 points et 12 pays sur 15. Les ETF
  n'offrent que 10 à 20 ans de comparaison.
- **Limites du test** : monnaie locale (l'application juge des ETF en dollars) ; données annuelles ; base arrêtée en 2020 ; la
  médiane des sociétés (secteurs) n'est pas testée, faute d'historique.

## Comparaison avec Kairys Lite

Kairys Lite comparait le PER courant de l'ETF (Yahoo Finance) à un « PER normal » saisi à la main par ETF ou par segment, sans
source ni historique, complété par le momentum, la force relative contre l'ACWI et la tendance. Aucune de ces normes ne peut être
testée sur le passé ; la mesure par les dividendes, elle, a pu l'être, et le test dit qu'elle ne mérite pas un feu. Ce n'était donc
pas mieux : c'était invérifiable.

## Piste d'amélioration (non faite)

Raccorder, pour les pays développés, l'historique long de la base JST (jusqu'en 2020) aux dividendes des ETF depuis : la comparaison
porterait sur un siècle (variante B). Un nouveau protocole serait écrit avant.
