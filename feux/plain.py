"""Couche « mode simple » : les mêmes règles et les mêmes chiffres, expliqués à quelqu'un qui n'a jamais lu
un bilan. Tout est déterministe (gabarits), donc gratuit et sans risque d'invention."""
from __future__ import annotations

import pandas as pd

from .config import rules
from .explain import fr_num

COLOR_FR = {"green": "vert", "orange": "orange", "red": "rouge", "none": "sans feu (données insuffisantes)"}

# ----------------------------------------------------------------------------------------------
# 1. Phrase du jour par actif
# ----------------------------------------------------------------------------------------------
_PLAIN_NAMES = {"sp500": "les grandes entreprises américaines (S&P 500)", "ndx": "les valeurs technologiques américaines (Nasdaq-100)",
                "world": "les grandes entreprises mondiales (MSCI World)", "btc": "le Bitcoin"}


def _fr_date(s) -> str:
    try:
        d = pd.Timestamp(s)
        return f"{d.day:02d}/{d.month:02d}/{d.year}"
    except Exception:
        return str(s)


def _why_index(row: pd.Series) -> str:
    """Phrase « pourquoi » d'un indice (v1.0) : seules la valorisation en niveau et la capitulation font la couleur."""
    bits = []
    proxy = " (mesurée sur le S&P 500, faute d'équivalent pour cet indice)" if bool(row.get("valuation_is_proxy", False)) else ""
    if row["drawdown"] >= 0.25 and row["P"] == row["P"] and row["P"] >= 80:
        bits.append("le marché a perdu plus d'un quart de sa valeur et la peur est forte")
    if row["V"] == row["V"] and row["V"] <= 40:
        bits.append(f"les actions se paient peu cher par rapport à toute leur histoire depuis 1881{proxy}")
    return " ; ".join(bits)


def _er_sentence(row: pd.Series) -> str:
    er, lo, hi = row.get("er10"), row.get("er10_lo"), row.get("er10_hi")
    if er is None or er != er:
        return ""
    return (f"Rendement réel attendu sur dix ans selon le CAPE : environ {100 * er:+.0f} %/an (fourchette historique {100 * lo:+.0f} à {100 * hi:+.0f} %), "
            f"contre 6,7 %/an en moyenne depuis 1881 ; depuis 1990 ce modèle a été trop pessimiste d'environ 5 points par an.")


def since_sentence(row: pd.Series, what: str = "l'indice") -> str:
    """« Rouge depuis le 01/10/2025 (401 jours) : l'indice a fait +9,9 % depuis. » — la rétroaction factuelle de l'état en cours."""
    if not row.get("state_since") or row.get("perf_since_state") is None or row.get("perf_since_state") != row.get("perf_since_state"):
        return ""
    c = COLOR_FR.get(row.get("color_confirmed", row.get("color")), "")
    return f"{c.capitalize()} depuis le {_fr_date(row['state_since'])} ({int(row.get('state_days', 0))} jours) : {what} a fait {100 * row['perf_since_state']:+.1f} % depuis."


