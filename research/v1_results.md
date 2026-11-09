# Résultats du protocole v1.0 — publiés tels quels

Protocole : `research/v1_protocol.md` (commit e92b515, poussé le 9 novembre 2026 à 07:40, avant tout calcul ;
sha256 `08e5abbb…df44`). Calcul : `python -m feux longrun` (module `feux/longrun.py`), une seule exécution.
Données : Shiller `ie_data.xls` du 8 novembre 2026, FRED `BAA`/`AAA`, séries quotidiennes v0.6.

## Issue

**Aucun candidat ne passe sur le S&P 500 depuis 1990** (moteur quotidien). Les trois passaient largement sur 1920-1989.
Conformément au §8.4 du protocole : le vert est conservé ; le rouge des indices devient un état d'information « cher »
(V ≥ 80) sans règle de report ; les montants exceptionnels sont toujours déployés en trois tranches mensuelles, sauf en vert ;
le levier reste gouverné par la tendance. **Bitcoin : B1 passe et est adopté.**

## 1. Hors échantillon — S&P Composite mensuel, janvier 1920 → décembre 1989 (rendements réels, dividendes inclus)

| Candidat | Part vert / orange / rouge | Épisodes rouges | 3 ans après vert | après orange | après rouge | Écart vert − rouge (a) | (b) rouge ≤ 25 % | (c) ≥ 3 épisodes | (d) p90 baisse 24 mois orange / rouge |
|---|---|---|---|---|---|---|---|---|---|
| R1 cher et tendu | 53 % / 45 % / 2 % | 8 | +13.8 % | +4.5 % | -5.5 % | **+19.3 pts** ✓ | ✓ | ✓ | 37 % / 42 % ✓ |
| R2 cher et cassé | 53 % / 43 % / 4 % | 11 | +13.8 % | +4.6 % | +1.0 % | **+12.8 pts** ✓ | ✓ | ✓ | 35 % / 67 % ✓ |
| R3 très cher | 53 % / 34 % / 13 % | 8 | +13.8 % | +5.5 % | -0.0 % | **+13.8 pts** ✓ | ✓ | ✓ | 34 % / 49 % ✓ |

## 2. Conception — S&P 500 quotidien, 1990 → aujourd'hui (rendements de prix ; critère décisif)

| Candidat | Part vert / orange / rouge | Épisodes rouges | 3 ans après vert | après orange | après rouge | Écart vert − rouge (a) | (b) rouge ≤ 25 % | (c) ≥ 3 épisodes | (d) p90 baisse 24 mois orange / rouge |
|---|---|---|---|---|---|---|---|---|---|
| v0.6 (référence) | 12 % / 78 % / 11 % | 9 | +12.8 % | +9.6 % | +8.5 % | **+4.4 pts** ✗ | ✓ | ✓ | 36 % / 31 % ✗ |
| R1 cher et tendu | 8 % / 88 % / 5 % | 4 | +12.3 % | +9.7 % | +8.7 % | **+3.6 pts** ✗ | ✓ | ✓ | 34 % / 17 % ✗ |
| R2 cher et cassé | 8 % / 78 % / 14 % | 22 | +12.3 % | +9.6 % | +10.1 % | **+2.2 pts** ✗ | ✓ | ✓ | 25 % / 49 % ✓ |
| R3 très cher | 8 % / 24 % / 69 % | 16 | +12.3 % | +11.5 % | +8.9 % | **+3.3 pts** ✗ | ✗ | ✓ | 18 % / 35 % ✓ |

Pour comparaison, même période en mensuel (rendements réels, mise en œuvre le mois suivant) :

| Candidat | Part vert / orange / rouge | Épisodes rouges | 3 ans après vert | après orange | après rouge | Écart vert − rouge (a) | (b) rouge ≤ 25 % | (c) ≥ 3 épisodes | (d) p90 baisse 24 mois orange / rouge |
|---|---|---|---|---|---|---|---|---|---|
| R1 cher et tendu | 2 % / 93 % / 5 % | 13 | +13.7 % | +9.5 % | +6.1 % | **+7.6 pts** ✓ | ✓ | ✓ | 30 % / 14 % ✗ |
| R2 cher et cassé | 2 % / 80 % / 18 % | 18 | +13.7 % | +9.5 % | +7.4 % | **+6.3 pts** ✓ | ✓ | ✓ | 21 % / 38 % ✓ |
| R3 très cher | 2 % / 28 % / 70 % | 9 | +13.7 % | +11.4 % | +8.1 % | **+5.6 pts** ✓ | ✗ | ✓ | 12 % / 30 % ✓ |

## 3. Nasdaq-100 et MSCI World (conception quotidienne, 1990 → aujourd'hui ; valorisation du S&P 500 en proxy)

Nasdaq-100 :

