# Journal des modifications des règles

## 2026-11-09 — v1.1 (rouge extrême des indices ; zones, secteurs et thèmes en information)

**Rouge extrême des indices** (`rules.yaml`, `indices.valuation.red_min: 98` ; `research/v1_1_amendment.md`).
- Rouge si le CAPE du S&P 500 est plus élevé que dans 98 % des mois connus depuis 1881 ; prioritaire sur le vert de capitulation.
- Conduite : versements maintenus vers les mêmes supports ; montants exceptionnels en six tranches mensuelles au lieu de trois ;
  levier ≤ 5 % ; aucune vente motivée par le feu.
- **Règle de jugement**, seuil choisi après avoir vu l'histoire : 1911-2026, mois à V ≥ 98 suivis de +1,9 %/an réels à 3 ans et
  −2,8 %/an à 5 ans (médianes ; +7 à +11 % ailleurs), rien à 1 an ; quatre épisodes achevés, dont 1995-1997 suivi de trois à cinq
  excellentes années. 1990-2026 (quotidien) : rouge 22 % du temps, rendement médian à 3 ans inférieur à l'orange de 2,1 (S&P 500),
  5,4 (Nasdaq-100) et 2,9 points (MSCI World) ; 35 % de cas négatifs à 3 ans contre 14 % (S&P 500). Coût de l'étalement sur un plan
  type : −0,1 % (S&P 500).
- Préséance : les 108 jours du Nasdaq-100 d'avril 2000 à février 2001 (baisse ≥ 25 %, peur forte, V ≥ 98), verts en v1.0, sont rouges.
- Pré-inscription : `prereg/2026-11-09-v1.1.json` (hypothèses et critère d'échec écrits le jour de l'adoption).
- Allumé aujourd'hui sur les trois indices (V = 98,1, au ras du seuil).
- Indices sans valorisation : « pas de feu » au lieu d'orange (sauf capitulation mesurée).
- Témoin : « rouge si et seulement si V ≥ 98 » remplace « plus de rouge depuis la v1.0 ».

**Zones, secteurs et thèmes : la valorisation devient une information, plus un feu.**
- Test sur 16 pays, 1870-2020 (`research/zones_test_protocol.md`, écrit avant calcul ; `research/zones_test_results.md`) : la mesure
  « prix / dividendes réels moyens sur 10 ans contre ses 20 dernières années » a été suivie de +1,9 point par an à 5 ans pour les
  années « bon marché », sous le seuil de 2 points fixé d'avance (corrélation de rang −0,13, IC 90 % [−0,20 ; −0,07] ; 13 pays sur 16).
- Affichage : très bon marché, bon marché, dans sa moyenne, cher, très cher, contre son propre passé ; « non mesurable » avec sa raison.
- Témoin : aucune zone, aucun secteur, aucun thème ne porte de feu de couleur.

## 2026-11-09 — v1.0.2 (données à jour, « pas de feu », zones géographiques ; règles des indices et du Bitcoin inchangées)

**Données à jour.**
- L'API « companyfacts » de la SEC n'avait pas intégré plusieurs dépôts récents : 10-Q 2026 de Citigroup (trois) et de NextEra
  (deux), 20-F 2026 de TSMC, Toyota, Sony et BHP. Ces dépôts sont désormais lus directement dans leur instance XBRL, datés de leur
  dépôt. Plus aucune des 91 sociétés suivies à la SEC n'est en « comptes anciens » (TSMC passe de comptes 2024 à 2025, Citi de
  2025 au 3e trimestre 2026).
- VIX : les clôtures Yahoo complètent FRED, qui publie le lendemain. Prix du Bitcoin : Yahoo complète Coin Metrics pour les jours
  pas encore publiés (le MVRV reste celui de Coin Metrics, sa date est affichée à part). Un cours en séance n'est jamais pris pour
  une clôture.
- Onglet Validation : tableau de fraîcheur de chaque source (dernière valeur, âge, rythme de publication).

