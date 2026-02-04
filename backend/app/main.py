"""
TradeMe - API Backend Principal (V2).
FastAPI avec WebSocket, Supabase, et trading temps réel.
"""
import logging
import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .core.config import settings
from .core.alpaca_client import alpaca_client
from .core.llm_client import llm_client
from .core.supabase_client import supabase_client
from .core.news_aggregator import news_aggregator
from .core.watch_service import watch_service
from .core.optimized_watch import optimized_watch
from .core.data_aggregator import data_aggregator
from .agents.manager_agent import agent_manager

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Scheduler pour les cycles de trading
scheduler = AsyncIOScheduler()

# WebSocket connections
websocket_connections: List[WebSocket] = []

# État global du trading
trading_state = {
    "active": False,
    "session_id": None,
    "started_at": None,
    "total_trades": 0,
    "last_cycle": None,
}


# === Modèles Pydantic ===

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    services: Dict[str, bool]
    trading_active: bool


class TradingToggle(BaseModel):
    active: bool


class PerformanceQuery(BaseModel):
    hours: int = 1


# === Lifecycle ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application."""
    logger.info("🚀 Démarrage TradeMe Backend...")
    
    # Initialiser les services
    alpaca_ok = alpaca_client.initialize()
    llm_ok = llm_client.initialize()
    supabase_ok = supabase_client.initialize()
    
    # Initialiser agents avec $10,000 chacun
    agents_ok = agent_manager.initialize(capital_per_agent=10000.0)
    
    logger.info(f"  - Alpaca: {'✅' if alpaca_ok else '❌'}")
    logger.info(f"  - OpenRouter: {'✅' if llm_ok else '❌'}")
    logger.info(f"  - Supabase: {'✅' if supabase_ok else '❌'}")
    logger.info(f"  - Agents: {'✅' if agents_ok else '❌'}")
    
    # Initialiser l'agrégateur de news
    news_ok = news_aggregator.initialize()
    logger.info(f"  - News Aggregator: {'✅' if news_ok else '❌'}")
    
    # Initialiser le service de veille
    watch_ok = watch_service.initialize()
    logger.info(f"  - Watch Service: {'✅' if watch_ok else '❌'}")
    
    # Initialiser le service de veille optimisé
    opt_watch_ok = optimized_watch.initialize()
    logger.info(f"  - Optimized Watch: {'✅' if opt_watch_ok else '❌'}")
    
    # Synchroniser les agents en BDD avec $10,000
    if supabase_ok and agents_ok:
        await sync_agents_to_db()
    
    # Ajouter les jobs du scheduler
    scheduler.add_job(
        trading_cycle,
        'interval',
        minutes=settings.trading_interval_minutes,
        id='trading_cycle',
        replace_existing=True,
    )
    scheduler.add_job(
        snapshot_performance,
        'interval',
        seconds=60,
        id='snapshot_performance',
        replace_existing=True,
    )
    # Job de veille économique - 3 fois/jour pendant fermeture marché (toutes les 5h)
    # Heures: ~23h, ~04h, ~09h (marché fermé 22h-15h30)
    scheduler.add_job(
        hourly_watch_cycle,
        'interval',
        hours=5,
        id='hourly_watch',
        replace_existing=True,
    )
    # Job de revue des positions (toutes les 5 minutes quand marché ouvert)
    scheduler.add_job(
        position_review_cycle,
        'interval',
        minutes=5,
        id='position_review',
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"⏰ Scheduler initialisé (trading désactivé par défaut)")
    
    yield
    
    # Cleanup
    logger.info("🛑 Arrêt TradeMe Backend...")
    if trading_state["active"] and trading_state["session_id"]:
        supabase_client.end_trading_session(
            trading_state["session_id"], 
            trading_state["total_trades"]
        )
    scheduler.shutdown()


async def sync_agents_to_db():
    """Synchronise les agents en mémoire avec la BDD (charge les données existantes)."""
    for agent_name, agent in agent_manager.get_all_agents().items():
        db_agent = supabase_client.get_agent_by_name(agent.name)
        
        if db_agent:
            # Charger le capital ACTUEL depuis la BDD (ne pas réinitialiser!)
            agent.db_id = db_agent['id']
            agent.current_capital = float(db_agent.get('current_capital', 10000.0))
            agent.total_fees = float(db_agent.get('total_fees', 0))
            logger.info(f"💰 {agent.name}: Capital chargé depuis BDD = ${agent.current_capital:.2f}")


