# Protocole d'évaluation des règles v1.0 — écrit avant tout calcul

Rédigé le 9 novembre 2026, avant d'avoir calculé un seul résultat pour les candidats ci-dessous. Ce fichier est commité
et poussé sur GitHub avant le premier calcul : la date du commit et son empreinte font foi. Toute modification ultérieure
de ce fichier sera visible dans l'historique git ; aucune ne sera faite avant la publication des résultats.

## 0. Pourquoi une v1.0

Les règles v0.x (gelées le 8 novembre 2026) **échouent** à leur propre critère d'acceptation pré-enregistré
(écart de rendement médian annualisé à 3 ans entre jours verts et jours rouges ≥ 5 points) sur le S&P 500 (4,4 pts)
et le MSCI World (4,8 pts). Le protocole v0 prévoyait de simplifier une règle qui échoue. Une revue indépendante a de plus
montré que : la famille « euphorie » (dette sur marge) portait seule 55 % des jours rouges du S&P 500 ; le critère de bulle
GSY n'a jamais été le seul déclencheur d'un rouge d'indice ; le sommet de 2007 était orange ; le Bitcoin était vert un tiers
du temps parce que ses z-scores sont relatifs aux quatre dernières années.

## 1. Ce que je sais déjà (déclaration de biais)

Je connais les grands épisodes de marché (1929, 1937, 1973-74, 1987, 2000, 2008, 2020, 2022), je sais que le CAPE était
élevé en 1929, 1966, 2000 et 2021, et j'ai vu les résultats du backtest v0.x sur 1990-2026 ainsi que les diagnostics de la
revue. Je n'ai calculé **aucun** résultat des candidats R1, R2, R3, B1 sur aucune période. La période 1920-1989 n'a servi à
concevoir aucune règle des feux : elle est « hors échantillon » au sens où rien n'y a été ajusté, pas au sens où je l'ignore.

## 2. Données

- **Mensuel long** : fichier de Robert Shiller `ie_data.xls` (version téléchargée le 8 novembre 2026) : prix moyen mensuel
  du S&P Composite, prix « réel rendement total » (dividendes réinvestis, déflaté par le CPI), bénéfices, CPI.
  CAPE point-in-time = prix réel / moyenne sur 120 mois des bénéfices réels **décalés de 3 mois** (même définition que v0.x).
- **Peur mensuelle** : écart Moody's Baa − Aaa (FRED `BAA`, `AAA`, mensuel depuis 1919).
- **Quotidien** : séries v0.x (Yahoo, FRED, Shiller), inchangées.

## 3. Périodes

- **Hors échantillon (mensuel)** : janvier 1920 → décembre 1989, S&P Composite (Shiller), rendements réels dividendes inclus.
- **Conception (quotidien)** : janvier 1990 → dernier jour disponible, moteur de backtest v0.x (rendements de prix, sans
  dividendes : biais identique pour toutes les couleurs, signalé), S&P 500, Nasdaq-100, MSCI World.
- **Conception (mensuel)** : janvier 1990 → dernier mois, même calcul que le hors-échantillon, publié pour comparaison.
- Bitcoin : janvier 2014 → dernier jour (aucun hors-échantillon possible ; dit tel quel).

## 4. Définitions communes aux candidats indices

- **V (valorisation, en niveau)** : percentile du CAPE point-in-time parmi **toutes** les valeurs mensuelles disponibles depuis
  janvier 1881 jusqu'à la date (fenêtre croissante, minimum 360 mois). Au quotidien : CAPE « vivant » (dernier CAPE mensuel
  connu × prix du jour / prix moyen de ce mois) comparé au même historique. Les trois indices utilisent la valorisation du
  S&P 500 (proxy affiché comme tel pour le Nasdaq-100 et le MSCI World).
- **T (tendance cassée)** : dernière clôture mensuelle sous sa moyenne des 10 derniers mois (Faber 2007) ; en mensuel,
  prix moyen du mois (Shiller) sous sa moyenne 10 mois.
- **X (tension)** : percentile de l'écart du prix à sa moyenne des 200 jours (quotidien) ou à sa moyenne 10 mois (mensuel),
  fenêtre croissante (minimum 15 ans en quotidien, 30 ans en mensuel).
- **P (peur)** : quotidien = v0.x inchangé (médiane des percentiles VIX et spread Baa − taux 10 ans) ; mensuel = percentile
  de l'écart Baa − Aaa, fenêtre croissante, minimum 120 mois (disponible à partir de janvier 1929).