**« Pas de feu » (gris) quand les données ne permettent pas de juger**, au lieu d'un orange par défaut, toujours avec la raison
écrite :
- actions sans comptes à la SEC (11) ;
- valorisation contre son passé non mesurable (moins de 5 ans de multiples positifs : Palantir, CrowdStrike, GE Vernova, Shopify) ;
- comparaison aux autres impossible (Gilead, Deere : dette non publiée sous une forme exploitable ; Welltower : seule foncière) ;
- comptes de plus de 15 mois ;
- société bon marché dont la solidité n'est pas mesurable ;
- Bitcoin sans MVRV ou sans moyenne 200 semaines (2010-2014, exclus des statistiques comme dans le protocole) ;
- zones, secteurs et thèmes sans mesure.

Témoins : chaque « pas de feu » a une raison, aucune couleur sans mesure.

**Feux des zones, secteurs et thèmes (indicatifs, non testés), mêmes seuils que les indices, pas de rouge.**
- 13 zones ajoutées (ETF cotés en dollars) : Euro Stoxx 50, Europe développée, Royaume-Uni, Allemagne, France, Japon, Chine, Inde,
  Corée du Sud, Taïwan, Amérique latine, Brésil, marchés émergents.
- Mesure :
  - pour un secteur ou un thème d'au moins 5 sociétés du Top 100 : la médiane de leurs valorisations, chacune contre ses dix
    dernières années ;
  - sinon : le prix de l'ETF rapporté à ses dividendes réels moyens sur 10 ans (un « CAPE » fait avec les dividendes), contre son
    propre passé (10 à 20 ans) ;
  - pas de feu si l'historique est insuffisant, si les dividendes sont trop faibles (moins de 1 %/an) ou s'ils ne sont plus publiés
    depuis plus de 13 mois (Inde).
- Limites écrites dans l'application : une hausse du taux de distribution fait paraître une zone moins chère qu'elle ne l'est ; les
  dividendes des matières premières sont cycliques.
- Aujourd'hui :
  - zones vertes : Japon, Chine, Taïwan, Amérique latine, Brésil ; « chères » : Euro Stoxx 50, Europe, Royaume-Uni ;
  - secteurs verts : Communication, Immobilier coté ; « chers » : Matériaux, Services aux collectivités ;
  - thèmes : Énergies propres vert, semi-conducteurs et logiciels orange, quatre sans feu (dividendes trop faibles).
- Le thème semi-conducteurs suit l'ETF SOXX (dividendes) au lieu de l'indice ^SOX.