| Candidat | Part vert / orange / rouge | Épisodes rouges | 3 ans après vert | après orange | après rouge | Écart vert − rouge (a) | (b) rouge ≤ 25 % | (c) ≥ 3 épisodes | (d) p90 baisse 24 mois orange / rouge |
|---|---|---|---|---|---|---|---|---|---|
| v0.6 (référence) | 16 % / 71 % / 14 % | 11 | +16.7 % | +16.4 % | +8.7 % | **+8.1 pts** ✓ | ✓ | ✓ | 28 % / 68 % ✓ |
| R1 cher et tendu | 13 % / 80 % / 8 % | 9 | +16.8 % | +16.0 % | +8.3 % | **+8.5 pts** ✓ | ✓ | ✓ | 31 % / 68 % ✓ |
| R2 cher et cassé | 13 % / 73 % / 14 % | 24 | +16.8 % | +15.3 % | +19.4 % | **-2.6 pts** ✗ | ✓ | ✓ | 34 % / 44 % ✓ |
| R3 très cher | 13 % / 21 % / 66 % | 16 | +16.8 % | +17.5 % | +14.2 % | **+2.7 pts** ✗ | ✗ | ✓ | 18 % / 42 % ✓ |

MSCI World :

| Candidat | Part vert / orange / rouge | Épisodes rouges | 3 ans après vert | après orange | après rouge | Écart vert − rouge (a) | (b) rouge ≤ 25 % | (c) ≥ 3 épisodes | (d) p90 baisse 24 mois orange / rouge |
|---|---|---|---|---|---|---|---|---|---|
| v0.6 (référence) | 13 % / 79 % / 8 % | 5 | +10.0 % | +7.9 % | +5.2 % | **+4.8 pts** ✗ | ✓ | ✓ | 37 % / 37 % ✗ |
| R1 cher et tendu | 9 % / 86 % / 4 % | 4 | +10.9 % | +7.7 % | +6.6 % | **+4.2 pts** ✗ | ✓ | ✓ | 37 % / 20 % ✗ |
| R2 cher et cassé | 9 % / 73 % / 18 % | 22 | +10.9 % | +7.3 % | +9.7 % | **+1.2 pts** ✗ | ✓ | ✓ | 29 % / 48 % ✓ |
| R3 très cher | 9 % / 23 % / 68 % | 16 | +10.9 % | +8.1 % | +7.1 % | **+3.7 pts** ✗ | ✗ | ✓ | 21 % / 38 % ✓ |

## 4. Pourquoi : le marché américain est « cher » 88 % du temps depuis 1990

Le CAPE du S&P 500 a été au-dessus de son 80e percentile historique (depuis 1881) **88 % du temps depuis 1990**, contre
**20 %** sur 1920-1989. Avant 1990, « cher » était un état rare suivi de rendements faibles ; depuis, c'est l'état normal du
marché, et attendre parce que le marché était cher a coûté cher. Les épisodes rouges des candidats l'illustrent :
- R1 (cher et tendu) depuis 1990 : 1995-1999 (le marché a encore beaucoup monté), 2004, 2011, fin 2020-2021, 2024 ;
- R2 (cher et cassé) : 2000-2003 et fin 2007-2008 (justes), mais aussi 1994, 1998, 2015-2016, fin 2018, mars-mai 2020,
  2022 et 2025 (achats différés juste avant de fortes hausses) ;
- R3 (très cher) : 69 % du temps depuis 1990.

## 5. Observations **non retenues** (pour ne pas choisir après avoir vu les résultats)

- **R1 sur le Nasdaq-100 passe** (écart +8.5 %, rouge 8 % du temps).
  Le protocole sélectionne sur le S&P 500 ; l'adopter pour le seul Nasdaq-100 serait un choix fait après coup. Il est affiché
  comme **drapeau d'information** (« cher et tendu ») avec ses statistiques, et inscrit comme hypothèse à tester en avant.
- R2 passe en mensuel sur 1990-2026 mais pas en quotidien : résultat fragile, dépendant de la mise en œuvre.

## 6. Rendement réel attendu à 10 ans (affichage, pas une règle)

Régression du rendement réel annualisé à 10 ans (dividendes inclus) sur le logarithme du CAPE, 1881-2016 :
rendement ≈ 24,6 % − 6,5 % × ln(CAPE) ; R² = 0,26 ; environ 13 décennies indépendantes.
- CAPE 40,8 (septembre 2026) → **+0,4 %/an** ; fourchette 80 % des écarts historiques : −5,8 % à +6,4 %/an.
- Précédents à ce niveau (CAPE 36,7 à 44,9 avec issue connue) : 31 mois, tous en 1998-2001 ; rendement réalisé −5,9 % à
  +1,1 %/an, médiane −3,1 %.
- **Hors échantillon** (modèle réestimé chaque mois avec les seules issues connues) : corrélation prévu/réalisé
  0.49 sur 1950-2016 ; sur 1990-2016 le classement des périodes est bon (corrélation 0,91) mais le niveau a été
  **trop pessimiste de 5.2 points par an** en moyenne (+0.6 point sur 1950-1989).
  L'application affiche donc l'estimation, sa fourchette et ce biais.

