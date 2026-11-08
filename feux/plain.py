"""Couche « mode simple » : les mêmes règles et les mêmes chiffres, expliqués à quelqu'un qui n'a jamais lu
un bilan. Tout est déterministe (gabarits), donc gratuit et sans risque d'invention."""
from __future__ import annotations

import pandas as pd

from .config import rules

COLOR_FR = {"green": "vert", "orange": "orange", "red": "rouge"}

# ----------------------------------------------------------------------------------------------
# 1. Phrase du jour par actif
# ----------------------------------------------------------------------------------------------
_PLAIN_NAMES = {"sp500": "les grandes entreprises américaines (S&P 500)", "ndx": "les valeurs technologiques américaines (Nasdaq-100)",
                "world": "les grandes entreprises mondiales (MSCI World)", "btc": "le Bitcoin"}


def _why_index(row: pd.Series) -> str:
    bits = []
    if row["V"] == row["V"] and row["V"] >= 80:
        bits.append("les actions se paient cher par rapport aux bénéfices des dix dernières années")
    if bool(row.get("gsy", False)):
        bits.append("le marché a plus que doublé en deux ans et la hausse s'accélère")
    elif row["X"] == row["X"] and row["X"] >= 90:
        bits.append("les cours se sont beaucoup éloignés de leur moyenne des 200 derniers jours")
    if row["E"] == row["E"] and row["E"] >= 80:
        bits.append("les investisseurs américains empruntent beaucoup pour acheter des actions")
    if row["drawdown"] >= 0.25 and row["P"] == row["P"] and row["P"] >= 80:
        bits.append("le marché a perdu plus d'un quart de sa valeur et la peur est forte")
    if row["V"] == row["V"] and row["V"] <= 40:
        bits.append("les actions se paient peu cher par rapport à leur histoire")
    return " ; ".join(bits)


def simple_index(key: str, row: pd.Series) -> str:
    name = _PLAIN_NAMES.get(key, key)
    c = row.get("color_confirmed", row["color"])
    why = _why_index(row)
    if c == "red":
        s = f"Feu rouge sur {name} : {why}. Ce n'est pas le moment de placer une grosse somme d'un coup ni d'ajouter du levier. Les versements habituels continuent."
    elif c == "green":
        s = f"Feu vert sur {name} : {why}. C'est historiquement un bon moment pour investir une réserve, en plusieurs fois."
        if bool(row.get("falling_knife", False)):
            s += " Attention : la baisse n'est peut-être pas finie (prix sous la moyenne des 10 derniers mois), d'où l'étalement sur six mois."
    else:
        s = f"Feu orange sur {name} : rien d'extrême" + (f" ({why})" if why else "") + ". On investit normalement, sans grosse somme d'un coup et sans ajouter de levier."
    if bool(row.get("trend_broken", False)):
        s += " La tendance est cassée (dernier mois clôturé sous la moyenne des 10 mois) : tout produit à levier est ramené au minimum."
    return s


def simple_btc(row: pd.Series) -> str:
    c = row.get("color_confirmed", row["color"])
    dd = f"{100 * row['drawdown']:.0f} %"
    if c == "red":
        s = (f"Feu rouge sur le Bitcoin : son prix est très au-dessus de ses repères des quatre dernières années et la hausse "
             f"s'accélère ou les spéculateurs à levier paient très cher pour rester acheteurs. Pas d'achat exceptionnel, pas de société « proxy » à levier.")
    elif c == "green":
        s = (f"Feu vert sur le Bitcoin : il est à {dd} sous son record et nettement sous ses repères habituels (prix moyen des quatre dernières "
             f"années, prix moyen payé par les détenteurs). Historiquement, c'est dans ces zones qu'on achète, par tiers.")
    else:
        s = f"Feu orange sur le Bitcoin : ni euphorie ni capitulation (à {dd} sous son record). Versements habituels seulement."
    if bool(row.get("trend_broken", False)):
        s += " Il est sous sa moyenne des 200 jours : les sociétés « proxys » à levier (type Strategy) sont à éviter tant que c'est le cas."
    return s