## 2026-11-09 — v1.0.1 (relecture indépendante : corrections de données et de textes ; règles inchangées)
Une relecture indépendante du code et des données (agent n'ayant pas participé à la conception, sans accès réseau, sur une copie)
a reproduit les défauts suivants. Tous sont corrigés ; aucun seuil de `rules.yaml` n'a changé.

**Actions (comptes SEC) — ce qui changeait des chiffres affichés :**
- **Dette manquante comptée zéro.** 25 des 76 sociétés industrielles n'avaient pas de dette à long terme à la dernière date (concepts
  XBRL non reconnus) : Oracle affichait 7,2 Md de dette au lieu de 125 Md, Verizon 24 Md au lieu de 166 Md ; Verizon, Philip Morris et
  Amphenol passaient à tort le test de dette. Nouveau modèle de dette (total publié, ou dette à long terme totale + court terme, ou
  parts non courante + courante) ; une dette introuvable reste **inconnue** (ni valeur d'entreprise, ni test de dette), sauf pour les
  sociétés sans aucun concept de dette depuis trois ans et sans charges d'intérêts (Arista, Intuitive Surgical, Palantir : dette nulle).
- **Investissements (capex)** : les incorporels (licences, fréquences, logiciels) s'ajoutent aux corporels au lieu d'en être une
  alternative (AstraZeneca 2,8 → 5,9 Md, Novartis 1,6 → 3,9 Md, Verizon fréquences comprises) ; un capex ancien n'est plus reporté
  indéfiniment (Verizon utilisait celui de 2020, ConocoPhillips celui de 2023, Alibaba celui de 2022) : flux libre inconnu à la place.
- **Fusion des concepts** : tri stable, et pour chaque période la valeur **publiée en premier** (un tri instable figeait parfois le
  résultat d'Oracle à mai 2025). Une différence de cumuls n'associe jamais deux concepts différents (une mise en commun essayée en
  cours de correction produisait des trimestres faux chez Union Pacific, Linde, AT&T et Morgan Stanley : abandonnée).
- **Trimestres** : exercices de 52/53 semaines pris en compte (4e trimestre de 16 semaines : flux d'exploitation de PepsiCo 12,4 → 14,6 Md,
  PepsiCo repasse le test de cash ; Costco à jour de son exercice d'août) ; une somme sur 12 mois exige quatre trimestres consécutifs.
- **Déposants annuels (20-F)** : le bilan expire au même rythme que les flux (avant : chaque année, quelques semaines avec dette et
  trésorerie nulles chez Shell, TSMC, SAP, AstraZeneca, HSBC, Alibaba, dans l'historique qui sert au percentile).
- **Berkshire Hathaway** jugée en P/E et P/B (son « résultat d'exploitation » comprend les plus-values de son portefeuille).
- **Comptes anciens** : le feu affiché passe à l'orange immédiatement (il pouvait garder sa couleur quatre jours).
- Nombre d'actions : la référence du nettoyage est une valeur confirmée par sa voisine (Alibaba : page de garde 2026 dix fois trop petite).
- Seconde vérification par le même relecteur, après correction : chiffres de dette conformes aux comptes pour Oracle, Verizon,
  Philip Morris, Amphenol, Coca-Cola, Exxon, Tesla, Thermo Fisher, AT&T (sans double compte de la part courante) ; aucune fuite
  d'information future sur 630 contrôles par troncature ; dates de disponibilité avancées là où une valeur publiée plus tôt existait
  (capex 2025 de Coca-Cola connu en février et non en octobre, dette de PepsiCo de fin 2022 connue en février) ; « intérêts inconnus =
  zéro » remplacé par la plus forte charge d'intérêts réellement publiée sur trois ans (Berkshire était jugée sans dette en 2016-2020).
- Effet : 41 sociétés solides au lieu de 45 ; Coca-Cola V 43 → 62 ; Verizon, Philip Morris et Amphenol échouent au test de dette ;
  Chevron n'est plus vert même en brut (V 24 → 41) ; seule Accenture reste verte.

**Indices et Bitcoin (effet négligeable, mais point-in-time) :** le CAPE d'un mois n'est utilisé qu'après la publication de l'indice des
prix (vers le 15 du mois suivant) ; l'écart de crédit Baa est daté du jour ouvré suivant ; la barre fictive du dimanche du MSCI World
est écartée ; le drapeau de tendance des secteurs et thèmes est décalé d'un jour comme celui des indices ; les jours Bitcoin sans
MVRV ou sans moyenne 200 semaines (2010-2014) n'affichent plus un motif vert ou rouge. Protocole v1.0 recalculé : écarts de
rendement modifiés d'au plus 0,11 point, mêmes conclusions.

**Textes corrigés :** le MVRV a dépassé 3,7 pendant 22 jours depuis 2014 (pas « jamais ») ; ses sommets (7,7 en 2011, 5,9 en 2013,
4,7 en 2017, 4,0 en 2021) ; le rouge Bitcoin de mai-juin 2017 manquait à la liste des épisodes ; le vert des indices n'a été suivi
que de +1 à +3 points par an (et sur le Nasdaq-100 de nouvelles baisses en 2000-2002), pas d'« un bon moment » ; plan « trois
tranches » réellement en trois tranches égales (pratiquement identique à l'investissement immédiat) ; la ligne « rouge : levier 5 % »
retirée du tableau de conduite (le rouge ne concerne que le Bitcoin) ; chiffre de l'hypothèse Nasdaq-100 « cher et tendu » : −7,8 points
contre les autres jours (et non −8,5, qui était l'écart vert − rouge ; voir `prereg/ERRATA.md`).

**Application :** part de levier = montant en ETF à levier / poche actions (un Bitcoin ×2 la faussait) ; alerte si un produit Bitcoin à
levier est détenu en rouge ou en tendance cassée ; textes saisis échappés ; un portefeuille importé incomplet ne bloque plus le Journal ;
une vente d'action est aussi « en période de stress » quand le marché l'est.

**Garde-fous :** témoins sans succès vacant (listes vides = échec), dette et flux libre connus, aucune valeur d'entreprise avec une dette
inconnue, empreintes des pré-inscriptions recalculées (bloquant), fraîcheur du VIX, de l'écart de crédit et des données de Shiller
(bloquant), cours des actions. Pré-inscription : seulement à la date du jour ; l'hypothèse « actions » est désormais suivie.
Tests unitaires exécutés avant chaque publication.

**Limites restantes, documentées :** les bénéfices mensuels de Shiller sont interpolés (annuels avant 1926), si bien que le décalage
de 3 mois peut laisser passer 1 à 2 mois d'information, davantage au début du hors-échantillon 1920-1989 ; les dettes de Deere et
Shopify, et le capex d'Alibaba, NextEra, TotalEnergies et ConocoPhillips sont publiés sous des concepts propres à la société : inconnus ;
celui de Nvidia ne l'est sous des concepts standard que depuis fin 2023, et celui d'Arista mêle deux concepts d'un trimestre à l'autre :
leur test de cash reste « n.d. ». Le suivi de l'hypothèse « actions » compare des cours ajustés des divisions aux deux bouts.

## 2026-11-09 — v1.0 (refonte selon un protocole pré-enregistré)
Déclencheur : en v0.6, le rouge des indices ne passait pas son propre critère (écart vert − rouge à 3 ans < 5 points sur le
S&P 500 et le MSCI World), et la consigne de « challenger la pertinence des signaux ».

**Méthode.** Protocole écrit et poussé **avant tout calcul** (`research/v1_protocol.md`, commit e92b515, sha256 `08e5abbb…df44`) :
trois candidats rouges, critères chiffrés, règle de décision écrite d'avance (§8.4), et un hors-échantillon jamais utilisé
(S&P Composite mensuel 1920-1989, rendements réels dividendes inclus). Résultats publiés tels quels : `research/v1_results.md`.

**Résultat.** Les trois candidats passent largement sur 1920-1989 (écart +13 à +19 points) mais **aucun ne passe sur le S&P 500
depuis 1990** (+2,2 à +3,6 points) : le CAPE a été au-dessus de son 80e percentile historique 88 % du temps depuis 1990, contre
20 % avant. Attendre parce que le marché était cher a coûté cher. Bitcoin : la règle B1 passe.

**Indices.**
- Plus de rouge. « Cher » (V ≥ 80) devient une information, sans règle de report. Vert : V ≤ 40, ou baisse ≥ 25 % avec peur ≥ 80e percentile.
- V = percentile du CAPE point-in-time contre **tout l'historique depuis 1881** (une fenêtre glissante finit par trouver normal ce qui est cher).
- Rendement réel attendu à 10 ans (régression sur ln(CAPE)) affiché avec sa fourchette et son biais hors échantillon
  (trop pessimiste de 5,2 points par an depuis 1990) : aujourd'hui environ +0,7 %/an, fourchette −5,6 à +6,6 %.
- Drapeau d'information « cher et tendu » (R1 : passe sur le Nasdaq-100 seul ; non retenu, choisi après coup ; inscrit comme hypothèse en avant).
- Contexte séparé de la règle (dette sur marge, excess CAPE yield, allocation des ménages, momentum, GSY). Drapeau de tendance décalé d'un jour.
- Conduite : montants exceptionnels en trois tranches mensuelles en orange (« cher » compris), réserve déployée en vert ;
  levier plafonné à 15 % en vert, 10 % en orange (« cher » compris, conformément au §8.4), 5 % si la tendance est cassée.
- Plan type 1990-2026 (1 000 €/mois + 10 000 €/an) : trois tranches mensuelles égales contre tout investir tout de suite, pratiquement
  identique ; attendre le vert, −9,6 % (S&P 500) et −28,8 % (Nasdaq-100) (chiffres corrigés en v1.0.1, voir plus haut).

**Bitcoin.** Règle B1 en niveaux (vert si MVRV < 1 ou prix < moyenne 200 semaines ; rouge si MVRV ≥ 3) au lieu des z-scores
glissants. Le MVRV n'a dépassé 3,7 que 22 jours depuis 2014 (corrigé en v1.0.1) et B1 n'a allumé le rouge ni en novembre 2021 ni en mars 2024
ni en octobre 2025 : il peut manquer le prochain sommet (écrit sur la carte). État du jour : orange (v0.6 : vert).

**Actions.**
- **Défaut corrigé, présent depuis la v0.5** : les nombres d'actions de la SEC n'étaient pas ajustés des divisions alors que les prix
  Yahoo le sont. La capitalisation passée des sociétés ayant divisé leurs actions était 4 à 20 fois trop faible avant la division,
  donc leur valorisation paraissait chère contre leur passé à tort (Nvidia V 76 → 4, Netflix 75 → 2, Amazon 59 → 2).
- Correctifs du 9 novembre (après la mise en place des témoins) : division appliquée selon la **date de dépôt** et non de clôture
  (Alphabet : capitalisation 20 fois trop forte de juillet à octobre 2022) ; nombres d'actions déclarés en millions ou en milliers
  corrigés (McDonald's 2024-2026 : V 34 → 20 ; Royal Bank of Canada 2019) ; valeurs isolées aberrantes écartées (Wells Fargo juillet 2023,
  BHP 2020-2021 déclaré pour la seule société australienne, coquille Linde plc 2018, CrowdStrike avant 2021). Témoin quotidien :
  aucun saut de plus de 50 % en un jour du nombre d'actions implicite sur dix ans (91 sociétés).
- Flux libre net de la rémunération en actions ; deux lentilles (son passé, les autres grandes sociétés) ; feu indicatif par
  conjonction (rouge : chère sous les deux lentilles **et** tendue ; vert : bon marché sous les deux **et** solide) ; retour aux
  actionnaires, dilution sur 3 ans, accruals, marge brute ; comptes de plus de 15 mois → orange. TSMC, Toyota, Sony et BHP sont dans
  ce cas : leurs rapports annuels 2026 sont déposés, mais leurs chiffres IFRS n'apparaissent pas (encore) dans l'API de la SEC.
- Secteurs sans couleur (drapeaux et valorisation médiane seulement) ; 7 thèmes.
- Valorisation « par le bas » de chaque indice (P/E agrégé des plus grosses sociétés et position contre leur propre passé), en contexte.

**Test en avant.** Archive quotidienne (`history/`) et pré-inscription mensuelle datée et hachée (`prereg/`) de ce que les règles
affirment, confrontées au réalisé à un an et trois ans dans l'onglet Validation. Premiers verdicts : 9 novembre 2027 et 9 novembre 2029.

**Repris de Kairys Lite et Kairys Alpha.** Contrôles avant publication et témoins (`python -m feux check`) : publication
« fail-closed » (un contrôle bloquant en échec arrête la mise à jour, le site garde la dernière version sûre, une alerte part) ;
minute de déclenchement non ronde (22 h 17 UTC) ; fraîcheur affichée (« il y a X h ») ; sources sur chaque carte ; points
d'attention par ligne et « test d'échange » dans Mon portefeuille ; alerte de concentration (une action > 12 % de la poche risquée) ;
trois questions de vente et délai de 7 jours pour une vente en période de stress ; revue écrite à 90 jours de chaque décision.

**Défaut d'affichage corrigé.** Du 8 novembre au soir (v0.6) au 9 novembre, une erreur JavaScript (déclaration placée dans un
`switch`) arrêtait le script de la page : le tableau des actions, les secteurs, Mon portefeuille et le Journal restaient vides ; les
cartes du jour, générées côté serveur, s'affichaient normalement. Un test de fumée de la page (navigateur simulé, `tests/page_smoke.js`)
s'exécute désormais avant chaque publication et la bloque à la moindre erreur. Les contrôles de couverture des actions ne bloquent
pas la publication (une panne de la SEC ne doit pas empêcher la mise à jour des feux des indices et du Bitcoin).

**Archivé.** Règles et résultats v0.6 (`archive/`) ; la robustesse v0.6 est remplacée par le protocole et la pré-inscription.

## 2026-11-08 — v0.6 (couche d'honnêteté ; aucune règle modifiée)
Suite à une revue critique indépendante des signaux (lecteur n'ayant pas participé à la conception), vérifiée point par point :
- **Validation** : le tableau affiche désormais l'écart vert − rouge à 3 ans face au critère pré-enregistré (≥ 5 pts) — **non atteint
  pour le S&P 500 (4,4 pts) et le MSCI World (4,8 pts)** ; le nombre d'épisodes (≥ 20 jours) derrière chaque couleur ; le 90e
  percentile des baisses à 24 mois (sur le S&P 500, plus profond après un jour orange qu'après un rouge) ; et un encadré « ce que ce
  tableau ne doit pas cacher » : 2007 orange sur les trois indices, règles écrites/gelées/testées le même jour (pas de valeur probante),
  effectifs faibles. Le protocole prévoyait de simplifier une règle qui échoue : c'est l'objet de la refonte v1.0 proposée.
- **Cartes** : « Rouge depuis le 01/10/2025 (401 jours) : l'indice a fait +9,9 % depuis » (rétroaction factuelle de l'état en cours) ;
  « Valorisation : celle du S&P 500 (proxy) » sur Nasdaq-100 et MSCI World ; dates de référence de la dette sur marge (fin septembre,
  publiée fin octobre) et de l'allocation des ménages (30 juin) à côté des valeurs ; « euphorie » remplacé par « achats à crédit ».
- **Bitcoin** : la phrase est générée à partir des niveaux (prix 1,12× sa moyenne 200 semaines, MVRV 1,41) et dit explicitement que le
  vert vient de la comparaison aux quatre dernières années, pas d'une capitulation, et que cette zone a couvert un tiers du temps depuis 2014.
- **Actions** : date des derniers comptes lus dans le tableau, avertissement au-delà de 15 mois (TSMC, Toyota).
- **Journal** : les statistiques historiques citent leur effectif en épisodes.
- **Thèmes** : 7 au lieu de 2, choisis là où les bulles se sont historiquement formées et avec ≥ 15 ans d'historique (semi-conducteurs,
  éditeurs de logiciels, biotechnologies, énergies propres, mines d'or, constructeurs de maisons, défense). Drapeaux de prix seulement.
- **Top 100 en un coup d'œil** : part des sociétés au-dessus de leur MM200 et en tendance cassée, répartition des feux, concentration
  (10 premières = 47 % du Top 100, Apple 10 %). Faits de contexte, hors règles.
- **Univers** : appartenance au S&P 500 (positions officielles SPY : 74 sociétés, 67 % du poids), au Nasdaq-100 (29) et au MSCI World (95),
  pour une future valorisation bottom-up des indices.
- Textes corrigés : dette nette/EBITDA « prudent sous 2,5 » (glossaire, runbook).

## 2026-11-08 — v0.5 (actions : solidité pluriannuelle, dégradé de valorisation, secteurs ; règles des indices et du Bitcoin inchangées)
Constat déclencheur : 92 actions orange sur 102 et 42 « échecs » qualité sur 86. Diagnostic : un tiers des échecs venait de défauts
de données (concept XBRL abandonné et figé — KLA sans résultat d'exploitation depuis 2015, Qualcomm/Broadcom/UnitedHealth/Visa
sans fonds propres depuis 2019 ; amortissements publiés en deux morceaux chez Abbott, Gilead, Merck ; flux de trésorerie
« continuing operations » chez Disney, AT&T, RTX ; Visa capitalisée avec 469 M d'actions de 2010 au lieu de ~1,9 Md),
un autre tiers de banques jugées comme des industrielles, le reste de la grille elle-même (instantanée et binaire).
1. **Grille de solidité** (`stocks.quality`) : les trois tests sont désormais jugés sur des **moyennes pluriannuelles**
   (rentabilité du capital et conversion en cash : moyenne 5 ans, au moins 3 ; dette nette / EBITDA : EBITDA moyen 3 ans).
   Une année de capex exceptionnel ou une charge d'acquisition ne fait plus « échouer » une société solide à elle seule ;
   inversement une rentabilité récente ne blanchit pas cinq ans de faiblesse (AstraZeneca, Salesforce, RTX restent non solides).
   Seuil dette nette/EBITDA **2,0 → 2,5** (seuil Fundsmith, identique à Kairys Alpha). ROIC ≥ 10 % et FCF/RN ≥ 0,7 inchangés.
   Les tests échoués sont **nommés** (« dette 3,1× », « cash 0,42× ») au lieu d'un « échec » global.
2. **Modes par industrie** : banques, courtiers, assureurs, crédit à la consommation → P/E, P/B et rentabilité des fonds propres
   (moyenne 5 ans), quelle que soit la disponibilité d'un « résultat d'exploitation » ; **réseaux de paiement et Berkshire
   restent industriels** ; **foncières** : valorisation P/E-P/B, grille non applicable (jamais vertes).
3. **Données** : une valeur comptable n'est plus reportée au-delà de 400 jours (730 pour les déposants annuels de 20-F, 800 pour
   le nombre d'actions) ; fusion des concepts de bilan (le plus récent l'emporte) ; amortissements = dépréciation + amortissement
   des incorporels à défaut de concept combiné ; résultat avant impôt = résultat net + impôt à défaut (TotalEnergies) ;
   actions ≈ flottant déclaré / cours pour les sociétés à actions multi-classes sans décompte exploitable (Visa, Berkshire) ;
   fusion de plusieurs CIK (ExxonMobil, BlackRock : nouvelles holdings) ; CIK sans comptes XBRL → prix seul (SK hynix).
   La date des derniers comptes lus est affichée (TSMC, Toyota : le 20-F 2025/2026 n'est pas encore dans l'API).
   Effet : 89 sociétés valorisées (86), 52 solides sur 89 (44 « OK » sur 86 avec l'ancienne grille, dont des faux positifs),
   5 sociétés avec un test non calculable (pétrolières et NextEra sans concept de capex standard ; CrowdStrike en perte).
4. **Dégradé** : le feu reste à trois couleurs et à ses règles de conjonction (inchangées) ; l'application ajoute une jauge
   0-100 et cinq paliers de lecture (très bon marché ≤ 20, bon marché, dans sa moyenne, cher, très cher > 80), un filtre par
   palier et la distribution de l'univers. Un orange « très cher mais pas tendu » se distingue ainsi d'un orange « bon marché
   mais pas solide ». Aucune règle d'action n'est attachée aux paliers.
5. **Secteurs et thèmes** (`themes`) : les onze secteurs GICS (ETF SPDR, VNQ et VOX pour l'historique long) remplacent les
   trois « thèmes de votre portefeuille ». Pour chaque secteur : drapeaux de prix de l'ETF **et** valorisation médiane des
   sociétés du Top 100 du secteur (au moins 3), combinées avec les règles de conjonction des indices. **Non backtesté** :
   lecture de contexte, ne gouverne ni le levier ni les montants. Semi-conducteurs et éditeurs de logiciels restent des thèmes
   (drapeaux seulement).

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

## 2026-11-08 — v0.4 (une application, pas des rapports ; actions = Top 100 mondial ; aucun seuil de règle modifié)
- **Application monopage** `docs/index.html` : onglets Aujourd'hui · Actions Top 100 · Mon portefeuille · Journal · Validation ·
  Règles & glossaire ; mode simple / détaillé global ; données embarquées (fonctionne hors ligne, publiée par GitHub Pages).
  Les rapports de validation et de robustesse sont intégrés (plus de pages séparées à ouvrir).
- **Mon portefeuille** (dans le navigateur, rien n'est transmis) : lignes avec levier et enveloppe, exposition réelle (x2 compté
  double), part exposée à un feu rouge, part de levier contre le plafond de la couleur du jour, test de résistance en euros,
  écart aux cibles avec les bandes de la couleur, répartition du versement mensuel vers les poches sous-pondérées non rouges.
- **Journal** dans le navigateur : intention + cinq questions + rappel historique, confirmation verrouillée 48 h, export.
- **Univers Top 100 mondial** : 100 premières pondérations du MSCI ACWI (positions quotidiennes publiques de l'ETF SPDR MSCI ACWI,
  State Street), une ligne par société, symboles résolus par ISIN (Yahoo), éligibilité PEA approchée par le pays, CIK SEC par nom
  et ticker quand `SEC_USER_AGENT` est défini. `stocks.yaml` ne sert plus qu'aux compléments et surcharges (Strategy, SoftBank, Oracle).
- Module actions : conversion de devise prix/comptes (pence, dollars, euros), repli « prix seul » sans accès SEC.