## 7. Bitcoin — 2014 → aujourd'hui (pas de hors-échantillon possible)

| Règle | Part vert / orange / rouge | Épisodes rouges | 3 ans après vert | après orange | après rouge | Écart | Critères |
|---|---|---|---|---|---|---|---|
| B1 (MVRV ≥ 3) | 17 % / 78 % / 4 % | 3 | +125.8 % | +53.9 % | +9.3 % | +116.5 pts | ✓ |
| Sensibilité MVRV ≥ 3,7 | 17 % / 82 % / 0 % | 0 | +125.8 % | +49.7 % | +4.1 % | +121.7 pts | ✗ |
| v0.6 (référence) | 34 % / 57 % / 9 % | 4 | +78.5 % | +49.5 % | +33.1 % | +45.4 pts | — |

Rouges B1 : novembre-décembre 2017, décembre 2020-avril 2021. Verts B1 : 2015, fin 2018-avril 2019, juin 2022-mars 2023,
août-septembre 2023. Le seuil d'origine 3,7 n'a jamais été atteint depuis 2014 : les sommets sont de moins en moins extrêmes,
et B1 n'a pas allumé le rouge aux sommets de novembre 2021, mars 2024 et octobre 2025. **Le rouge Bitcoin peut donc manquer le
prochain sommet** ; c'est écrit sur la carte.

## 8. Conséquences dans l'application (v1.0)

- Indices : vert (V ≤ 40, ou baisse ≥ 25 % avec peur ≥ 80e percentile) ; sinon orange. « Cher » (V ≥ 80) et le rendement réel
  attendu à 10 ans sont affichés comme information, sans règle de report. Le drapeau « cher et tendu » est affiché sur le
  Nasdaq-100 avec ses statistiques et l'avertissement qu'il n'est pas une règle.
- Conduite : versements maintenus ; montants exceptionnels en trois tranches mensuelles (orange) ; réserve déployée en vert ;
  levier plafonné par la couleur (vert 15 %, orange 10 %) et ramené à 5 % quand la tendance est cassée.
- Bitcoin : B1.
- Ce qui sort des règles et reste affiché en contexte : dette sur marge, excess CAPE yield, allocation des ménages (AIAE),
  momentum 12 mois, critère GSY (indices et Bitcoin), taux de financement, Fear & Greed, z-scores Bitcoin.

## Erratum (9 novembre 2026, après relecture indépendante)

Les tableaux ci-dessus sont inchangés ; trois phrases de commentaire étaient inexactes.

- §7 : « le seuil d'origine 3,7 n'a jamais été atteint depuis 2014 » est **faux**. Le MVRV a été ≥ 3,7 pendant 22 jours depuis 2014
  (14 en décembre 2017, maximum 4,72 le 7 décembre ; 8 en février 2021, maximum 3,96). La ligne « Sensibilité MVRV ≥ 3,7 » affiche
  « 0 % » et « 0 » épisode par arrondi (0,5 % du temps) et parce qu'aucune séquence n'atteint 20 jours. La conclusion (la sensibilité
  3,7 échoue au critère du nombre d'épisodes) est inchangée.
- §7 : la liste des rouges B1 omettait mai-juin 2017 (rouge brut du 19 mai au 23 juin, prix d'environ 2 000 à 2 650 $, suivi d'une
  hausse d'environ ×8 jusqu'en décembre) et de courtes séquences en août, octobre et novembre 2017.
- Le plan « trois tranches » du module de validation ne déployait pas des tranches égales (33 %, 22 %, 17 %, 17 %, 11 %). Corrigé :
  trois tranches égales coûtent −0,01 % de capital final contre l'investissement immédiat sur le S&P 500 (−0,1 % sur le Nasdaq-100) ;
  attendre le vert, −9,6 % et −28,8 %.

Point-in-time : dans le moteur quotidien, le CAPE d'un mois était utilisé dès la fin du mois, avant la publication de l'indice des prix
(vers le 15 du mois suivant). Corrigé ; le protocole recalculé (moteurs quotidien et mensuel) donne des écarts modifiés d'au plus 0,11 point et les mêmes conclusions
(aucun candidat retenu sur le S&P 500, B1 adopté). Le moteur mensuel 1920-2026 n'était pas concerné (mise en œuvre le mois suivant) ; la reconstitution quotidienne du protocole l'était, corrigée aussi.
Limite non corrigée : les bénéfices mensuels de Shiller sont interpolés (annuels avant 1926) ; le décalage de 3 mois peut laisser
passer 1 à 2 mois d'information, davantage au début du hors-échantillon. Vu l'ampleur des écarts hors échantillon (+13 à +19 points),
la conclusion n'en dépend pas, mais ce n'est pas démontré ici.