# === Application FastAPI ===

app = FastAPI(
    title="TradeMe - Multi-AI Trading Platform",
    description="Plateforme de trading automatisé avec plusieurs agents IA",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Fonctions Trading ===

async def trading_cycle():
    """Cycle de trading automatique."""
    if not trading_state["active"]:
        return
    
    logger.info("🔄 Début du cycle de trading...")
    trading_state["last_cycle"] = datetime.now().isoformat()
    
    try:
        if not alpaca_client.is_market_open():
            logger.info("📴 Marché fermé, cycle ignoré")
            await broadcast_update({
                "type": "market_closed",
                "timestamp": datetime.now().isoformat(),
            })
            return
        
        market_data = {
            "account": alpaca_client.get_account(),
            "positions": alpaca_client.get_positions(),
            "movers": alpaca_client.get_movers(limit=50),
            "market_hours": alpaca_client.get_market_hours(),
        }
        
        # 📰 Récupérer les actualités en temps réel
        try:
            news_text = await news_aggregator.format_news_for_agent(limit=15)
            logger.info("📰 Actualités récupérées pour les agents")
        except Exception as e:
            logger.warning(f"⚠️ Erreur récupération news: {e}")
            news_text = None
        
        results = await agent_manager.run_trading_cycle(
            market_data=market_data,
            news=news_text,
            execute_trades=True,
        )
        
        for agent_name, result in results.items():
            if result.get("decision") and result["decision"].get("decision") != "HOLD":
                await save_trade_to_db(agent_name, result)
                trading_state["total_trades"] += 1
        
        await broadcast_update({
            "type": "trading_cycle",
            "timestamp": datetime.now().isoformat(),
            "results": results,
        })
        
        logger.info("✅ Cycle de trading terminé")
        
    except Exception as e:
        logger.error(f"❌ Erreur cycle de trading: {e}")
        await broadcast_update({
            "type": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat(),
        })


async def save_trade_to_db(agent_name: str, result: Dict[str, Any]):
    """Sauvegarde un trade en base de données."""
    agent = agent_manager.get_agent(agent_name)
    if not agent or not hasattr(agent, 'db_id'):
        return
    
    decision = result.get("decision", {})
    
    trade_data = {
        "agent_id": agent.db_id,
        "decision": decision.get("decision", "HOLD"),
        "symbol": decision.get("symbol", ""),
        "quantity": decision.get("quantity", 0),
        "price": decision.get("price", 0),
        "reasoning": decision.get("reasoning", "")[:500],
        "confidence": decision.get("confidence", 0),
        "risk_level": decision.get("risk_level", "MEDIUM"),
        "executed": result.get("executed", False),
        "order_id": result.get("order_id", ""),
    }
    
    supabase_client.insert_trade(trade_data)
    
    supabase_client.update_agent_capital(
        agent.db_id,
        agent.current_capital,
        agent.total_fees,
    )


async def snapshot_performance():
    """Sauvegarde un snapshot de performance pour les graphes."""
    if not supabase_client._initialized:
        return
    
    for agent_name, agent in agent_manager.get_all_agents().items():
        if not hasattr(agent, 'db_id'):
            continue
        
        snapshot_data = {
            "agent_id": agent.db_id,
            "capital": agent.current_capital,
            "performance_pct": agent.get_performance(),
            "total_profit": agent.current_capital - agent.initial_capital,
            "total_fees": agent.total_fees,
            "trade_count": len(agent.history),
        }
        
        supabase_client.insert_snapshot(snapshot_data)


async def hourly_watch_cycle():
    """
    Cycle de veille horaire - Les IAs analysent et préparent leurs trades.
    Exécuté toutes les heures, même quand le marché est fermé.
    """
    logger.info("🔍 Début du cycle de veille horaire...")
    
    try:
        # Lancer la veille pour tous les agents
        reports = await watch_service.run_all_agents_watch()
        
        # Notifier via WebSocket
        await broadcast_update({
            "type": "watch_cycle_complete",
            "timestamp": datetime.now().isoformat(),
            "reports_count": len(reports),
            "agents": list(reports.keys()),
        })
        
        logger.info(f"✅ Cycle de veille terminé - {len(reports)} rapports générés")
        
    except Exception as e:
        logger.error(f"❌ Erreur cycle de veille: {e}")


async def position_review_cycle():
    """
    Cycle de revue des positions - Toutes les 5 minutes quand marché ouvert.
    Les IAs vérifient leurs positions et décident de garder/vendre/ajuster.
    """
    # Ne faire que si le marché est ouvert
    if not alpaca_client.is_market_open():
        return
    
    logger.info("👀 Début de la revue des positions...")
    
    try:
        # Lancer la revue pour tous les agents
        reviews = await watch_service.run_all_position_reviews()
        
        # Notifier via WebSocket
        await broadcast_update({
            "type": "position_review_complete",
            "timestamp": datetime.now().isoformat(),
            "reviews": reviews,
        })
        
        logger.info(f"✅ Revue des positions terminée")
        
    except Exception as e:
        logger.error(f"❌ Erreur revue positions: {e}")


async def broadcast_update(data: Dict[str, Any]):
    """Envoie une mise à jour à tous les clients WebSocket."""
    disconnected = []
    
    for ws in websocket_connections:
        try:
            await ws.send_json(data)
        except Exception:
            disconnected.append(ws)
    
    for ws in disconnected:
        if ws in websocket_connections:
            websocket_connections.remove(ws)


# === Routes API ===

@app.get("/")
async def root():
    """Route racine."""
    return {
        "name": "TradeMe API",
        "version": "2.0.0",
        "status": "running",
        "trading_active": trading_state["active"],
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Vérifie l'état de santé des services."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        services={
            "alpaca": alpaca_client._initialized,
            "openrouter": llm_client._initialized,
            "supabase": supabase_client._initialized,
        },
        trading_active=trading_state["active"],
    )


