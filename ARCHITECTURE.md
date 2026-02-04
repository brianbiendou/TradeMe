# 🧠 MyTrader Backend - Documentation Technique

Ce document explique en détail l'architecture et le fonctionnement du backend de MyTrader, une plateforme de trading automatisé utilisant plusieurs intelligences artificielles.

---

## 📁 Structure du Projet

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # Point d'entrée
│   ├── agents/              # Les agents IA
│   │   ├── __init__.py
│   │   ├── base_agent.py    # Classe de base
│   │   ├── grok_agent.py    # Agent Grok
│   │   ├── deepseek_agent.py # Agent DeepSeek
│   │   ├── openai_agent.py  # Agent OpenAI
│   │   └── manager_agent.py # Orchestrateur
│   └── core/                # Modules centraux
│       ├── __init__.py
│       ├── config.py        # Configuration
│       ├── alpaca_client.py # API Alpaca
│       └── llm_client.py    # API OpenRouter
├── requirements.txt
└── test_connection.py
```

---

## 🔧 Configuration (`core/config.py`)

### Fonctionnement
Le fichier `config.py` utilise **Pydantic Settings** pour charger les variables d'environnement de manière type-safe.

1. Charge le fichier `.env` à la racine via `python-dotenv`
2. Crée une classe `Settings` qui mappe les variables d'environnement
3. Exporte une instance `settings` utilisable partout dans l'app

### Variables d'environnement requises
| Variable | Description |
|----------|-------------|
| `ALPACA_API_KEY` | Clé API Alpaca |
| `ALPACA_API_SECRET` | Secret API Alpaca |
| `ALPACA_BASE_URL` | URL de l'API (paper ou live) |
| `OPENROUTER_API_KEY` | Clé API OpenRouter |

### Modèles IA configurés
- **Grok** : `x-ai/grok-beta` (accès X/Twitter)
- **DeepSeek** : `deepseek/deepseek-r1` (analyse technique)
- **OpenAI** : `openai/gpt-4o` (analyse fondamentale)

---

## 🔌 Client Alpaca (`core/alpaca_client.py`)

### Qu'est-ce qu'Alpaca ?
Alpaca est un broker API-first qui permet d'exécuter des trades programmatiquement sur les marchés américains.

### Fonctionnalités implémentées

#### 1. `get_account()`
Récupère les informations du compte (solde, pouvoir d'achat, etc.).

#### 2. `get_positions()`
Liste toutes les positions actuelles du portefeuille.

#### 3. `get_market_data(symbol, timeframe, limit)`
Récupère les données historiques d'une action (barres OHLCV).

#### 4. `submit_order(symbol, qty, side, type, time_in_force)`
Soumet un ordre d'achat ou de vente au marché.
- `side` : "buy" ou "sell"
- `type` : "market" (exécution immédiate au prix du marché)
- `time_in_force` : "day" (valide pour la journée)

#### 5. `get_all_assets()`
Liste tous les actifs tradables (filtrés par NYSE, NASDAQ, AMEX).

#### 6. `get_movers(limit)`
**La fonction la plus complexe** - Scanne le marché pour trouver :
- **Top Gainers** : Actions avec la plus forte hausse
- **Top Losers** : Actions avec la plus forte baisse
- **High Volume** : Actions les plus tradées

**Comment ça marche :**
1. Récupère la liste de tous les actifs actifs
2. Limite à 400 symboles pour éviter les timeouts
3. Récupère les snapshots par chunks de 100
4. Calcule le % de variation vs la clôture précédente
5. Trie et retourne les top N de chaque catégorie

---

## 🤖 Client LLM (`core/llm_client.py`)

### Qu'est-ce qu'OpenRouter ?
OpenRouter est une API unifiée qui donne accès à plusieurs modèles IA (OpenAI, Anthropic, Grok, Mistral, etc.) via une seule interface.

### Fonctionnement de `generate_response()`

1. **Construction du payload** :
   ```python
   {
     "model": model,           # Ex: "openai/gpt-4o"
     "messages": [
       {"role": "system", "content": system_prompt},
       {"role": "user", "content": user_content}
     ],
     "temperature": 0.7        # Créativité (0=déterministe, 1=créatif)
   }
   ```

2. **Envoi de la requête** HTTP POST vers `/chat/completions`

3. **Parsing de la réponse** : Extrait le contenu du premier choix

### Headers requis
- `Authorization: Bearer <OPENROUTER_API_KEY>`
- `HTTP-Referer` : Pour les statistiques OpenRouter
- `X-Title` : Nom de l'application

---

## 🧬 Agent de Base (`agents/base_agent.py`)

### Philosophie
Chaque agent IA est un **trader virtuel autonome** avec :
- Une personnalité (sniper, technique, fondamental)
- Un historique de trades
- Un système d'autocritique

### Attributs principaux
| Attribut | Description |
|----------|-------------|
| `name` | Nom de l'agent (ex: "Grok") |
| `model` | ID du modèle LLM à utiliser |
| `personality` | Prompt de personnalité |
| `history` | Liste des décisions passées |
| `total_fees` | Frais cumulés (pénalité $1/trade) |

### Méthodes principales

#### 1. `get_system_prompt()`
Génère le prompt système qui définit le comportement de l'agent.

**Contenu clé :**
- Objectif : MAXIMISER LES PROFITS
- Stratégie : Chercher des "gems", pas suivre le troupeau
- Conscience des frais : Chaque trade coûte
- Auto-amélioration continue

#### 2. `autocritique()`
**Innovation majeure** - L'agent s'auto-évalue tous les 5-10 trades.

**Questions posées :**
- Est-ce que je trade trop ?
- Est-ce que je suis le troupeau ?
- Ai-je raté un signal de vente ?
- Comment faire PLUS de profit ?

Retourne un "monologue interne" qui influence les décisions futures.

#### 3. `analyze_market(market_data, news)`
**Boucle de décision principale** :

1. Exécute l'autocritique
2. Construit un prompt avec :
   - Données de marché actuelles
   - Actualités/sentiment
   - Frais payés jusqu'ici
   - Critique interne
3. Demande au LLM une décision JSON :
   ```json
   {
     "decision": "BUY|SELL|HOLD",
     "symbol": "TICKER",
     "quantity": 10,
     "reasoning": "Explication...",
     "confidence": 85
   }
   ```

#### 4. `execute_trade(decision)`
Exécute la décision :
- `HOLD` : Ne fait rien, log le raisonnement
- `BUY`/`SELL` : Appelle `alpaca.submit_order()`
- Ajoute $1 de frais simulés

---

## 🎯 Agents Spécialisés

### Grok Agent (`grok_agent.py`)
**Personnalité : Sniper / Contrarian**

- Cherche les **biotech, pharma, volatilité**
- Connecté à X (Twitter) pour les rumeurs
- Prêt à prendre de **gros risques**
- Évite ce que tout le monde achète (Nvidia, etc.)
- Cherche des gains de +20% en un jour

### DeepSeek Agent (`deepseek_agent.py`)
**Personnalité : Analyste Technique**

- Vit dans les **graphiques**
- Indicateurs : RSI, MACD, Bollinger Bands
- **Nerveux mais précis**
- Change d'avis rapidement si le trend casse
- Surfe sur le momentum, sort avant le crash

### OpenAI Agent (`openai_agent.py`)
**Personnalité : Investisseur Fondamental**

- Cherche les **"gems" sous-évaluées**
- Analyse la santé financière + macro
- Ne suit pas aveuglément les Big Tech
- Veut des **earnings surprises**, rotation sectorielle
- Style "holder" mais flexible

---

## 🎛 Manager Agent (`agents/manager_agent.py`)

### Rôle
L'orchestrateur qui coordonne tous les agents.

### Cycle de Trading (`run_cycle()`)

1. **Market Screener** :
   - Appelle `alpaca.get_movers(limit=10)`
   - Formate les résultats (gainers, losers, volume)

2. **Dispatch aux agents** :
   - Lance les 3 agents **en parallèle** (asyncio)
   - Chaque agent reçoit les mêmes données de marché

3. **Exécution des décisions** :
   - Chaque agent analyse et exécute sa propre décision

### Mode Collaboratif (🚧 En développement)
L'idée est que les 3 IA **votent** :
- Vote majoritaire
- Ou pondération basée sur la performance historique
- Un seul trade pour le compte "Collaboratif"

---

## 🔄 Flux d'exécution complet

```
1. main.py lance ManagerAgent.run()
        ↓
