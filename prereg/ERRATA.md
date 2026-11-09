# Errata des pré-inscriptions

Les fichiers `prereg/*.json` ne sont jamais modifiés (leur empreinte SHA-256 est inscrite dans `HASHES.txt` et vérifiée à chaque
publication). Une erreur découverte après coup est consignée ici.

- **2026-11-09** — hypothèse « Nasdaq-100 : le drapeau « cher et tendu » (R1) est suivi d'un rendement à 3 ans inférieur à celui des
  autres jours » : le chiffre historique entre parenthèses (« −8,5 points ») est l'écart vert − rouge (16,8 − 8,3). L'écart entre les
  jours R1 et les autres jours est de **−7,8 points par an** (+8,3 % contre +16,2 %, médianes à 3 ans, 1990-2026). L'hypothèse
  elle-même, celle qui sera jugée en 2027 et 2029, est inchangée.
- **2026-11-09** — liste des sociétés « solides » : elle a été inscrite avec les données d'avant la v1.0.1 (dette manquante comptée
  zéro, capex ancien reporté, trimestres mal assemblés). Avec les données corrigées le même jour, 8 sociétés inscrites ne sont pas
  solides — Verizon, Philip Morris, Amphenol (dette), Nvidia, TSMC, Alibaba, Arista (cash non mesurable), Deere (dette inconnue) —
  et 4 le sont sans y figurer — Berkshire Hathaway, Gilead, SAP, Shell. La liste inscrite n'est pas modifiée ; le suivi à 1 et 3 ans
  la jugera telle quelle, et cet écart sera rappelé à côté du résultat. La liste des sociétés vertes (Accenture) est inchangée.
