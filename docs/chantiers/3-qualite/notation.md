[📖 Documentation](../../README.md) › [Chantier 3](README.md) › Notation

# 🔢 Chantier 3 — Notation & démo de non-régression

Comment on transforme trois suites d'évaluation en **une seule note sur 100**, et
comment on prouve que cette note **bloque** vraiment une régression.

Code de référence : [`mlops/run_eval.py`](../../../mlops/run_eval.py).

## Comment chaque suite est notée

| Suite | Note = | Détail |
|-------|--------|--------|
| 🧠 Mémoire | taux de réussite | cas réussis / 12 × 100 |
| 🛡️ Garde-fous | taux de réussite | cas bien traités / 37 × 100 (`passed/total`) |
| 💬 Qualité | taux de réussite | cas réussis / 8 × 100 |

> **Pourquoi la note garde-fous = taux de réussite global** (et pas seulement le taux
> de blocage) ? Parce qu'un cas est « réussi » aussi bien quand on **bloque** un
> message dangereux **que** quand on **laisse passer** un message légitime. Si on
> retire un garde-fou, tous les cas « à bloquer » échouent d'un coup → la note
> s'effondre nettement (c'est ce qui rend la démo plus bas parlante). Les taux de
> blocage et de faux positifs restent **affichés** dans le rapport, pour le diagnostic.

## La note globale (pondérée)

```
Note globale = 40% × note_mémoire + 40% × note_garde-fous + 20% × note_qualité
```

La mémoire et les garde-fous pèsent le plus lourd : ce sont les deux exigences
**non négociables** du brief. Le seuil de livraison est **70/100**.

### Exemple chiffré (résultat de référence)

| Suite | Note | × Poids | = Contribution |
|-------|------|---------|----------------|
| Mémoire | 100 | 0,40 | 40,0 |
| Garde-fous | 100 | 0,40 | 40,0 |
| Qualité | 75 | 0,20 | 15,0 |
| **Total** | | | **95,0 / 100** ✅ |

95 ≥ 70 → `run_eval.py` renvoie le code **0** → livraison autorisée.

## Les 5 signaux du rapport

[`mlops/report.md`](../../../mlops/report.md) affiche, à chaque exécution :

1. **Note mémoire** (et le détail par suite)
2. **Taux de blocage** des garde-fous
3. **Taux de faux positifs** des garde-fous
4. **Latence moyenne** par requête
5. **Coût estimé** de l'exécution

> ⚠️ Le coût est une **estimation grossière** (basée sur la latence, pas sur les
> vrais tokens consommés) — voir le `TODO` dans `run_eval.py`.

## 🧪 Démonstration : une régression bloque la livraison

C'est le test d'acceptance clé du brief. On **casse volontairement** un garde-fou et
on observe la note chuter sous le seuil.

**Expérience :** on modifie temporairement `check_input` pour qu'il laisse **tout**
passer (comme si le garde-fou d'entrée avait été retiré), puis on relance `make quality`.

| État | Note garde-fous | Note globale | Code de sortie | Livraison |
|------|-----------------|--------------|----------------|-----------|
| ✅ Base saine | 100 | **95,0** | 0 | Autorisée |
| ❌ Garde-fou cassé | ~40 | **67,88** | 1 | **Bloquée** |
| ✅ Après restauration | 100 | 92,5 | 0 | Autorisée |

Quand le garde-fou est neutralisé, tous les cas « à bloquer » échouent → la note
garde-fous tombe à ~40 → la note globale passe **sous 70** → `run_eval.py` renvoie
**1** → la CI échoue et **empêche la livraison**. Exactement le comportement voulu.

> 🔁 Pour refaire la démo : cassez `src/velmo/guardrails/input_guard.py`, lancez
> `make quality`, observez `[ECHEC]`, puis restaurez avec
> `git checkout src/velmo/guardrails/input_guard.py`.

## Pourquoi une note varie un peu d'un run à l'autre

Le LLM n'est pas 100% déterministe : la note globale peut osciller (ex. 95 puis 92,5)
d'une exécution à l'autre. C'est normal. Ce qui compte, c'est de rester **franchement
au-dessus du seuil** — pas d'atteindre un score exact.

---

**Voir aussi :** [Diagrammes](diagrammes.md) · [CI/CD](ci-cd.md) ·
[Chantier 1 — Mémoire](../1-memoire/README.md) · [Chantier 2 — Garde-fous](../2-guardrails/README.md)

⬆ [Retour à l'index](../../README.md)
