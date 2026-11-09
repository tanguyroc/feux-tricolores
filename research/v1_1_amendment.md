# Amendement v1.1 — le « rouge extrême » des indices

Adopté le 9 novembre 2026. Pré-inscrit le même jour (`prereg/2026-11-09-v1.1.json`, empreinte dans `prereg/HASHES.txt`).

## 1. La règle

- **Rouge extrême** si V ≥ 98 : le CAPE du S&P 500, calculé avec les seuls bénéfices publiés à la date (point-in-time),
  est plus élevé que dans 98 % des mois connus depuis 1881 (fenêtre croissante, comme le vert).
- Préséance : rouge extrême, puis vert de capitulation, puis vert de valorisation, puis orange.
- S'applique aux trois indices, car V est commun (le CAPE du S&P 500 sert de repère au Nasdaq-100 et au MSCI World).
- Confirmation : 5 jours de bourse, comme les autres couleurs.

**Conduite** (`rules.yaml`, `conduct.red`) : versements réguliers maintenus vers les mêmes supports ; montants exceptionnels
étalés en six tranches mensuelles au lieu de trois ; levier plafonné à 5 % de la poche actions ; **aucune vente motivée par le feu**.

## 2. Statut : une règle de jugement, pas une règle validée

Le protocole v1.0 (§8.4) avait testé, avant calcul, des rouges partant du 80e percentile : aucun ne passait depuis 1990.
Ce seuil de 98 a été choisi **après** avoir vu l'histoire, à la demande de l'utilisateur (« si le PER est délirant comme
lors de la bulle internet, ça justifie un rouge ? »). Les chiffres ci-dessous sont donc **descriptifs** : ils montrent
pourquoi la règle est plausible, ils ne prouvent pas qu'elle marchera. Seul le suivi en avant le dira.

## 3. Ce que dit l'histoire

### 3.1 Mensuel, 1911-2026 (Shiller, rendement total réel, dividendes réinvestis)

Rendement annualisé médian après un mois, selon V ce mois-là (n = nombre de mois, qui se chevauchent).

| Horizon | V ≥ 98 | 80 ≤ V < 98 | 40 < V < 80 | V ≤ 40 |
|---|---|---|---|---|
| 1 an | +9,1 % (n = 100, 39 % négatifs) | +8,0 % | +9,8 % | +10,5 % |
| 3 ans | +1,9 % (n = 94, 46 % négatifs) | +7,5 % | +7,2 % | +10,9 % |
| 5 ans | −2,8 % (n = 92, 67 % négatifs) | +7,0 % | +8,1 % | +10,0 % |
| 10 ans | +0,3 % (n = 85, 48 % négatifs) | +5,3 % | +9,0 % | +10,1 % |

Même sens sur les deux moitiés : 1911-1989, V ≥ 98 → −22,4 %/an à 3 ans (n = 20, 1929) ; 1990-2026 → +4,4 %/an à 3 ans,
−2,1 %/an à 5 ans, contre +9,5 % et +9,3 % pour 80-98.

**À un an, rien** : le rouge extrême ne dit pas quand le marché baisse.

### 3.2 Épisode par épisode (premier mois à V ≥ 98, rendement réel annualisé ensuite)

| Début | 1 an | 3 ans | 5 ans | 10 ans | Pire baisse sur 5 ans |
|---|---|---|---|---|---|
| octobre 1928 | +33,3 % | −14,2 % | −4,9 % | +2,5 % | −77 % |
| février 1965 | +7,3 % | +1,6 % | −0,7 % | −2,6 % | −21 % |
| juillet 1995 | +14,8 % | +27,1 % | +20,4 % | +7,2 % | −12 % |
| avril 2021 | −0,7 % | +3,2 % | +7,6 % | — | −24 % |
| novembre 2024 | +12,1 % | — | — | — | — |

Quatre épisodes achevés. Un (1995) a été suivi de cinq excellentes années : un investisseur qui aurait vendu en
juillet 1995 aurait manqué environ +20 %/an réels jusqu'en 2000. C'est la raison de la conduite légère.

### 3.3 Quotidien, 1990-2026 (backtest du dépôt, rendement de prix)

Le rouge a été allumé 22 % des jours (7 séquences de 20 jours ou plus, en réalité trois épisodes : 1995-2001, 2021-2022,
2025-2026). Rendement médian à 3 ans, rouge contre orange : S&P 500 −2,1 points par an, Nasdaq-100 −5,4, MSCI World −2,9.
Part des cas négatifs à 3 ans : 35 % contre 14 % (S&P 500). La vraie différence est dans la queue gauche, pas dans la médiane.

Coût de la conduite (plan type, 1 000 €/mois + 10 000 €/an depuis 1990) : étaler en six tranches au lieu de trois en rouge
change la valeur finale de −0,1 % (S&P 500), −0,3 % (Nasdaq-100), +0,1 % (MSCI World). Elle ne coûte presque rien ; elle
ne rapporte presque rien non plus. Son intérêt est ailleurs : ne pas engager d'un coup une grosse somme au sommet de
l'histoire, et le dire clairement.

### 3.4 Préséance sur la capitulation

Sur le Nasdaq-100, 108 jours (14 avril 2000 – 14 février 2001) cumulaient V ≥ 98 et une baisse de 25 % avec une peur forte :
ils étaient verts en v1.0, ils sont rouges en v1.1. Le Nasdaq-100 a ensuite perdu environ 75 %. Ce choix est fait en
connaissant cette suite : c'est un jugement (« une baisse qui laisse le marché parmi les 2 % des mois les plus chers n'est
pas une capitulation »), pas une découverte.

## 4. Fragilités connues

- **Seuil au ras** : au 6 novembre 2026, V = 98,1. Le feu peut basculer entre rouge et orange au gré des cours ; la
  confirmation de 5 jours limite le clignotement (9 changements de couleur confirmée sur le S&P 500 depuis 2021).
- **Repère commun** : le Nasdaq-100 et le MSCI World héritent du CAPE américain. Pour le World (environ 70 % d'actions
  américaines) c'est raisonnable ; pour le Nasdaq-100, sa propre valorisation peut être plus ou moins tendue.
- **Régime** : depuis 1990, le marché a été au-dessus du 98e percentile de son histoire 20 % des mois. Si le niveau
  « normal » des CAPE a durablement monté (taux, marges, composition de l'indice), ce rouge s'allumera souvent pour rien.

## 5. Suivi en avant (critères écrits avant tout résultat)

Hypothèses inscrites dans `prereg/2026-11-09-v1.1.json` :

1. À 3 et 5 ans, le rendement après un jour rouge est inférieur à celui après un jour orange. **Échec** si, sur les
   épisodes postérieurs au 9 novembre 2026, l'écart est nul ou de signe contraire.
2. À 1 an, le rouge ne dit rien : il ne doit jamais servir à vendre.

Révision : la règle n'est pas modifiée avant novembre 2029 (premier horizon de 3 ans), sauf erreur de calcul, documentée
dans `prereg/ERRATA.md`.