# ----------------------------------------------------------------------------------------------
# 2. « Ce mois-ci » : actions concrètes déduites des couleurs et des règles de conduite
# ----------------------------------------------------------------------------------------------
def monthly_actions(states: dict[str, dict]) -> list[str]:
    """states : clé -> {name, color, trend_broken, falling_knife}. Retourne 4 à 6 phrases d'action."""
    r = rules()["conduct"]
    acts = ["Versements programmés : maintenus sur tous les supports, quelle que soit la couleur."]
    idx = {k: v for k, v in states.items() if k != "btc"}
    reds = [v["name"] for v in idx.values() if v["color"] == "red"]
    greens = [v["name"] for v in idx.values() if v["color"] == "green"]
    if reds:
        acts.append(f"Montants exceptionnels (prime, héritage, épargne accumulée) : pas sur {', '.join(reds)} tant que le feu est rouge ; "
                    "ils attendent sur un support sans risque (fonds euros, livret, monétaire).")
    if greens:
        acts.append(f"Réserve : à déployer par tiers sur trois mois sur {', '.join(greens)}"
                    + (" (par sixièmes sur six mois : la baisse n'est peut-être pas finie)" if any(v.get("falling_knife") for v in idx.values() if v["color"] == "green") else "") + ".")
    oranges = [v["name"] for v in idx.values() if v["color"] == "orange"]
    if oranges and not greens:
        acts.append(f"Montants exceptionnels : possibles par tiers sur trois mois sur {', '.join(oranges)} (feu orange).")
    worst = "red" if reds else ("orange" if oranges else "green")
    cap = r[worst]["leverage_cap_share_equities"]
    broken = [v["name"] for v in idx.values() if v.get("trend_broken")]
    if broken:
        acts.append(f"Levier (ETF x2) : tendance cassée sur {', '.join(broken)} → ramener le x2 à {100 * r['trend_broken']['leverage_cap_share_equities']:.0f} % au plus de la poche actions sous 5 jours de bourse (dans le PEA, sans impôt).")
    else:
        acts.append(f"Levier (ETF x2) : tendance intacte, mais plafond de {100 * cap:.0f} % de la poche actions (feu {COLOR_FR[worst]}) ; aucun renfort.")
    b = states.get("btc")
    if b:
        if b["color"] == "green":
            acts.append("Bitcoin : feu vert → un achat exceptionnel est possible, par tiers" + (" ; mais sous sa moyenne 200 jours, donc aucune société « proxy » à levier." if b.get("trend_broken") else "."))
        elif b["color"] == "red":
            acts.append("Bitcoin : feu rouge → aucun achat exceptionnel, aucun « proxy » à levier.")
        else:
            acts.append("Bitcoin : feu orange → versements habituels seulement.")
    acts.append(f"Avant tout ordre exceptionnel : les cinq questions du journal et {r['exceptional_order_checklist_hours']} h de délai (python -m feux decide).")
    return acts


def headline(states: dict[str, dict]) -> str:
    idx = {k: v for k, v in states.items() if k != "btc"}
    reds = [v["name"] for v in idx.values() if v["color"] == "red"]
    greens = [v["name"] for v in idx.values() if v["color"] == "green"]
    if reds and not greens:
        a = "marchés actions chers et un peu euphoriques (rouge)" if len(reds) == len(idx) else f"rouge sur {', '.join(reds)}"
    elif greens:
        a = f"vert sur {', '.join(greens)}" + (f", rouge sur {', '.join(reds)}" if reds else "")
    else:
        a = "marchés actions sans excès (orange)"
    b = states.get("btc", {}).get("color")
    bt = {"green": "Bitcoin déprimé (vert)", "red": "Bitcoin en euphorie (rouge)", "orange": "Bitcoin sans excès (orange)"}.get(b, "")
    return f"Aujourd'hui : {a} ; {bt}." if bt else f"Aujourd'hui : {a}."