def simple_index(key: str, row: pd.Series) -> str:
    name = _PLAIN_NAMES.get(key, key)
    c = row.get("color_confirmed", row["color"])
    why = _why_index(row)
    proxy = " (valorisation du S&P 500 utilisée comme repère)" if bool(row.get("valuation_is_proxy", False)) else ""
    if c == "green":
        s = f"Feu vert sur {name} : {why}. Depuis 1990, les jours verts ont été suivis de rendements à trois ans un peu meilleurs que les jours orange (+1 à +3 points par an selon l'indice), parfois après de nouvelles baisses : c'est le moment d'engager une réserve, en plusieurs fois."
        if bool(row.get("falling_knife", False)):
            s += " Attention : la baisse n'est peut-être pas finie (prix sous la moyenne des 10 derniers mois), d'où l'étalement sur six mois."
    elif bool(row.get("cher", False)):
        s = (f"Feu orange sur {name}, marché cher{proxy} : les actions américaines se paient plus cher que dans {row['V']:.0f} % des mois depuis 1881. "
             f"Ce n'est pas une raison d'attendre : depuis 1990 le marché a été cher 88 % du temps et attendre a coûté cher. "
             f"On investit normalement, les montants exceptionnels en trois tranches mensuelles, sans ajouter de levier au-delà du plafond. "
             + _er_sentence(row))
    else:
        s = f"Feu orange sur {name} : rien d'extrême. On investit normalement, les montants exceptionnels en trois tranches mensuelles."
    if row.get("bu_pe") and row.get("bu_pe_sp500") and key != "sp500":
        s += (f" Par le bas : ses {int(row['bu_n'])} plus grosses sociétés se paient {row['bu_pe']:.1f} fois leurs bénéfices des 12 derniers mois "
              f"(S&P 500 : {row['bu_pe_sp500']:.1f}), et se situent en moyenne au {row['bu_v_own']:.0f}e percentile de leur propre passé.")
    elif row.get("bu_pe") and key == "sp500":
        s += (f" Par le bas : ses {int(row['bu_n'])} plus grosses sociétés se paient {row['bu_pe']:.1f} fois leurs bénéfices des 12 derniers mois "
              f"et se situent en moyenne au {row['bu_v_own']:.0f}e percentile de leur propre passé : chères contre un siècle d'histoire, pas contre leurs dix dernières années.")
    if bool(row.get("cher_tendu", False)):
        s += (" Drapeau d'information « cher et tendu » : les cours sont aussi très au-dessus de leur moyenne des 200 jours (sur le Nasdaq-100, "
              "ce drapeau a été suivi de rendements plus faibles depuis 1990, mais il n'a pas marché sur le S&P 500 ; ce n'est pas une règle).")
    if bool(row.get("trend_broken", False)):
        s += " La tendance est cassée (dernier mois clôturé sous la moyenne des 10 mois) : tout produit à levier est ramené au minimum."
    return fr_num(s)


def _btc_levels(row: pd.Series) -> str:
    """Les deux repères en niveau, tels qu'ils sont : le verdict vient de z-scores relatifs aux quatre dernières années,
    et ceux-ci peuvent dire « déprimé » alors que le prix est au-dessus des repères (fin 2026)."""
    bits = []
    r = row.get("ratio_200w")
    if r == r and r is not None:
        bits.append(f"prix à {r:.2f}× sa moyenne des 200 semaines" + (" (au-dessus)" if r > 1 else " (en dessous)"))
    m = row.get("mvrv")
    if m == m and m is not None:
        bits.append(f"MVRV {m:.2f}" + (" (les détenteurs sont en gain en moyenne)" if m > 1 else " (les détenteurs sont en perte en moyenne)"))
    return ", ".join(bits)


def simple_btc(row: pd.Series) -> str:
    c = row.get("color_confirmed", row["color"])
    dd = f"{100 * row['drawdown']:.0f} %"
    lv = _btc_levels(row)
    if c == "red":
        s = (f"Feu rouge sur le Bitcoin : {lv}. Les détenteurs ont en moyenne triplé leur mise, ce qui n'a été vu que lors des bulles de 2011, "
             f"2013, 2017 et début 2021. Pas d'achat exceptionnel, pas de société « proxy » à levier.")
    elif c == "green":
        s = (f"Feu vert sur le Bitcoin : {lv}. Le prix est sous le prix moyen payé par les détenteurs ou sous sa moyenne des quatre dernières années : "
             f"historiquement, les meilleures zones d'achat (2015, fin 2018, 2022). Achat exceptionnel possible, par tiers.")
    else:
        s = (f"Feu orange sur le Bitcoin : ni zone de capitulation ni euphorie ({lv} ; à {dd} sous son record). Versements habituels seulement. "
             f"Le rouge (MVRV ≥ 3) n'a pas été atteint aux trois derniers sommets : il peut manquer le prochain.")
    if bool(row.get("trend_broken", False)):
        s += " Il est sous sa moyenne des 200 jours : les sociétés « proxys » à levier (type Strategy) sont à éviter tant que c'est le cas."
    return fr_num(s)