2. ManagerAgent scanne le marché via Alpaca
        ↓
3. Dispatch les données aux 3 agents en parallèle
        ↓
4. Chaque agent:
   a. S'autocritique
   b. Analyse les données avec son LLM
   c. Génère une décision JSON
   d. Exécute le trade sur Alpaca
        ↓
5. Les trades sont loggés
        ↓
6. Cycle terminé, attendre le prochain intervalle
```

---

## 💾 Base de données (`database/init_schema.sql`)

### Tables

#### `trades`
Historique de tous les trades exécutés.
| Colonne | Type | Description |
|---------|------|-------------|
| `id` | UUID | Identifiant unique |
| `agent_id` | TEXT | "grok", "deepseek", "openai", "collaborative" |
| `symbol` | TEXT | Ticker de l'action |
| `action` | TEXT | "BUY", "SELL", "HOLD" |
| `quantity` | NUMERIC | Nombre d'actions |
| `price` | NUMERIC | Prix d'exécution |
| `status` | TEXT | "PENDING", "FILLED", etc. |
| `reasoning` | TEXT | Justification de l'IA |

#### `agent_logs`
Pensées et critiques des agents.
| Colonne | Type | Description |
|---------|------|-------------|
| `agent_id` | TEXT | ID de l'agent |
| `log_type` | TEXT | "THOUGHT", "CRITIQUE", "DECISION" |
| `content` | TEXT | Contenu du log |

#### `portfolio_snapshots`
Snapshots de la valeur du portfolio.
| Colonne | Type | Description |
|---------|------|-------------|
| `agent_id` | TEXT | ID de l'agent |
| `total_value` | NUMERIC | Valeur totale |
| `cash_balance` | NUMERIC | Cash disponible |
| `positions_value` | NUMERIC | Valeur des positions |

---

## 🚀 Comment lancer

```bash
# 1. Installer les dépendances
pip install -r requirements.txt

# 2. Configurer .env
# ALPACA_API_KEY=...
# ALPACA_API_SECRET=...
# OPENROUTER_API_KEY=...

# 3. Lancer
python -m app.main
```

---

## 🔮 Améliorations futures

1. **WebSocket temps réel** : Streamer les décisions vers le frontend
2. **Mode collaboratif** : Implémenter le vote entre IA
3. **Backtesting** : Tester sur données historiques
4. **Stop-loss automatiques** : Gestion du risque intégrée
5. **Connexion X API** : Vraie connexion pour Grok (pas simulée)
