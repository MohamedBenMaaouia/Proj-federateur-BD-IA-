# Backlog Technique MoSCoW — Vehicle Diagnostics & Maintenance Assistant (Advanced RAG)

## Découpage Agile des User Stories & Critères d'Acceptation

Assistant RAG bilingue (anglais / français) répondant aux questions des propriétaires de véhicules et des mécaniciens à partir des manuels du propriétaire (PDF EN + FR) et des codes de diagnostic OBD-II (SAE J2012), avec citation systématique des sources et refus de répondre hors corpus.

---

## 1. MUST HAVE (Indispensables pour la Livraison Finale S7)

*Fonctionnalités non négociables : sans elles, l'assistant n'est ni fiable ni utilisable.*

| ID | User Story Technique | Critères d'Acceptation (DoD) | Séance Cible |
| :---: | :---- | :---- | :---: |
| **US-01** | **Ingestion & Chunking Sémantique**<br>En tant que Data Engineer, je veux découper les manuels et la liste de codes en chunks porteurs de métadonnées pour permettre un indexage et une citation précis. | - Script Python asynchrone avec gestion des erreurs (fichier illisible, page vide, JSON invalide) et journalisation.<br>- Corpus validé en amont par `scripts/validate_corpus.py` (manifest + SHA-256).<br>- Métadonnées stockées : `doc_id`, `source`, `page_number`, `chunk_id`, `doc_type` (`manual` / `obd_code`), `language` (`en` / `fr`).<br>- Manuels : **chunking sémantique** (découpage aux ruptures de sens), taille plafonnée.<br>- Codes OBD-II : **1 code = 1 chunk**, jamais découpé (le code reste lié à sa signification).<br>- Tableaux textuels (intervalles d'entretien, capacités) extraits en texte et vérifiés sur un échantillon de pages-tableaux. | **S2** |
| **US-02** | **Indexation Vectorielle Hybride (Qdrant, HNSW)**<br>En tant que système RAG, je veux indexer pour chaque chunk un vecteur dense et un vecteur creux BM25 afin de combiner recherche sémantique et correspondance exacte. | - Qdrant démarré via `docker compose up -d` (image épinglée, ports liés à `127.0.0.1`, volume persistant).<br>- Vecteur dense : index HNSW, distance Cosine, embeddings normalisés.<br>- Vecteurs creux BM25 avec modificateur **IDF**, un par langue (règles EN et FR).<br>- Index de payload sur `language` et `doc_type`.<br>- Upsert d'un batch de 64 chunks (vecteurs pré-calculés) < 50 ms, mesuré.<br>- Une ré-ingestion complète laisse exactement le nombre de chunks attendu (aucun doublon). | **S2** |
| **US-03** | **Retrieval Hybride & Reranking**<br>En tant que moteur de recherche, je veux fusionner les résultats denses et BM25 puis reranker les candidats pour fournir au LLM les passages les plus pertinents. | - Top-30 candidats en recherche hybride (dense + BM25, fusion RRF dans Qdrant).<br>- Cross-Encoder multilingue réduisant la liste au **Top-6**, avec coupure de pertinence relative (les chunks très inférieurs au meilleur sont écartés).<br>- Une question sur un code (ex. « P0420 ») retrouve la ligne exacte de ce code en 1ʳᵉ position.<br>- **Recall@6 au niveau passage ≥ 80 %**, MRR ≥ 0,60, mesurés sur le jeu d'évaluation. | **S3** |
| **US-04** | **API REST FastAPI & Schémas Pydantic v2**<br>En tant qu'application cliente, je veux interroger l'assistant via des endpoints asynchrones, typés et validés. | - Endpoints `async def` ; schémas Pydantic v2 stricts `QueryRequest` (question 3–1000 caractères, langue `auto` / `en` / `fr`) et `QueryResponse` (réponse, sources, latence).<br>- Rejet immédiat en **HTTP 422** si question vide, trop longue ou langue inconnue.<br>- Endpoints `/api/v1/health` (état Qdrant / Redis / LLM) et `/api/v1/ingest`.<br>- Documentation OpenAPI / Swagger interactive générée. | **S4** |
| **US-05** | **Génération de Réponse en Streaming SSE**<br>En tant qu'utilisateur, je veux recevoir la réponse mot par mot avec les sources citées pour réduire la latence perçue. | - Endpoint `/api/v1/chat/stream` émettant des Server-Sent Events.<br>- Événements typés : `sources` (texte du chunk, fichier, page, score du reranker), `token`, `done`, `error`.<br>- Time-to-First-Token mesuré et journalisé à chaque requête ; objectif **< 800 ms** avec LLM servi sur GPU. | **S4 / S5** |
| **US-06** | **Interface Web Réactive (React)**<br>En tant qu'utilisateur final, je veux poser ma question et voir la réponse s'afficher en streaming avec les sources citées. | - Composant chat avec gestion des états (idle, loading, streaming, error).<br>- Panneau latéral affichant le texte exact de chaque chunk cité, avec fichier et numéro de page.<br>- Sélecteur de langue (auto / EN / FR).<br>- Zéro rechargement de page ; interface responsive. | **S5** |
| **US-07** | **Réponses Ancrées, Citées et Bilingues**<br>En tant qu'utilisateur, je veux des réponses fondées uniquement sur la documentation, citées et dans ma langue, afin de pouvoir m'y fier. | - Chaque affirmation est suivie d'une citation `(fichier, p.N)`.<br>- Si le corpus ne contient pas la réponse : phrase de refus fixe, sans appel au LLM lorsque rien n'est retrouvé.<br>- Aucun code, valeur de couple ou capacité inventé.<br>- Réponse dans la langue de la question (FR ou EN), y compris quand la source est dans l'autre langue.<br>- Température du LLM ≤ 0,1.<br>- 100 % de refus corrects sur les questions hors périmètre du jeu d'évaluation. | **S3 / S4** |
| **US-08** | **Assurance Qualité & CI/CD Automatisée**<br>En tant que Lead Developer, je veux que chaque commit déclenche les tests et le linter. | - Workflow GitHub Actions : `ruff check` + `pytest` à chaque push / pull request.<br>- Au minimum 4 tests Pytest obligatoires avec LLM mocké et base vectorielle de test (sans coût) : chunking, retrieval hybride, API (422 + schéma de réponse), streaming SSE.<br>- Test anti-dérive : le retriever exécute exactement la stratégie configurée.<br>- Branche `main` protégée : merge bloqué si le workflow n'est pas vert. | **S6** |
| **US-09** | **Conteneurisation de Production Multi-Stage**<br>En tant qu'ingénieur DevOps, je veux déployer l'ensemble du système via un Docker Compose de production sécurisé. | - Dockerfile multi-stage (build / runtime) avec utilisateur non-root.<br>- Secrets et configuration injectés uniquement par variables d'environnement (`.env` non versionné, `.env.example` fourni).<br>- Qdrant et Redis sur un réseau Docker interne privé ; seule l'API (et l'UI) exposées.<br>- Healthchecks sur tous les services. | **S7** |

---

## 2. SHOULD HAVE (Forte Valeur Ajoutée Industrielle)

*Fonctionnalités renforçant la robustesse, la sécurité et la maturité MLOps.*

| ID | User Story Technique | Critères d'Acceptation | Séance Cible |
| :---: | :---- | :---- | :---: |
| **US-10** | **Tracing MLOps (Langfuse)**<br>En tant que responsable IA, je veux tracer chaque étape de la chaîne RAG pour identifier les goulets d'étranglement. | - Latence découpée par étape : embedding, recherche vectorielle, reranking, LLM.<br>- Tokens consommés enregistrés par requête.<br>- Trace consultable par requête dans Langfuse. | **S3 / S4** |
| **US-11** | **Évaluation Continue (Ragas)**<br>En tant que Data Scientist, je veux évaluer automatiquement la qualité des réponses sur un benchmark de référence. | - Benchmark bilingue versionné (codes, entretien, symptômes, procédures, questions hors périmètre) avec passage attendu par question.<br>- Métriques : Recall@k et MRR au niveau passage, Faithfulness et Answer Relevance (Ragas, LLM juge distinct du LLM évalué).<br>- Résultats horodatés et loggués dans Langfuse ; exécution périodique.<br>- Objectifs : Faithfulness ≥ 0,85, Answer Relevance ≥ 0,80. | **S3** |
| **US-12** | **Cache Sémantique Redis**<br>En tant qu'architecte système, je veux servir instantanément les questions déjà posées ou reformulées. | - Deux niveaux : cache exact (question normalisée) et cache sémantique (similarité cosinus ≥ seuil calibré sur le corpus).<br>- Garde-fous : pas de hit si les identifiants diffèrent (P0420 ≠ P0455) ou si la langue diffère.<br>- Réponse servie depuis le cache en < 50 ms.<br>- Invalidation à chaque ré-ingestion ou changement de configuration ; durée de vie (TTL) configurable.<br>- Redis indisponible ⇒ l'API continue de fonctionner sans cache. | **S4** |
| **US-13** | **Protection contre l'Injection de Prompt**<br>En tant que responsable sécurité, je veux empêcher qu'une question ou un document détourne l'assistant. | - Règles dans le message système ; question et chunks encadrés comme données non fiables.<br>- Filtrage des formulations d'attaque connues (EN / FR) avant tout appel au LLM.<br>- Chunks contenant une injection écartés avant le prompt.<br>- Réponse divulguant le prompt système remplacée par un refus.<br>- Jeu d'attaques (red-team) évalué : 0 fuite du prompt système. | **S5** |

---

## 3. COULD HAVE (Différenciateurs Optionnels)

*Améliorations avancées, dans le périmètre du produit.*

| ID | User Story Technique | Critères d'Acceptation |
| :---: | :---- | :---- |
| **US-14** | **Reformulation de Requête (Query Rewriting)** | Le LLM reformule les questions dont le vocabulaire diffère de celui du manuel avant la recherche ; gain de Recall@6 mesuré sur le benchmark. |
| **US-15** | **Mémoire Conversationnelle** | Les questions de suivi (« et pour le modèle diesel ? ») sont résolues à partir de l'historique de la conversation. |
| **US-16** | **Extension du Corpus** | Ajout d'autres modèles et années de véhicules, avec filtrage par modèle via les métadonnées. |
| **US-17** | **Support de l'Arabe** | Questions et réponses en arabe sur le corpus EN / FR (retrieval cross-lingue). |
| **US-18** | **Manifestes Kubernetes de Déploiement** | Déploiement K8s complet (Deployments, Services, ConfigMaps, Ingress et HPA). |

---

## 4. WON'T HAVE (Exclus du Périmètre Projet)

*Explicitement exclus pour éviter la dispersion :*

- Routage agentique multi-outils (dispatch vers SQL, calculatrice ou autres outils).
- Ingestion multimodale d'images, de schémas ou de photos (modèles de vision) : seul le texte des PDF est indexé.
- Diagnostic de panne ou procédure de réparation au-delà de ce que contient la documentation.
- Entraînement ou fine-tuning de modèles de langage.
- Envoi des données vers des API LLM cloud : tous les modèles tournent localement.
- Facturation SaaS, gestion d'abonnements et paiement.
- Application mobile native iOS / Android (l'interface web responsive suffit).
