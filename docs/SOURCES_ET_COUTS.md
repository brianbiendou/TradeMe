# 📊 Sources de Données & Estimation des Coûts

## Vue d'Ensemble du Système de Veille

Le système TradeMe utilise une approche **hybride** pour minimiser les coûts:
1. **Collecte de données**: Gratuite ou très peu chère
2. **Pré-analyse locale**: Calculs RSI, MACD, sentiment - 100% GRATUIT
3. **Synthèse IA**: Utilisation minimale de tokens pour les décisions finales

---

## 📡 Sources de Données Disponibles

### ✅ Sources GRATUITES (Intégrées)

| Source | Type | Données | Limite | Fiabilité |
|--------|------|---------|--------|-----------|
| **Alpaca News** | API | News marché, earnings | ∞ (avec compte) | ⭐⭐⭐⭐⭐ |
| **Alpaca Market Data** | API | Prix, volume, historique | ∞ (avec compte) | ⭐⭐⭐⭐⭐ |
| **CNN Fear & Greed** | Scraping | Index sentiment (0-100) | ∞ | ⭐⭐⭐⭐ |
| **Yahoo Finance** | Scraping | Movers, top gainers/losers | ∞ | ⭐⭐⭐⭐ |
| **SEC EDGAR** | API publique | Filings officiels (10-K, 10-Q, 8-K) | ∞ | ⭐⭐⭐⭐⭐ |
| **Reddit (r/wallstreetbets)** | API gratuit | Sentiment social, trending | ∞ | ⭐⭐⭐ |

### 🟡 Sources avec Limites Gratuites

| Source | Type | Limite Gratuite | Au-delà |
|--------|------|-----------------|---------|
| **Finnhub** | API | 60 req/min | $0 (suffisant) |
| **Alpha Vantage** | API | 25 req/jour | $50/mois |
| **Polygon.io** | API | 5 req/min | $29/mois |

### 🔴 Sources Payantes (NON intégrées par défaut)

| Source | Coût | Avantages |
|--------|------|-----------|
| **X/Twitter API** | $100/mois min | Sentiment temps réel |
| **Bloomberg** | $$$$$$ | Données premium |
| **Reuters** | $$$ | News institutionnelles |

---

## 💰 Estimation des Coûts LLM

### Modèles Utilisés (via OpenRouter)

| Modèle | Prix Input (1M tokens) | Prix Output (1M tokens) | Usage |
|--------|------------------------|-------------------------|-------|
| GPT-4o-mini | $0.15 | $0.60 | Analyse générale |
| DeepSeek Chat | $0.14 | $0.28 | Raisonnement |
| Grok-3-mini | $0.30 | $0.50 | Social/trends |

### Consommation par Appel

| Opération | Tokens Estimés | Coût Estimé |
|-----------|----------------|-------------|
| Veille 1 agent (optimisé) | ~800 tokens | $0.001-0.002 |
| Veille tous agents (4) | ~3200 tokens | $0.004-0.008 |
| Revue 1 position | ~500 tokens | $0.001 |
| Cycle trading complet | ~2000 tokens | $0.002-0.004 |

### Scénarios Quotidiens

#### 🟢 Mode Économique (par défaut)
```
Veille horaire: 24h × $0.005 = $0.12/jour
Revues positions: 78 × $0.003 = $0.23/jour (market hours only)
Trading cycles: 78 × $0.003 = $0.23/jour
────────────────────────────────────────────
TOTAL: ~$0.60/jour ≈ $18/mois
```

#### 🟡 Mode Normal
```
Veille complète: 24h × $0.02 = $0.48/jour
Revues détaillées: 78 × $0.01 = $0.78/jour
Trading avec analyse: 78 × $0.01 = $0.78/jour
────────────────────────────────────────────
TOTAL: ~$2/jour ≈ $60/mois
```

#### 🔴 Mode Intensif (NON recommandé)
```
Questions détaillées: 24h × $0.10 = $2.40/jour
Analyses profondes: 78 × $0.05 = $3.90/jour
────────────────────────────────────────────
TOTAL: ~$6/jour ≈ $180/mois
```

---

## 🔧 Architecture Optimisée

### Flux de Données (Mode Économique)

```
┌─────────────────────────────────────────────────────────────┐
│                    COLLECTE (GRATUIT)                        │
├─────────────────────────────────────────────────────────────┤
│ Alpaca → News, Prix, Positions                               │
│ CNN → Fear & Greed Index                                     │
│ Yahoo → Top Movers                                           │
│ Reddit → Trending symbols                                    │
│ SEC → Filings récents                                        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              PRÉ-ANALYSE LOCALE (GRATUIT)                    │
├─────────────────────────────────────────────────────────────┤
│ ✓ RSI, MACD, SMA calculations                                │
│ ✓ Sentiment scoring (keyword-based)                          │
│ ✓ Pattern detection                                          │
│ ✓ Signal aggregation                                         │
│ ✓ Opportunity filtering                                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              SYNTHÈSE LLM (MINIMAL - ~$0.01)                 │
├─────────────────────────────────────────────────────────────┤
│ Prompt court: 400 tokens max                                 │
│ Réponse JSON: 200 tokens max                                 │
│ → Décision: BUY/SELL/HOLD + confidence                       │
└─────────────────────────────────────────────────────────────┘
```

### Optimisations Implémentées

1. **Cache agressif**: Les données sont cachées (TTL variable par source)
2. **Modèles moins chers**: GPT-4o-mini au lieu de GPT-4o
3. **Prompts courts**: 400 tokens max d'input
4. **Réponses limitées**: 200-400 tokens max
5. **Synthèse locale**: Le Consortium vote SANS appel LLM
6. **Budget quotidien**: Limite configurable ($3/jour par défaut)

---

## 📈 Comment Réduire les Coûts Encore Plus

### Option 1: Réduire la Fréquence
```python
# Dans main.py, modifier:
scheduler.add_job(hourly_watch_cycle, 'interval', hours=2)  # toutes les 2h
scheduler.add_job(position_review_cycle, 'interval', minutes=15)  # toutes les 15min
```

### Option 2: Utiliser DeepSeek Exclusivement
DeepSeek est 10x moins cher que GPT-4o:
```python
# Dans optimized_watch.py
def _get_cheap_model(self, agent_name: str) -> str:
    return "deepseek/deepseek-chat"  # Pour tous les agents
```

### Option 3: Désactiver la Veille Hors-Market
```python
# Dans hourly_watch_cycle()
if not alpaca_client.is_market_open():
    return  # Skip veille si marché fermé
```

---

## 🎯 Résumé

| Aspect | Valeur |
|--------|--------|
| **Sources gratuites** | 6+ intégrées |
| **Coût data** | $0/jour |
| **Coût LLM mode éco** | ~$0.60/jour |
| **Coût LLM mode normal** | ~$2/jour |
| **Budget max recommandé** | $3/jour |
| **Analyse locale** | RSI, MACD, SMA, Sentiment |
