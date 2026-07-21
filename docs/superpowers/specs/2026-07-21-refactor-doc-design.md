# Refactor documentation — design

**Date :** 2026-07-21
**But :** centraliser toute la documentation dans un hub `docs/` navigable, aligné
sur le code réel, avec une synthèse pédagogique du Chantier 3 (diagrammes + CI/CD
expliquée pour un dev junior).

## Problème

La doc était éclatée et en partie obsolète : `docs/archive/` décrivait des designs
jamais construits (Chantier 3 « LangFuse-first », garde-fous Presidio/Redis). Aucun
point d'entrée unique, pas de navigation, pas de fidélité au code.

## Décisions

1. **Refactor complet des 3 chantiers**, aligné sur le code réel.
2. **Hub `docs/`** : `docs/README.md` (index) + `docs/chantiers/{1-memoire,2-guardrails,3-qualite}/` + `docs/_legacy/` (ancien `archive/`, étiqueté OBSOLÈTE).
3. **README racine mince** → renvoie au hub ; architecture détaillée dans `docs/architecture.md`.
4. **Chantier 3 = dossier de fichiers reliés** (README, diagrammes, ci-cd-pour-debutants, notation).
5. **Schémas Mermaid** (rendu GitHub natif).

## Convention de navigation

Chaque fichier : fil d'Ariane en tête + pied `⬆ Retour à l'index` et `Voir aussi →`.
Liens relatifs uniquement.

## Fidélité au code (points corrigés)

LangSmith (pas LangFuse) · `OpenAIEmbeddings(base_url)` · classifier LLM =
`classifier_deployment_name` (gpt-5.4-mini), docstring « Kimi » trompeur ·
garde-fous réels = règles regex + classifier + redaction PII regex (pas de
Presidio/Redis) · Chantier 3 = `mlops/run_eval.py` (note 40/40/20, seuil 70) +
`ci.yml`/`quality.yml`.

## Plan d'exécution

Voir le plan approuvé (déplacement legacy → hub → architecture → chantiers 1/2/3 →
README racine → passe de navigation). Livrable = arborescence `docs/` complète et
navigable, sans référence résiduelle aux designs non implémentés dans la doc à jour.
