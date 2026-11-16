# Fiche de Cadrage d'Ingénierie — Projet Fédérateur AI-BD_BI

## Spécification du Moteur RAG / Data Intelligent

---

### 1. Fiche d'Identité du Projet

- **Nom du Projet :** `Vehicle Diagnostics & Maintenance Assistant (Advanced RAG)`
- **Membres de l'Équipe :**
  1. Mohamed ben maaouia
  2. Youssef fazzeni
  3. Mohamed yassine skik
- **Lien du Dépôt GitHub :** `https://github.com/MohamedBenMaaouia/Proj-federateur-BD-IA-`
- **Branche de travail principale :** `main` (protégée)

---

### 2. Cadrage du Problème Métier ("Problem-First")

#### 2.1 Persona Cible & Contexte Opérationnel

- **Utilisateur visé :** propriétaires de véhicules, mécaniciens amateurs, techniciens et conseillers d'atelier, francophones et anglophones.
- **Point de douleur majeur (*Pain point*) :** devoir parcourir un manuel du propriétaire de 600 à 700 pages, rempli de tableaux, de renvois et d'avertissements, pour trouver un intervalle d'entretien, une capacité de fluide ou une procédure. Et face à un voyant moteur, ne pas savoir ce que signifie un code de diagnostic comme **P0420** ou **P0171**, dont la définition se trouve dans une nomenclature à part (SAE J2012).
- **Limite des approches classiques (Pourquoi l'IA générative ?) :**
  - Une recherche Ctrl+F ou plein texte échoue face aux synonymes (« vidange » vs « changer l'huile moteur »), aux questions formulées en langage courant et aux questions posées dans une autre langue que celle du manuel.
  - Un chatbot généraliste répond de mémoire : il invente des intervalles d'entretien, des capacités ou des significations de codes, sans source vérifiable. Pour un véhicule, une valeur inventée peut causer une panne ou un risque de sécurité.
  - Les modèles d'embeddings seuls confondent des identifiants proches (P0420 ≈ P0455), d'où le besoin d'une recherche hybride avec correspondance exacte.

#### 2.2 Proposition de Valeur

Fournir un assistant web bilingue (FR / EN) en streaming, qui répond en langage naturel à partir de la documentation officielle du véhicule et de la nomenclature OBD-II, **cite systématiquement le fichier et la page de chaque information**, retrouve un code de diagnostic exact en première position, **refuse explicitement de répondre** lorsque la documentation ne couvre pas la question, et vise un score de fidélité (Faithfulness) ≥ 0,85. L'ensemble tourne localement : aucune donnée ne quitte la machine.

---

### 3. Données & Volumétrie

- **Format des données sources :** `[x] PDF multi-colonnes` `[x] JSON/CSV` `[ ] Tables relationnelles SQL` `[ ] Markdown` `[ ] Images/Scans`
  - 2 manuels du propriétaire Ford F-150 2017 (PDF, anglais 599 pages et français 683 pages).
  - 469 codes de diagnostic OBD-II génériques SAE J2012 (JSON).
  - Corpus validé par `scripts/validate_corpus.py` (texte extractible, langue, format des codes, absence de doublons, SHA-256 dans `data/raw/manifest.json`).
- **Volumétrie initiale (PoC S1-S3) :** `3 fichiers / 1 282 pages + 469 codes / ≈ 4 500 chunks`
- **Volumétrie cible en production :** `≈ 100 manuels (≈ 50 modèles × 2 langues) + nomenclature OBD-II complète / ≈ 250 000 chunks` *(estimation)*
- **Fréquence de mise à jour des données :** `[x] Batch quotidien` `[ ] Temps réel / Streaming` `[ ] Statique`
  - En pratique, ré-ingestion par lot à chaque nouvelle édition de manuel ou nouveau modèle. Le corpus évolue rarement, mais la ré-ingestion est entièrement automatisée et idempotente.

---

### 4. Architecture Technique & Composants RAG

- **Stratégie de Chunking :** `[ ] Recursive Character` `[x] Semantic Chunking` `[ ] Parent-Document / Hierarchical`
  - Manuels : chunking sémantique, avec découpage récursif en repli pour les sections trop longues.
  - Codes OBD-II : 1 code = 1 chunk, jamais découpé.
  - *Taille de chunk visée :* `≈ 200 tokens (plafond 800 caractères)` | *Overlap :* `≈ 40 tokens (150 caractères) en repli récursif`
- **Modèle d'Embeddings :** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (Dimension : `384`), multilingue, exécuté sur CPU, vecteurs normalisés.
  - Recherche creuse : BM25 (FastEmbed `Qdrant/bm25`), un vecteur par langue (règles EN et FR).
- **Base Vectorielle retenue :** `[x] Qdrant` `[ ] Milvus` `[ ] pgvector`
  - *Justification du choix :* recherche hybride **native** (vecteurs denses et creux sur le même point, fusion RRF en une seule requête), indispensable pour la correspondance exacte des codes de diagnostic ; filtrage par métadonnées (langue, type de document) appliqué pendant la recherche HNSW, avec index de payload ; un seul conteneur en local, même API jusqu'au cluster. Milvus nécessite 3 services (Milvus + etcd + MinIO) ; pgvector n'a pas de BM25 natif. Spécification complète : `docs/vector-database-choice.md`.
- **Reranker (Cross-Encoder) :** `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (multilingue), Top-30 → Top-6 avec coupure de pertinence relative.
- **LLM de Génération :** `Mistral-7B-Instruct via Ollama (local)`, température 0,1.
  - LLM juge pour l'évaluation Ragas : `Qwen2.5-14B via Ollama` (distinct du LLM évalué).
- **API & Interface :** FastAPI asynchrone + Pydantic v2, streaming SSE ; interface web React.
- **Cache & Observabilité :** Redis (cache exact + sémantique) ; Langfuse (traces et scores Ragas).

---

### 5. Métriques Quantitatives & SLAs

| Métrique | Définition / Outil | Objectif Cible (KPI) |
| :---- | :---- | :---: |
| **Recall@6 (Retrieval)** | Présence du passage de vérité (texte d'ancrage vérifié dans le corpus) dans le top-6, après reranking | $\ge 80\%$ |
| **MRR (Retrieval)** | Rang moyen du premier passage de vérité (1 / rang) | $\ge 0.60$ |
| **Recherche de code exacte** | Question sur un code OBD-II → ligne exacte de ce code en 1ʳᵉ position | $100\%$ |
| **Faithfulness (Ragas)** | Part des affirmations de la réponse appuyées par les chunks récupérés | $\geq 0.85$ / 1.00 |
| **Answer Relevance (Ragas)** | Adéquation directe de la réponse à la question posée | $\geq 0.80$ / 1.00 |
| **Refus hors périmètre** | Questions hors corpus recevant la phrase de refus | $100\%$ |
| **Latence First-Token (TTFT)** | Temps d'affichage du premier token en streaming (LLM servi sur GPU) | $<800$ ms |
| **Latence E2E P95** | Temps total de complétion de la requête (LLM servi sur GPU) | $<3.5$ s |
| **Latence cache** | Réponse servie depuis le cache Redis | $<50$ ms |

---

### 6. Gestion des Risques & Garde-fous

- **Prévention des Hallucinations :** injection systématique de la directive : *« Si l'information n'est pas présente dans les extraits ci-dessus, répondez explicitement que le corpus ne permet pas de conclure. »* Elle est complétée par :
  - une citation `(fichier, p.N)` obligatoire après chaque affirmation ;
  - l'interdiction d'inventer codes, couples de serrage ou capacités ;
  - une température de 0,1 ;
  - une mesure continue de la Faithfulness avec Ragas.
- **Confusion d'identifiants :** recherche hybride (BM25) et reranking pour retrouver le code exact. Le cache sémantique n'est jamais servi si les identifiants de la question diffèrent (P0420 ≠ P0455).
- **Injection de prompt :** règles dans le message système, question et chunks encadrés comme données non fiables, filtrage des formulations d'attaque connues (FR / EN), chunks suspects écartés, contrôle des fuites du prompt système. Le tout est évalué sur un jeu d'attaques dédié.
- **Protection des Secrets :** utilisation exclusive de variables d'environnement via `.env` (non versionné, `.env.example` fourni) ; aucun token dans le code source.
- **Isolation Réseau :** Qdrant et Redis confinés dans un réseau Docker interne privé ; seuls l'API et l'interface sont exposées. En développement, les ports sont liés à `127.0.0.1` uniquement.
- **Confidentialité :** tous les modèles (embeddings, reranker, LLM, juge d'évaluation) tournent localement ; aucune donnée n'est envoyée à une API externe.
- **Latence matérielle :** sur un poste de développement sans GPU dédié, la génération par un LLM 7B dépasse les objectifs de TTFT et de latence E2E. Ces objectifs supposent un LLM servi sur GPU ; la latence est mesurée et tracée dans Langfuse dans tous les cas, et le cache Redis sert instantanément les questions fréquentes.
- **Qualité des données :** corpus validé automatiquement avant ingestion (texte extractible, langue, format et unicité des codes, sommes de contrôle). Les deux erreurs de saisie détectées dans la liste de codes source ont été corrigées et tracées.
- **Droits sur les données :** manuels © Ford Motor Company, utilisés dans un cadre académique et non commercial ; nomenclature OBD-II SAE J2012 issue du projet open source dtcdb.
