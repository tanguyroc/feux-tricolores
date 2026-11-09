# Test de la mesure « dividendes lissés » des zones — protocole écrit avant calcul

Écrit le 9 novembre 2026, avant tout calcul sur les données ci-dessous.

## Question

Le feu des zones (et des secteurs ou thèmes de moins de 5 sociétés du Top 100) repose sur P/D10 : le prix rapporté aux
dividendes réels moyens des dix dernières années, en percentile contre son propre passé. Cette mesure a-t-elle, par le
passé, distingué les marchés chers des marchés bon marché ?

## Données

Jordà-Schularick-Taylor Macrohistory Database, version R6 (macrohistory.net) : rendement total et rendement de prix des
actions, rapport dividende / prix, inflation ; annuel, 16 pays avec données actions, 1870-2020, en monnaie locale.
(L'application juge des ETF en dollars depuis 1996 environ : ce test porte sur la mesure, pas sur les ETF eux-mêmes.)

## Mesures

- Prix réel P (rendement de prix cumulé, déflaté) ; dividende réel D = (dividende / prix) × P ; P/D10 = P / moyenne de D sur
  10 ans (10 années disponibles exigées).
- Variante A, « comme l'application » : percentile de P/D10 parmi les 20 dernières années du même pays (5 valeurs au moins).
- Variante B, « idéale » : percentile parmi tout le passé connu du pays (30 valeurs au moins).
- Témoin sans dividendes : percentile du prix réel rapporté à sa moyenne des 10 dernières années (même fenêtre que A),
  pour savoir si les dividendes apportent quelque chose au-delà du simple « le prix a beaucoup monté ».
- Résultat : rendement total réel annualisé à 5 ans (principal), 3 et 10 ans (secondaires).

## Critères (la variante A est jugée utile si les trois sont remplis)

1. Corrélation de rang, toutes années et pays confondus, entre le percentile et le rendement à 5 ans : négative, intervalle
   à 90 % (bootstrap par blocs pays × décennies, 1 000 tirages) excluant zéro.
2. Rendement médian à 5 ans des années « vertes » (percentile ≤ 40) supérieur d'au moins 2 points par an à celui des autres.
3. Même sens (vert > autres à 5 ans) dans au moins deux tiers des pays ayant au moins 5 années vertes.

Si A échoue, le feu des zones fondé sur P/D10 est retiré ou rétrogradé en simple information, quel que soit le résultat
de B. Si le témoin sans dividendes fait aussi bien que A, la mesure est simplifiée.