# === Routes Trading Control ===

@app.get("/api/trading/status")
async def get_trading_status():
    """Récupère l'état actuel du trading."""
    return {
        "active": trading_state["active"],
        "session_id": trading_state["session_id"],
        "started_at": trading_state["started_at"],
        "total_trades": trading_state["total_trades"],
        "last_cycle": trading_state["last_cycle"],
        "market_open": alpaca_client.is_market_open(),
    }


@app.post("/api/trading/toggle")
async def toggle_trading(toggle: TradingToggle):
    """Active ou désactive le trading."""
    if toggle.active and not trading_state["active"]:
        trading_state["active"] = True
        trading_state["started_at"] = datetime.now().isoformat()
        trading_state["total_trades"] = 0
        
        session_id = supabase_client.start_trading_session()
        trading_state["session_id"] = session_id
        
        logger.info("🟢 TRADING ACTIVÉ")
        
        asyncio.create_task(trading_cycle())
        
        await broadcast_update({
            "type": "trading_enabled",
            "timestamp": datetime.now().isoformat(),
        })
        
    elif not toggle.active and trading_state["active"]:
        trading_state["active"] = False
        
        if trading_state["session_id"]:
            supabase_client.end_trading_session(
                trading_state["session_id"],
                trading_state["total_trades"]
            )
        
        logger.info("🔴 TRADING DÉSACTIVÉ")
        
        await broadcast_update({
            "type": "trading_disabled",
            "timestamp": datetime.now().isoformat(),
        })
    
    return {
        "active": trading_state["active"],
        "session_id": trading_state["session_id"],
        "started_at": trading_state["started_at"],
        "total_trades": trading_state["total_trades"],
        "last_cycle": trading_state["last_cycle"],
        "market_open": alpaca_client.is_market_open(),
    }


# === Routes Alpaca ===

@app.get("/api/account")
async def get_account():
    """Récupère les informations du compte Alpaca."""
    account = alpaca_client.get_account()
    if not account:
        raise HTTPException(status_code=503, detail="Alpaca non disponible")
    return account


@app.get("/api/positions")
async def get_positions():
    """Récupère les positions actuelles."""
    return alpaca_client.get_positions()


@app.get("/api/market/hours")
async def get_market_hours():
    """Récupère les heures de marché."""
    hours = alpaca_client.get_market_hours()
    if not hours:
        raise HTTPException(status_code=503, detail="Impossible de récupérer les heures")
    return hours


@app.get("/api/market/movers")
async def get_movers(limit: int = 20):
    """Récupère les top movers du marché."""
    return alpaca_client.get_movers(limit=limit)


@app.get("/api/assets")
async def get_assets(limit: int = 100, active_only: bool = True):
    """Liste les actifs disponibles pour le trading."""
    assets = alpaca_client.get_all_assets()
    if active_only:
        assets = [a for a in assets if a.get('tradable', False)]
    return assets[:limit]


# === Routes Agents ===

