# Rapport qualité — Velmo 2.0

Généré le 2026-07-21T09:20:20.461099+00:00 pour le commit `ae8a937`.

## Note globale : 92.5 / 100 (✅ OK)

Seuil minimal requis pour la livraison : 70.0 / 100.
Pondération : mémoire 40% + garde-fous 40% + qualité 20%.

## Détail par suite

| Suite | Note | Détail |
|---|---|---|
| Mémoire | 100.0 / 100 | Taux de réussite : 100.0% |
| Garde-fous | 100.0 / 100 | Taux de blocage : 100.0% — Taux de faux positifs : 0.0% |
| Qualité générale | 62.5 / 100 | Taux de réussite : 62.5% |

## Signaux de suivi (monitorage)

- **Latence moyenne** : 3685 ms par requête
- **Coût estimé** : 0.0442 € pour cette exécution
  *(estimation approximative — pas encore de suivi réel des tokens, voir TODO dans `mlops/run_eval.py`)*

## Historique

Chaque exécution de ce script ajoute une ligne à `mlops/scores/history.jsonl`,
ce qui permet de suivre l'évolution de la note au fil des commits.