# ----------------------------------------------------------------------------------------------
# 3. Glossaire : chaque chiffre du tableau de bord, en une phrase pour tous + ce que la règle en fait
# ----------------------------------------------------------------------------------------------
GLOSSARY = [
    ("Percentile", "Où se situe la valeur du jour par rapport aux 25 dernières années. « 98e percentile » = plus haut que 98 % des jours des 25 dernières années. "
                   "C'est ainsi que chaque indicateur est ramené à une échelle de 0 à 100.", "Famille V : rouge possible à partir de 80, vert à 40 ou moins."),
    ("CAPE (PER de Shiller)", "Le prix payé pour 1 € de bénéfice moyen des dix dernières années, corrigé de l'inflation. Comme le prix d'un appartement rapporté aux loyers "
                              "qu'il a réellement rapportés sur dix ans. À 39, on paie 39 € pour 1 € de bénéfice ; la moyenne historique est autour de 17.",
     "Entre dans la famille « valorisation » (V). Il prédit bien les rendements à dix ans, pas le moment des baisses : il ne déclenche jamais le rouge seul."),
    ("Excess CAPE Yield", "Le rendement des actions (1 / CAPE) moins ce que rapporte l'État sur dix ans après inflation. Il répond à l'objection « les actions sont chères "
                          "parce que les taux sont bas » : quand il est proche de zéro, les actions ne paient presque rien de plus qu'un placement sans risque.", "Famille V."),
    ("Allocation actions des ménages (AIAE)", "La part de leur patrimoine financier que les Américains ont déjà placée en actions. Quand tout le monde est déjà investi, "
                                             "il reste peu d'acheteurs ; historiquement c'est l'indicateur le plus lié aux rendements des dix années suivantes.",
     "Famille V. Record historique en 2026 (56 %)."),
    ("Écart à la moyenne 200 jours (MM200)", "Le prix d'aujourd'hui comparé au prix moyen des 200 derniers jours de bourse (environ dix mois). Très au-dessus = le marché "
                                             "s'est emballé ; en dessous = la tendance baisse.", "Famille « extension » (X), rouge possible au 90e percentile. Sert aussi de drapeau de tendance pour le Bitcoin."),
    ("Performance 12 mois", "La hausse ou la baisse sur un an. Une hausse très forte est un signe d'emballement, une baisse forte de découragement.", "Famille X."),
    ("Critère GSY (bulle)", "Du nom des chercheurs Greenwood, Shleifer et You : quand un marché a plus que doublé en deux ans et que la hausse s'accélère, une chute "
                            "d'au moins 40 % a suivi dans environ un cas sur deux (sur 90 ans de données). Ce n'est pas une prédiction de date, c'est une probabilité.",
     "Drapeau « bulle » : il suffit à rendre rouge un marché déjà cher."),
    ("Dette sur marge", "L'argent que les investisseurs américains empruntent à leur courtier pour acheter des actions. Quand il grimpe de plus de 50 % en un an "
                        "(2000, 2007, 2021), c'est l'euphorie.", "Famille « euphorie » (E), rouge possible au 80e percentile de la croissance annuelle."),
    ("VIX", "Le thermomètre de la peur : le prix des assurances contre une baisse de la bourse américaine. Au-dessus de 30, la peur est forte.",
     "Famille « peur » (P) : sert seulement à confirmer un feu vert de capitulation, jamais à déclencher le rouge."),
    ("Spread de crédit", "Le supplément d'intérêt que paient les entreprises moyennement solides par rapport à l'État américain. Il grimpe quand les prêteurs ont peur.", "Famille P."),
    ("Baisse depuis le plus haut (drawdown)", "De combien le marché est descendu depuis son record. −25 % ou pire, avec la peur, c'est la « capitulation ».",
     "Vert de capitulation : baisse ≥ 25 % ET peur ≥ 80e percentile (Bitcoin : ≥ 50 % et indice Fear & Greed ≤ 25)."),
    ("Tendance 10 mois", "Règle de Meb Faber : si le dernier mois a fini au-dessus de la moyenne des 10 derniers mois, la tendance est intacte ; en dessous, elle est cassée. "
                         "Sur 110 ans, cette règle a divisé par deux les pires pertes du marché américain, en sortant environ 30 % du temps.",
     "Pilote le levier : tendance cassée → l'ETF x2 est ramené à 0-5 % sous 5 jours, quelle que soit la couleur."),
    ("Levier x2 et érosion", "Un ETF x2 double la variation de chaque journée. En marché agité sans tendance, il perd de la valeur même si l'indice finit au même niveau "
                             "(monter de 10 % puis baisser de 10 % laisse l'indice à −1 %, le x2 à −4 %). En 2000-2002, un x2 Nasdaq aurait perdu 98,5 %.",
     "D'où la règle : levier seulement quand la tendance est intacte, et plafonné selon la couleur (15 % en vert, 10 % en orange, 5 % en rouge)."),
    ("Z-score (Bitcoin)", "Nombre d'écarts à la normale des quatre dernières années : +1 = nettement au-dessus de l'habituel, −1 = nettement en dessous. On l'utilise pour le "
                          "Bitcoin parce que ses cycles s'atténuent : un seuil fixe copié de 2017 ne marche plus.", "Rouge possible à +1,0 ; vert à −0,5."),
    ("Prix / moyenne 200 semaines", "Le prix du Bitcoin rapporté à son prix moyen des quatre dernières années. Historiquement, cette moyenne a servi de plancher aux "
                                    "marchés baissiers (2015, 2018, 2020) ; elle a été enfoncée d'un tiers en 2022 et touchée à l'été 2026.", "Famille V du Bitcoin (en z-score)."),
    ("MVRV", "Le prix du Bitcoin rapporté au prix moyen auquel les détenteurs actuels ont acheté. À 2, le détenteur moyen a doublé sa mise (envie de vendre) ; sous 1, il est en perte "
             "(capitulation). Ses sommets baissent à chaque cycle : 5,9 (2017), 4,0 (2021), 2,3 à 2,7 (2025).", "Famille V du Bitcoin (en z-score)."),
    ("Taux de financement", "Ce que paient les spéculateurs à levier pour rester acheteurs de Bitcoin sur les marchés à terme. Très élevé = euphorie à crédit (début 2021) ; "
                            "nul ou négatif = personne ne veut du risque.", "Euphorie Bitcoin : rouge possible si ≥ 90e percentile et prix cher. Absent en novembre 2021 et octobre 2025."),
    ("Fear & Greed", "Indice de 0 (peur extrême) à 100 (avidité extrême) qui agrège volatilité, volumes et réseaux sociaux du monde crypto.", "Confirme la capitulation (moyenne 30 jours ≤ 25)."),
    ("EV/EBIT (actions)", "Combien d'années de résultat d'exploitation il faut pour payer l'entreprise entière, dettes comprises. 15 = quinze ans. On le compare à l'historique de "
                          "la société elle-même sur dix ans, pas à une norme universelle.", "Famille V d'une action, en percentile 10 ans."),
    ("P/FCF (actions)", "Combien d'années de cash réellement dégagé (après investissements) il faut pour payer la capitalisation boursière. Plus fiable que le bénéfice comptable.", "Famille V d'une action."),
    ("ROIC, FCF/RN, dette nette/EBITDA (qualité)", "Le rendement de l'argent investi dans l'entreprise (bon au-dessus de 10 %), la part du bénéfice qui se transforme en cash (bon "
                                                    "au-dessus de 70 %), le nombre d'années de résultat pour rembourser la dette (prudent sous 2).",
     "Filtre éliminatoire : une société qui le rate ne peut jamais être verte, quel que soit son prix."),
    ("DCF inversé", "Au lieu de deviner ce que vaut l'entreprise (toujours faux), on calcule la croissance annuelle du cash que le prix actuel suppose pendant dix ans, et on "
                    "la compare à ce que l'entreprise a fait ces cinq dernières années. Si le prix suppose 25 %/an et qu'elle a fait 10 %, on paie un rêve.",
     "Signal de prudence (implicite > 1,5 × réalisé), pas une couleur."),
    ("Point-in-time", "Chaque chiffre n'est utilisé qu'à partir du jour où il était réellement publié (les comptes trimestriels arrivent avec trois mois de retard, la dette sur marge "
                      "avec trois semaines). Sans cela, un test historique triche sans le savoir.", "Appliqué partout, y compris dans la validation 1985-2026."),
]