@app.get("/api/agents")
async def list_agents():
    """Liste tous les agents et leurs stats depuis la BDD."""
    if supabase_client._initialized:
        return supabase_client.get_leaderboard()
    return agent_manager.get_all_stats()


@app.get("/api/agents/{name}")
async def get_agent(name: str):
    """Récupère les détails d'un agent."""
    if supabase_client._initialized:
        agent = supabase_client.get_agent_by_name(name)
        if agent:
            return agent
    
    agent = agent_manager.get_agent(name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' non trouvé")
    return agent.to_dict()


@app.get("/api/leaderboard")
async def get_leaderboard():
    """Récupère le classement des agents depuis la BDD."""
    if supabase_client._initialized:
        return supabase_client.get_leaderboard()
    return agent_manager.get_leaderboard()


# === Routes Trades ===

@app.get("/api/trades")
async def get_trades(limit: int = 100, agent: str = None):
    """Récupère l'historique des trades depuis la BDD."""
    if supabase_client._initialized:
        if agent:
            agent_data = supabase_client.get_agent_by_name(agent)
            if agent_data:
                return supabase_client.get_trades(agent_id=agent_data['id'], limit=limit)
        return supabase_client.get_recent_trades(limit=limit)
    
    all_trades = []
    for name, ag in agent_manager.get_all_agents().items():
        for trade in ag.history[-limit:]:
            t = trade.to_dict()
            t['agent_name'] = name
            all_trades.append(t)
    return sorted(all_trades, key=lambda x: x['timestamp'], reverse=True)[:limit]


# === Routes Autocritiques ===

@app.get("/api/autocritiques")
async def get_autocritiques(limit: int = 20, agent: str = None):
    """Récupère les autocritiques des agents depuis la BDD."""
    if supabase_client._initialized:
        try:
            if agent:
                agent_data = supabase_client.get_agent_by_name(agent)
                if agent_data:
                    return supabase_client.get_autocritiques(agent_id=agent_data['id'], limit=limit)
            # Récupérer toutes les autocritiques
            response = supabase_client.client.table('autocritiques').select('*').order(
                'created_at', desc=True
            ).limit(limit).execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Erreur get_autocritiques: {e}")
            return []
    return []


# === Routes Performance (Graphes) ===

@app.get("/api/performance")
async def get_performance(hours: int = 1):
    """Récupère les données de performance pour les graphes."""
    if supabase_client._initialized:
        data = supabase_client.get_snapshots_for_chart(hours=hours)
        return {
            "hours": hours,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        }
    
    return {
        "hours": hours,
        "data": {
            agent.name: [{
                "time": datetime.now().isoformat(),
                "capital": agent.current_capital,
                "performance": agent.get_performance(),
            }]
            for name, agent in agent_manager.get_all_agents().items()
        },
        "timestamp": datetime.now().isoformat(),
    }


# === Routes Test ===

@app.get("/api/news")
async def get_news(limit: int = 20):
    """Récupère les actualités financières en temps réel."""
    try:
        news = await news_aggregator.get_market_news(limit=limit)
        sentiment = await news_aggregator.get_sentiment_summary()
        trending = await news_aggregator.get_trending_topics()
        
        return {
            "success": True,
            "news": news,
            "sentiment": sentiment,
            "trending": trending,
            "count": len(news),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Erreur get_news: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/news/formatted")
async def get_formatted_news(limit: int = 15):
    """Récupère les actualités formatées comme les agents les voient."""
    try:
        formatted = await news_aggregator.format_news_for_agent(limit=limit)
        return {
            "success": True,
            "formatted_news": formatted,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# === Routes Veille (Watch) ===

@app.get("/api/watch/reports")
async def get_watch_reports(
    agent: str = None,
    report_type: str = None,
    limit: int = 20
):
    """
    Récupère les rapports de veille des agents.
    
    Args:
        agent: Filtrer par agent (Grok, DeepSeek, GPT, Consortium)
        report_type: Filtrer par type (hourly_watch, market_analysis, etc.)
        limit: Nombre max de rapports
    """
    try:
        reports = watch_service.get_latest_reports(
            agent_name=agent,
            report_type=report_type,
            limit=limit
        )
        
        # Parser les JSON stockés
        for report in reports:
            for field in ['key_insights', 'opportunities', 'risks', 'watchlist', 
                          'planned_actions', 'questions_asked', 'answers', 'sources_consulted']:
                if report.get(field) and isinstance(report[field], str):
                    try:
                        report[field] = json.loads(report[field])
                    except:
                        pass
        
        return {
            "success": True,
            "reports": reports,
            "count": len(reports),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Erreur get_watch_reports: {e}")
        return {"success": False, "error": str(e), "reports": []}


@app.get("/api/watch/opportunities")
async def get_opportunities(agent: str = None, status: str = "pending"):
    """
    Récupère les opportunités détectées par les agents.
    
    Args:
        agent: Filtrer par agent
        status: pending, acted, expired, cancelled
    """
    try:
        opportunities = watch_service.get_active_opportunities(agent_name=agent)
        return {
            "success": True,
            "opportunities": opportunities,
            "count": len(opportunities),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Erreur get_opportunities: {e}")
        return {"success": False, "error": str(e), "opportunities": []}


@app.get("/api/watch/latest/{agent_name}")
async def get_agent_latest_watch(agent_name: str):
    """
    Récupère le dernier rapport de veille d'un agent spécifique.
    """
    try:
        reports = watch_service.get_latest_reports(agent_name=agent_name, limit=1)
        
        if not reports:
            return {
                "success": False,
                "error": f"Aucun rapport trouvé pour {agent_name}",
                "report": None,
            }
        
        report = reports[0]
        
        # Parser les JSON
        for field in ['key_insights', 'opportunities', 'risks', 'watchlist', 
                      'planned_actions', 'questions_asked', 'answers', 'sources_consulted']:
            if report.get(field) and isinstance(report[field], str):
                try:
                    report[field] = json.loads(report[field])
                except:
                    pass
        
        return {
            "success": True,
            "report": report,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Erreur get_agent_latest_watch: {e}")
        return {"success": False, "error": str(e), "report": None}


@app.post("/api/watch/run")
async def trigger_watch_cycle(agent: str = None):
    """
    Déclenche manuellement un cycle de veille.
    
    Args:
        agent: Nom de l'agent spécifique (optionnel, tous si non spécifié)
    """
    try:
        if agent:
            # Récupérer l'ID de l'agent
            agents = supabase_client.get_agents() if supabase_client._initialized else []
            agent_id = None
            for a in agents:
                if a["name"] == agent:
                    agent_id = a["id"]
                    break
            
            report = await watch_service.run_hourly_watch(agent, agent_id)
            return {
                "success": True,
                "message": f"Veille lancée pour {agent}",
                "report": report,
            }
        else:
            reports = await watch_service.run_all_agents_watch()
            return {
                "success": True,
                "message": "Veille lancée pour tous les agents",
                "reports_count": len(reports),
            }
    except Exception as e:
        logger.error(f"Erreur trigger_watch_cycle: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/watch/review-positions")
async def trigger_position_review():
    """
    Déclenche manuellement une revue des positions.
    """
    try:
        reviews = await watch_service.run_all_position_reviews()
        return {
            "success": True,
            "message": "Revue des positions terminée",
            "reviews": reviews,
        }
    except Exception as e:
        logger.error(f"Erreur trigger_position_review: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/watch/position-reviews")
async def get_position_reviews(agent: str = None, limit: int = 50):
    """
    Récupère l'historique des revues de positions.
    """
    try:
        if not supabase_client._initialized:
            return {"success": False, "error": "Supabase non initialisé", "reviews": []}
        
        query = supabase_client.client.table('position_reviews').select('*')
        
        if agent:
            agent_data = supabase_client.get_agent_by_name(agent)
            if agent_data:
                query = query.eq('agent_id', agent_data['id'])
        
        response = query.order('created_at', desc=True).limit(limit).execute()
        
        return {
            "success": True,
            "reviews": response.data if response.data else [],
            "count": len(response.data) if response.data else 0,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Erreur get_position_reviews: {e}")
        return {"success": False, "error": str(e), "reviews": []}


# === VEILLE OPTIMISÉE (mode économique) ===

@app.get("/api/watch/optimized/run")
async def run_optimized_watch():
    """
    Lance une veille OPTIMISÉE avec minimum de tokens.
    Coût estimé: ~$0.05-0.10 par exécution
    """
    try:
        results = await optimized_watch.run_all_agents_quick()
        
        return {
            "success": True,
            "message": "Veille optimisée terminée",
            "results": results,
            "token_usage": optimized_watch.get_daily_usage_report(),
        }
    except Exception as e:
        logger.error(f"Erreur veille optimisée: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/watch/usage")
async def get_token_usage():
    """Récupère le rapport d'utilisation des tokens."""
    return {
        "success": True,
        "usage": optimized_watch.get_daily_usage_report(),
    }


@app.post("/api/watch/budget")
async def set_daily_budget(budget_usd: float = 3.0):
    """Définit le budget quotidien maximum."""
    if budget_usd < 0.5:
        return {"success": False, "error": "Budget minimum: $0.50"}
    if budget_usd > 50:
        return {"success": False, "error": "Budget maximum: $50"}
    
    optimized_watch.set_daily_budget(budget_usd)
    return {
        "success": True,
        "message": f"Budget fixé à ${budget_usd}/jour",
        "usage": optimized_watch.get_daily_usage_report(),
    }


@app.get("/api/data/market-context")
async def get_market_context():
    """
    Récupère le contexte de marché SANS appel LLM.
    Sources: Fear & Greed, Yahoo, Reddit, Alpaca news
    100% GRATUIT
    """
    try:
        context = await data_aggregator.get_full_market_context()
        formatted = data_aggregator.format_context_for_llm(context, max_tokens=1000)
        
        return {
            "success": True,
            "raw_context": context,
            "formatted_for_llm": formatted,
            "sources_used": list(context.keys()),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Erreur market context: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/data/technical/{symbol}")
async def get_technical_analysis(symbol: str):
    """
    Analyse technique locale pour un symbole.
    Calculs RSI, MACD, SMA SANS LLM - GRATUIT
    """
    try:
        signal = await data_aggregator.calculate_technical_signal(symbol)
        
        return {
            "success": True,
            "symbol": symbol,
            "signal": {
                "rsi": signal.rsi,
                "rsi_signal": "oversold" if signal.rsi < 30 else "overbought" if signal.rsi > 70 else "neutral",
                "macd_signal": signal.macd_signal,
                "trend": signal.trend,
                "confidence": signal.confidence,
            },
            "cost": "$0.00 (local calculation)",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Erreur analyse technique {symbol}: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/test/alpaca")
async def test_alpaca():
    """Teste la connexion Alpaca."""
    account = alpaca_client.get_account()
    return {"success": account is not None, "account": account}


@app.get("/api/test/llm")
async def test_llm(model: str = "openai/gpt-4o-mini"):
    """Teste la connexion OpenRouter."""
    result = await llm_client.test_connection(model)
    return result


@app.get("/api/test/supabase")
async def test_supabase():
    """Teste la connexion Supabase."""
    if not supabase_client._initialized:
        return {"success": False, "error": "Non initialisé"}
    
    agents = supabase_client.get_agents()
    return {"success": True, "agents_count": len(agents), "agents": [a['name'] for a in agents]}


@app.post("/api/test/execute/{agent_name}")
async def test_execute_order(agent_name: str, symbol: str = "AAPL", action: str = "BUY", qty: int = 1):
    """TEST: Exécute un ordre réel pour vérifier que l'IA peut vraiment trader."""
    agent = agent_manager.get_agent(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' non trouvé")
    
    try:
        order = alpaca_client.submit_order(
            symbol=symbol,
            qty=qty,
            side=action.lower(),
            order_type="market"
        )
        
        return {
            "success": True,
            "agent": agent_name,
            "order": order,
            "message": f"Ordre {action} {qty} {symbol} exécuté"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === WebSocket ===

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket pour les mises à jour en temps réel."""
    await websocket.accept()
    websocket_connections.append(websocket)
    
    logger.info(f"🔌 Nouveau client WebSocket ({len(websocket_connections)} total)")
    
    try:
        await websocket.send_json({
            "type": "initial_state",
            "trading_status": {
                "active": trading_state["active"],
                "total_trades": trading_state["total_trades"],
            },
            "agents": agent_manager.get_all_stats(),
            "leaderboard": supabase_client.get_leaderboard() if supabase_client._initialized else [],
            "market_hours": alpaca_client.get_market_hours(),
        })
        
        while True:
            data = await websocket.receive_text()
            
            if data == "ping":
                await websocket.send_json({"type": "pong"})
            elif data == "refresh":
                await websocket.send_json({
                    "type": "refresh",
                    "trading_status": {
                        "active": trading_state["active"],
                        "total_trades": trading_state["total_trades"],
                    },
                    "agents": agent_manager.get_all_stats(),
                    "leaderboard": supabase_client.get_leaderboard() if supabase_client._initialized else [],
                })
                
    except WebSocketDisconnect:
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)
        logger.info(f"🔌 Client WebSocket déconnecté ({len(websocket_connections)} restants)")


# === Point d'entrée ===

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