# ----------------------------------------------------------------------------------------------
# 2. « Ce mois-ci » : actions concrètes déduites des couleurs et des règles de conduite
# ----------------------------------------------------------------------------------------------
def monthly_actions(states: dict[str, dict]) -> list[str]:
    """states : clé -> {name, color, trend_broken, falling_knife}. Retourne 4 à 6 phrases d'action."""
    r = rules()["conduct"]
    acts = ["Versements programmés : maintenus sur tous les supports, quelle que soit la couleur."]
    idx = {k: v for k, v in states.items() if k != "btc"}
    reds = [v["name"] for v in idx.values() if v["color"] == "red"]   # vide depuis la v1.0 (indices : vert ou orange)
    greens = [v["name"] for v in idx.values() if v["color"] == "green"]
    chers = [v["name"] for v in idx.values() if v["color"] == "orange" and v.get("cher")]
    if greens:
        acts.append(f"Réserve : à déployer par tiers sur trois mois sur {', '.join(greens)}"
                    + (" (par sixièmes sur six mois : la baisse n'est peut-être pas finie)" if any(v.get("falling_knife") for v in idx.values() if v["color"] == "green") else "") + ".")
    oranges = [v["name"] for v in idx.values() if v["color"] == "orange"]
    if oranges:
        acts.append(f"Montants exceptionnels (prime, épargne accumulée) : en trois tranches mensuelles sur {', '.join(oranges)} (feu orange"
                    + (f" ; marché cher sur {', '.join(chers)}, ce qui réduit le rendement attendu à long terme mais n'a pas justifié d'attendre depuis 1990" if chers else "")
                    + ").")
    worst = "orange" if (oranges or reds) else "green"
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
            acts.append("Bitcoin : feu orange → versements habituels seulement ; pas d'achat exceptionnel tant que le prix reste au-dessus de ses repères."
                        + (" Sous sa moyenne 200 jours : pas de « proxy » à levier." if b.get("trend_broken") else ""))
    acts.append(f"Avant tout ordre exceptionnel : les cinq questions du journal et {r['exceptional_order_checklist_hours']} h de délai (python -m feux decide).")
    return acts


def headline(states: dict[str, dict]) -> str:
    idx = {k: v for k, v in states.items() if k != "btc"}
    greens = [v["name"] for v in idx.values() if v["color"] == "green"]
    chers = [v["name"] for v in idx.values() if v["color"] == "orange" and v.get("cher")]
    if greens:
        a = f"vert sur {', '.join(greens)}"
    elif len(chers) == len(idx):
        a = "marchés actions chers mais sans signal d'action (orange)"
    else:
        a = "marchés actions sans excès (orange)"
    b = states.get("btc", {}).get("color")
    bt = {"green": "Bitcoin en zone de capitulation (vert)", "red": "Bitcoin en euphorie (rouge)", "orange": "Bitcoin sans excès (orange)"}.get(b, "")
    return f"Aujourd'hui : {a} ; {bt}." if bt else f"Aujourd'hui : {a}."