- **Baisse** : depuis le plus haut historique du prix (nominal en quotidien, réel rendement total en mensuel).
- **Vert (identique pour tous les candidats)** : V ≤ 40, ou (baisse ≥ 25 % et P ≥ 80). Le vert de capitulation a priorité
  sur le rouge, le rouge a priorité sur le vert de valorisation (ordre v0.x).
- La dette sur marge, l'excess CAPE yield, l'allocation des ménages (AIAE), le momentum 12 mois et le critère GSY **sortent
  des règles d'indices** et restent affichés comme contexte.

## 5. Candidats indices (aucun autre ne sera testé)

- **R1 « cher et tendu »** : rouge si V ≥ 80 et X ≥ 90.
- **R2 « cher et cassé »** : rouge si V ≥ 80 et T (la valorisation et la tendance disent la même chose ; Asness, Ilmanen et
  Maloney 2017 sur la combinaison valeur + momentum).
- **R3 « très cher »** : rouge si V ≥ 90.
- **Référence** : règles v0.x gelées (quotidien seulement, puisqu'elles utilisent des séries qui n'existent pas avant 1990).

## 6. Mesures (pour chaque candidat et chaque période)

Part du temps par couleur ; nombre d'épisodes distincts par couleur (séquences ≥ 1 mois en mensuel, ≥ 20 jours en quotidien) ;
rendement médian annualisé à 1, 3 et 5 ans après chaque couleur ; baisse maximale dans les 24 mois suivants (médiane et
90e percentile) par couleur ; changements de couleur par an.

## 7. Critères d'acceptation (tous requis, dans **chacune** des deux périodes S&P 500 : hors échantillon mensuel et conception quotidienne)

- (a) écart de rendement médian annualisé à 3 ans vert − rouge ≥ 5 points (critère v0.x) ;
- (b) rouge ≤ 25 % du temps (critère v0.x) ;
- (c) au moins 3 épisodes rouges distincts ;
- (d) 90e percentile de la baisse à 24 mois après un rouge ≥ celui après un orange (le rouge doit signaler le risque de forte
  baisse au moins aussi bien que l'orange).

## 8. Règle de décision

1. Un candidat est **retenu** s'il passe (a)-(d) sur les deux périodes du S&P 500.
2. Parmi les retenus, on choisit celui dont le plus petit des deux écarts (a) est le plus grand ; à moins d'un point près,
   le plus simple l'emporte (R3, puis R2, puis R1).
3. La règle choisie s'applique telle quelle au Nasdaq-100 et au MSCI World ; leurs résultats (conception seulement) sont
   publiés ; un indice qui échoue à (a) ou (b) affiche « rouge non validé sur cet indice ».
4. **Si aucun candidat ne passe** : le vert est conservé ; le rouge devient un état d'information « cher » (V ≥ 80) sans règle
   de report ; la conduite devient « montants exceptionnels toujours en trois tranches mensuelles, sauf vert » ; le levier
   reste gouverné par la tendance. Cette issue sera publiée telle quelle.
5. Les résultats complets de tous les candidats sont publiés, y compris ceux qui ne sont pas retenus.

## 9. Bitcoin (conception 2014 → aujourd'hui, pas de hors-échantillon)

- **B1** : vert si MVRV < 1 ou prix < moyenne des 200 semaines ; rouge si MVRV ≥ 3 (les détenteurs ont en moyenne triplé
  leur mise) ; orange sinon. Le taux de financement, le Fear & Greed, le critère GSY et les z-scores sortent de la règle
  (contexte). La tendance (moyenne 200 jours) continue de gouverner les « proxys » à levier.
- Sensibilité publiée, non choisissable : rouge si MVRV ≥ 3,7 (seuil d'origine de Mahmudov et Puell, 2018).
- Critères : (a) écart vert − rouge à 3 ans ≥ 5 points ; (b) rouge ≤ 30 % du temps ; (c) au moins 2 épisodes rouges.
  B1 est adopté s'il passe ; sinon le rouge Bitcoin devient « non validé » et seul le vert est conservé.

## 10. Ce qui n'est pas soumis à ce protocole

Le module actions (100 sociétés) et les secteurs/thèmes ne sont pas backtestés : ils restent « indicatifs, non backtestés ».
Leur refonte (valorisation sous deux lentilles, FCF net de la rémunération en actions, rendement actionnarial, secteurs sans
couleur) est une amélioration de lecture, pas une règle validée.

## 11. Hors-échantillon futur

À partir de la v1.0, l'état de chaque actif et les statistiques historiques associées sont archivés chaque jour et hachés
(SHA-256) ; ils seront confrontés aux rendements réalisés le 9 novembre 2027, 2028 et 2029. C'est le seul test qui ne
dépend pas de ce que je sais du passé.
