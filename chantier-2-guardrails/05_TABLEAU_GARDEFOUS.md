# Chantier 2 — Tableau des Garde-fous

Livrable de conception exigé par le brief : **catégorie × emplacement (entrée/sortie) × méthode × action en cas de blocage**, pour les 7 catégories interdites.

## Légende

- **Emplacement** : 🟦 Entrée (filtre la requête user) · 🟩 Sortie (filtre la réponse LLM) · 🟦🟩 Les deux
- **Action** : ❌ Bloquer + refus poli · 🔧 Rédiger/masquer · 📋 Journaliser · 🚨 Escalade humaine

---

## Tableau principal

| # | Catégorie interdite | Emplacement | Méthode | Action en cas de détection |
|---|---------------------|:-----------:|---------|----------------------------|
| 1 | **Haine, discrimination, harcèlement** | 🟦🟩 | Classifieur de modération (LLM) | ❌ Bloquer + refus poli + 📋 journaliser |
| 2 | **Violence, menaces, incitation au mal** | 🟦🟩 | Classifieur de modération (LLM) | ❌ Bloquer + refus poli + 📋 + 🚨 si auto-agression |
| 3 | **Sexuel / NSFW** | 🟦🟩 | Classifieur de modération (LLM) | ❌ Bloquer + refus poli + 📋 |
| 4 | **PII sensibles en sortie** (n° carte, mots de passe, données d'autres clients) | 🟩 | Regex + Presidio (motifs PII) | 🔧 Masquer `[REDACTED_*]` avant envoi + 📋 |
| 5 | **Hors périmètre** (conseil juridique/médical, engagement Velmo) | 🟩 | Vérification de périmètre (LLM + mots-clés) | ❌ Bloquer + réponse de recentrage + 📋 |
| 6 | **Injection de prompt / contournement** (« ignore tes instructions ») | 🟦 | Détection de motifs + instructions système durcies | ❌ Neutraliser (ne pas obéir) + 📋 + 🚨 si répété |
| 7 | **Fuite de secrets / config interne** (API keys, tokens) | 🟩 | Regex (motifs de secrets) | 🔧 Masquer + 📋 + 🚨 si récurrent |

---

## Pourquoi entrée, sortie, ou les deux ?

| Catégorie | Entrée seule | Sortie seule | Les deux | Raison |
|-----------|:---:|:---:|:---:|--------|
| Haine / Violence / NSFW (1,2,3) | | | ✅ | User peut l'écrire **et** le LLM peut le générer |
| PII en sortie (4) | | ✅ | | On ne peut redacter que ce que le LLM **produit** |
| Hors périmètre (5) | | ✅ | | C'est la **réponse** qui dérape, pas la question |
| Injection de prompt (6) | ✅ | | | L'attaque est dans la **requête** user |
| Fuite de secrets (7) | | ✅ | | Le secret fuit dans la **réponse** générée |

---

## Méthodes : avantages & angles morts

| Méthode | Avantage | Angle mort | Mitigation |
|---------|----------|------------|------------|
| **Regex / motifs** (PII, secrets) | Rapide, déterministe, gratuit | Rate les variantes non prévues | Compléter par Presidio (ML) |
| **Presidio** (ML PII) | Détecte entités contextuelles | Faux positifs sur cas ambigus | Seuil de confiance ajustable |
| **Classifieur LLM** (modération) | Comprend le contexte, nuance | Latence + coût + faux positifs | Cache + seuil + chain-of-thought |
| **Vérification périmètre** | Bloque le hors-scope | Frontière floue (support vs conseil) | Règles + exemples explicites |
| **Instructions durcies** (anti-injection) | Résiste au détournement | Jamais 100 % étanche | Défense en profondeur (entrée + système) |

---

## Gestion des faux positifs (équilibre sécurité / utilité)

- **Seuil de confiance** par catégorie : on ne bloque qu'au-dessus d'un score (ex. 0.75), sinon on laisse passer ou on vérifie.
- **Chain-of-thought** si score ambigu (0.5–0.75) : 2ᵉ passe de vérification avant de bloquer.
- **Objectif chiffré** : taux de faux positifs **< 3 %** (config prod), mesuré par la suite d'éval garde-fous (chantier 3).
- **Principe** : en cas de doute sur du contenu *dangereux* → bloquer (fail-safe). Sur du contenu *légitime limite* → laisser passer + journaliser.

---

## Que fait l'agent quand il bloque ?

1. **Message poli** à l'utilisateur (pas de détail technique) :
   > « Je ne peux pas traiter cette demande. Je suis là pour le support Velmo — reformulez et je vous aide. »
2. **Journalisation** (`audit_log`) : catégorie, emplacement, score, timestamp, user_id, action.
3. **Escalade humaine** (🚨) pour les cas graves : auto-agression, injection répétée, fuite récurrente.

---

## Résistance aux injections de prompt

Défense en profondeur — aucune couche n'est suffisante seule :

1. **Garde-fou d'entrée** : détecte les motifs (« ignore tes instructions », « tu es maintenant… »).
2. **Instructions système durcies** : le prompt système rappelle explicitement que les consignes ne peuvent être annulées par l'utilisateur.
3. **Séparation des rôles** : le contenu user n'est jamais interprété comme instruction système.
4. **Garde-fou de sortie** : même si l'injection passe, la sortie est re-filtrée (PII, périmètre, secrets).

---

## Traçabilité (lien chantier 3)

Chaque décision de blocage alimente les **signaux de suivi** : taux de blocage et taux de faux positifs sont mesurés par la suite d'éval garde-fous (`guardrail_cases.jsonl`) et reportés dans `mlops/report.md`.