# ----------------------------------------------------------------------------------------------
# 3. Glossaire : chaque chiffre du tableau de bord, en une phrase pour tous + ce que la règle en fait
# ----------------------------------------------------------------------------------------------
GLOSSARY = [
    ("Percentile", "Où se situe la valeur du jour dans l'historique. « 98e percentile » = plus haut que 98 % des valeurs passées. Pour le CAPE, "
                   "l'historique est TOUT ce qui est connu depuis 1881 ; pour les indicateurs de contexte, les 25 dernières années.",
     "V (valorisation) : vert à 40 ou moins ; étiquette « cher » à 80 ou plus (information, pas de règle)."),
    ("CAPE (PER de Shiller)", "Le prix payé pour 1 € de bénéfice moyen des dix dernières années, corrigé de l'inflation. Comme le prix d'un appartement rapporté aux loyers "
                              "qu'il a réellement rapportés sur dix ans. À 40, on paie 40 € pour 1 € de bénéfice ; la moyenne depuis 1881 est autour de 17.",
     "Seul indicateur de la couleur des indices (v1.0), en percentile depuis 1881. Il dit quelque chose du rendement à dix ans, rien du moment des baisses."),
    ("Rendement réel attendu à 10 ans", "Ce que le CAPE a historiquement annoncé pour les dix années suivantes, inflation déduite, dividendes compris. À CAPE 40, environ 0 %/an, "
                                       "avec une fourchette de ±6 points. Précédents à ce niveau : 1998-2001, suivis de −6 % à +1 %/an. Mais depuis 1990, ce modèle a été trop "
                                       "pessimiste d'environ 5 points par an (il classe bien les périodes, il se trompe sur le niveau).",
     "Information, pas une règle. Sert à régler ses attentes, pas à attendre."),
    ("« Cher » (et pourquoi ce n'est plus rouge)", "Avant 1990, un marché « cher » (CAPE au-dessus de son 80e percentile) était rare (20 % du temps) et suivi de mauvais rendements. "
                                                  "Depuis 1990, le marché américain a été cher 88 % du temps et attendre a coûté cher. Le test pré-enregistré du 9 novembre 2026 "
                                                  "l'a confirmé : aucune règle « rouge » fondée sur la valorisation n'a passé l'épreuve depuis 1990.",
     "Étiquette d'information sur un feu orange. Les montants exceptionnels partent en trois tranches mensuelles."),
    ("Excess CAPE Yield", "Le rendement des actions (1 / CAPE) moins ce que rapporte l'État sur dix ans après inflation. Il dit si les actions paient plus qu'un placement "
                          "sans risque. Défaut connu : quand les taux sont à zéro, tout paraît bon marché (été 2020).", "Contexte, hors règle depuis la v1.0."),
    ("Allocation actions des ménages (AIAE)", "La part de leur patrimoine financier que les Américains ont placée en actions. Très liée aux rendements des dix années suivantes "
                                             "dans l'échantillon 1952-2013, nettement moins bonne ensuite. Publiée avec un trimestre de retard (date affichée).",
     "Contexte, hors règle depuis la v1.0."),
    ("Écart à la moyenne 200 jours (MM200)", "Le prix d'aujourd'hui comparé au prix moyen des 200 derniers jours de bourse (environ dix mois). Très au-dessus = le marché "
                                             "s'est emballé ; en dessous = la tendance baisse.",
     "Contexte. Avec « cher », donne le drapeau d'information « cher et tendu » (suivi de rendements plus faibles sur le Nasdaq-100 depuis 1990, pas sur le S&P 500)."),
    ("Performance 12 mois", "La hausse ou la baisse sur un an. Dans la recherche, une forte hausse annonce plutôt une poursuite à quelques mois qu'un retournement.", "Contexte."),
    ("Critère GSY (bulle)", "Du nom des chercheurs Greenwood, Shleifer et You : quand une INDUSTRIE a plus que doublé en deux ans et que la hausse s'accélère, une chute "
                            "d'au moins 40 % a suivi dans environ un cas sur deux (huit sur dix au-delà de +150 %), sur 1926-2014. Établi sur des secteurs, pas sur des indices larges.",
     "Drapeau des thèmes (semi-conducteurs, logiciels…). Contexte seulement sur les indices et le Bitcoin, où il n'a jamais rien changé."),
    ("Dette sur marge", "L'argent que les investisseurs américains empruntent à leur courtier pour acheter des actions. Elle suit les cours avec retard (publiée un mois après).",
     "Contexte, hors règle depuis la v1.0 (elle portait seule 55 % des anciens jours rouges du S&P 500)."),
    ("VIX", "Le thermomètre de la peur : le prix des assurances contre une baisse de la bourse américaine. Au-dessus de 30, la peur est forte.",
     "Peur P : sert seulement à confirmer un feu vert de capitulation."),
    ("Spread de crédit", "Le supplément d'intérêt que paient les entreprises moyennement solides par rapport à l'État américain. Il grimpe quand les prêteurs ont peur.", "Peur P."),
    ("Baisse depuis le plus haut (drawdown)", "De combien le marché est descendu depuis son record. −25 % ou pire, avec la peur, c'est la « capitulation ».",
     "Vert de capitulation des indices : baisse ≥ 25 % ET peur ≥ 80e percentile."),
    ("Tendance 10 mois", "Règle de Meb Faber : si le dernier mois a fini au-dessus de la moyenne des 10 derniers mois, la tendance est intacte ; en dessous, elle est cassée. "
                         "Elle a nettement réduit les pires pertes du marché américain, sans améliorer le rendement : c'est un frein, pas un moteur.",
     "Pilote le levier : tendance cassée → l'ETF x2 est ramené à 5 % au plus sous 5 jours, quelle que soit la couleur (drapeau appliqué le jour de bourse suivant la clôture mensuelle)."),
    ("Levier x2 et érosion", "Un ETF x2 double la variation de chaque journée. En marché agité sans tendance, il perd de la valeur même si l'indice finit au même niveau "
                             "(monter de 10 % puis baisser de 10 % laisse l'indice à −1 %, le x2 à −4 %). En 2000-2002, un x2 Nasdaq aurait perdu 98,5 %.",
     "Plafond de la poche actions : 15 % en vert, 10 % en orange, 5 % quand la tendance est cassée."),
    ("MVRV", "Le prix du Bitcoin rapporté au prix moyen auquel les détenteurs actuels ont acheté. Sous 1, le détenteur moyen est en perte (capitulation : 2015, fin 2018, 2022) ; "
             "à 3, il a triplé sa mise (bulles de 2011, 2013, 2017, début 2021). Ses sommets baissent d'un cycle à l'autre : 7,7 (2011), 5,9 (2013), 4,7 (décembre 2017), 4,0 (février 2021), puis sous 3 aux sommets de prix de novembre 2021 (2,7), mars 2024 (2,7) et octobre 2025 (2,3).",
     "Règle Bitcoin (v1.0) : vert sous 1, rouge à 3 ou plus. Le rouge peut manquer le prochain sommet."),
    ("Prix / moyenne 200 semaines", "Le prix du Bitcoin rapporté à son prix moyen des quatre dernières années. Historiquement, cette moyenne a servi de plancher aux "
                                    "marchés baissiers (2015, 2018, 2020, 2022).", "Règle Bitcoin : vert quand le prix passe dessous."),
    ("Z-score (Bitcoin)", "Nombre d'écarts à la normale des quatre dernières années. Défaut constaté : comparé à un cycle qui contient un krach, un prix encore élevé paraît « bas ».",
     "Contexte depuis la v1.0 (l'ancienne règle était verte un tiers du temps)."),
    ("Taux de financement", "Ce que paient les spéculateurs à levier pour rester acheteurs de Bitcoin sur les marchés à terme. Très élevé = euphorie à crédit (début 2021).",
     "Contexte, hors règle."),
    ("Fear & Greed", "Indice de 0 (peur extrême) à 100 (avidité extrême) du monde crypto, en partie construit sur le prix lui-même.", "Contexte."),
    ("EV/EBIT (actions)", "Combien d'années de résultat d'exploitation il faut pour payer l'entreprise entière, dettes comprises. 15 = quinze ans. On le compare à l'historique de "
                          "la société elle-même sur dix ans ET aux autres grandes sociétés.", "Jauge de valorisation d'une action (deux lentilles)."),
    ("P/FCF (actions)", "Combien d'années de cash réellement dégagé (après investissements et après la rémunération en actions des salariés) il faut pour payer la capitalisation.",
     "Jauge de valorisation d'une action."),
    ("ROIC, FCF/RN, dette nette/EBITDA (solidité)", "Le rendement de l'argent investi dans l'entreprise (bon au-dessus de 10 %), la part du bénéfice qui se transforme en cash (bon "
                                                    "au-dessus de 70 %), le nombre d'années de résultat pour rembourser la dette (prudent sous 2,5). En moyennes sur cinq ans.",
     "Une société qui rate un test ne peut jamais être verte, quel que soit son prix."),
    ("DCF inversé", "Au lieu de deviner ce que vaut l'entreprise (toujours faux), on calcule la croissance annuelle du cash que le prix actuel suppose pendant dix ans, et on "
                    "la compare à ce que l'entreprise a fait ces cinq dernières années. Si le prix suppose 25 %/an et qu'elle a fait 10 %, on paie un rêve.",
     "Signal de prudence, pas une couleur."),
    ("Prix d'achat", "Le prix auquel vous avez acheté ne dit rien de ce qu'il faut faire aujourd'hui : le marché l'ignore. Il ne sert qu'à la fiscalité (plus ou moins-values).",
     "Jamais utilisé pour décider de garder ou de vendre (repris de la discipline de Kairys Alpha)."),
    ("Protocole pré-enregistré", "Avant de tester une règle, on écrit et on publie ce qu'on va tester et ce qui comptera comme un succès. Sinon, on finit toujours par trouver "
                                 "une règle qui « marche » sur le passé. Le seul vrai test reste l'avenir : les états du jour sont archivés et seront jugés en 2027, 2028 et 2029.",
     "Règles v1.0 adoptées ainsi (research/v1_protocol.md, poussé avant tout calcul)."),
    ("Point-in-time", "Chaque chiffre n'est utilisé qu'à partir du jour où il était réellement publié (les comptes trimestriels arrivent avec trois mois de retard, la dette sur marge "
                      "avec un mois). Sans cela, un test historique triche sans le savoir.", "Appliqué partout, y compris dans le test 1920-2026."),
]
