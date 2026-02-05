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
from .core.memory_service import memory_service
from .core.smart_data_service import smart_data_service
from .core.kelly_calculator import kelly_calculator
from .core.benchmark_service import benchmark_service
from .core.exit_strategy_manager import exit_strategy_manager
from .core.circuit_breaker import circuit_breaker
from .core.signal_combiner import signal_combiner
from .core.backtest_service import backtest_service
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
    
    # === NOUVEAUX SERVICES V2 ===
    # Mémoire RAG - Les IAs apprennent de leurs erreurs
    memory_ok = memory_service.initialize()
    logger.info(f"  - Memory RAG Service: {'✅' if memory_ok else '❌'}")
    
    # Smart Data - Dark Pool, Options, Insiders
    smart_ok = smart_data_service.initialize()
    logger.info(f"  - Smart Data Service: {'✅' if smart_ok else '❌'}")
    
    # Kelly Calculator - Position sizing optimal
    kelly_ok = kelly_calculator.initialize()
    logger.info(f"  - Kelly Calculator: {'✅' if kelly_ok else '❌'}")
    
    # Benchmark Service - S&P 500 & Berkshire Hathaway
    benchmark_ok = benchmark_service.initialize()
    logger.info(f"  - Benchmark Service: {'✅' if benchmark_ok else '❌'}")
    
    # === NOUVEAUX SERVICES V2.1 - FORTIFICATION ===
    # Exit Strategy Manager - Stop-Loss/Take-Profit automatiques
    exit_ok = exit_strategy_manager.initialize()
    logger.info(f"  - Exit Strategy Manager: {'✅' if exit_ok else '❌'}")
    
    # Circuit Breaker - Protection contre les pertes excessives
    breaker_ok = circuit_breaker.initialize()
    logger.info(f"  - Circuit Breaker: {'✅' if breaker_ok else '❌'}")
    
    # Signal Combiner - Combinaison intelligente des signaux
    combiner_ok = signal_combiner.initialize()
    logger.info(f"  - Signal Combiner: {'✅' if combiner_ok else '❌'}")
    
    # Backtest Service - Validation des stratégies
    backtest_ok = backtest_service.initialize()
    logger.info(f"  - Backtest Service: {'✅' if backtest_ok else '❌'}")
    
    # === NOUVEAUX SERVICES V2.2 - INDICATEURS TECHNIQUES & EARNINGS ===
    from .core.technical_indicators import technical_indicators
    from .core.earnings_calendar import earnings_calendar
    
    # Technical Indicators - RSI, MACD, Support/Résistance, Volume
    tech_ok = technical_indicators.initialize()
    logger.info(f"  - Technical Indicators: {'✅' if tech_ok else '❌'}")
    
    # Earnings Calendar - Éviter les achats avant earnings
    earnings_ok = earnings_calendar.initialize()
    logger.info(f"  - Earnings Calendar: {'✅' if earnings_ok else '❌'}")
    
    # === NOUVEAUX SERVICES V2.3 - TIMING, GATES, MÉMOIRE AMÉLIORÉE ===
    from .core.market_hours_service import market_hours_service
    from .core.technical_gates_service import technical_gates_service
    from .core.enhanced_memory_service import enhanced_memory_service
    
    # === NOUVEAU SERVICE V2.4 - WINNING PATTERNS ===
    from .core.winning_patterns_service import winning_patterns_service
    
    # Market Hours Service - Trading uniquement aux heures de marché (France)
    hours_ok = market_hours_service.initialize()
    logger.info(f"  - Market Hours Service: {'✅' if hours_ok else '❌'}")
    
    # Technical Gates Service - Règles dures RSI/MACD
    gates_ok = technical_gates_service.initialize()
    logger.info(f"  - Technical Gates Service: {'✅' if gates_ok else '❌'}")
    
    # Enhanced Memory Service - Mémoire RAG avec symbole/secteur
    enhanced_mem_ok = enhanced_memory_service.initialize()
    logger.info(f"  - Enhanced Memory Service: {'✅' if enhanced_mem_ok else '❌'}")
    
    # V2.4: Winning Patterns Service - Apprendre des succès
    winning_ok = winning_patterns_service.initialize()
    logger.info(f"  - Winning Patterns Service: {'✅' if winning_ok else '❌'}")
    
    # Synchroniser les agents en BDD avec $10,000
    if supabase_ok and agents_ok:
        await sync_agents_to_db()
    
    # Ajouter les jobs du scheduler
    # === V2.3: Trading continu (toutes les 5 minutes) au lieu de 30 min ===
    scheduler.add_job(
        autonomous_trading_cycle,
        'interval',
        minutes=5,  # V2.3: Cycle rapide toutes les 5 minutes
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

async def autonomous_trading_cycle():
    """
    Cycle de trading AUTONOME V2.3.
    
    AMÉLIORATIONS MAJEURES:
    1. Respect des horaires de marché (fuseau France)
    2. Évite les 30 premières et 15 dernières minutes
    3. Règles techniques DURES (RSI/MACD bloquants)
    4. Ordres LIMIT par défaut (pas de slippage)
    5. Mémoire RAG enrichie (symbole + secteur)
    6. Cycle rapide (5 min) avec décision autonome
    
    Intègre aussi V2.1/V2.2:
    - Circuit Breaker (protection drawdown)
    - Exit Strategy (vérification Stop-Loss/Take-Profit)
    - Signal Combiner (validation des trades)
    - Technical Indicators (RSI, MACD, S/R, Volume)
    - Earnings Calendar (éviter avant earnings)
    """
    if not trading_state["active"]:
        return
    
    trading_state["last_cycle"] = datetime.now().isoformat()
    
    try:
        # === CHECK 0: IMPORTATION DES NOUVEAUX SERVICES V2.3 ===
        from .core.market_hours_service import market_hours_service
        from .core.technical_gates_service import technical_gates_service
        from .core.enhanced_memory_service import enhanced_memory_service
        
        # === CHECK 1: HORAIRES DE MARCHÉ (FRANCE) ===
        market_hours_info = market_hours_service.get_market_hours_info()
        
        if not market_hours_info.can_trade:
            # Log seulement si c'est la première fois ou statut différent
            logger.info(f"⏰ {market_hours_info.reason}")
            await broadcast_update({
                "type": "market_hours_blocked",
                "timestamp": datetime.now().isoformat(),
                "reason": market_hours_info.reason,
                "status": market_hours_info.status.value,
                "next_open": market_hours_info.next_open_paris,
            })
            return
        
        logger.info(f"🔄 Cycle de trading V2.3 - {market_hours_info.trading_window.value}")
        
        # === CHECK 2: EXIT STRATEGY - Vérifier les positions existantes ===
        await check_exit_conditions_for_all_agents()
        
        # Récupérer les données de marché
        market_data = {
            "account": alpaca_client.get_account(),
            "positions": alpaca_client.get_positions(),
            "movers": alpaca_client.get_movers(limit=50),
            "market_hours": alpaca_client.get_market_hours(),
            "market_hours_v23": market_hours_info.to_dict(),  # V2.3
        }
        
        # 📰 Récupérer les actualités en temps réel
        try:
            news_text = await news_aggregator.format_news_for_agent(limit=15)
            logger.info("📰 Actualités récupérées pour les agents")
        except Exception as e:
            logger.warning(f"⚠️ Erreur récupération news: {e}")
            news_text = None
        
        # === CHECK 3: CIRCUIT BREAKER pour chaque agent ===
        agents_allowed = {}
        for agent_name, agent in agent_manager.get_all_agents().items():
            if hasattr(agent, 'db_id') and agent.db_id:
                can_trade, reason = circuit_breaker.can_trade(
                    agent.db_id, agent.current_capital
                )
                agents_allowed[agent_name] = {
                    "can_trade": can_trade,
                    "reason": reason,
                }
                if not can_trade:
                    logger.warning(f"🚫 {agent_name}: {reason}")
            else:
                agents_allowed[agent_name] = {"can_trade": True, "reason": "OK"}
        
        # Exécuter le cycle de trading
        results = await agent_manager.run_trading_cycle(
            market_data=market_data,
            news=news_text,
            execute_trades=True,
            agents_allowed=agents_allowed,  # NOUVEAU: Passer les permissions
        )
        
        # Sauvegarder les trades et mettre à jour le circuit breaker
        for agent_name, result in results.items():
            if result.get("decision") and result["decision"].get("decision") != "HOLD":
                await save_trade_to_db(agent_name, result)
                trading_state["total_trades"] += 1
                
                # === NOUVEAU: Mettre à jour le circuit breaker avec le résultat ===
                agent = agent_manager.get_agent(agent_name)
                if agent and hasattr(agent, 'db_id') and result.get("executed"):
                    pnl = result.get("pnl", 0)  # P&L du trade si disponible
                    circuit_breaker.record_trade_result(
                        agent.db_id, pnl, agent.current_capital
                    )
        
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


async def check_exit_conditions_for_all_agents():
    """
    Vérifie les conditions de sortie pour toutes les positions de tous les agents.
    Exécute automatiquement les Stop-Loss et Take-Profit.
    """
    logger.info("🎯 Vérification des conditions de sortie...")
    
    # Récupérer les données Smart Money pour les signaux de sortie
    smart_data = None
    try:
        if smart_data_service._initialized:
            vix_data = await smart_data_service.get_vix_data()
            fng_data = await smart_data_service.get_fear_greed_index()
            
            # Déterminer le signal global
            vix = vix_data.get("vix", 20)
            fng = fng_data.get("fear_greed_index", 50)
            
            if vix > 30 and fng < 30:
                smart_signal = "STRONG_BEARISH"
            elif vix > 25 or fng < 40:
                smart_signal = "BEARISH"
            elif vix < 15 and fng > 60:
                smart_signal = "BULLISH"
            else:
                smart_signal = "NEUTRAL"
            
            smart_data = {"signal": smart_signal}
    except Exception as e:
        logger.warning(f"⚠️ Erreur récupération Smart Data pour exits: {e}")
    
    for agent_name, agent in agent_manager.get_all_agents().items():
        if not agent.positions or not hasattr(agent, 'db_id'):
            continue
        
        for symbol, position in list(agent.positions.items()):
            try:
                # Récupérer le prix actuel
                market_data = alpaca_client.get_market_data(symbol, "1Day", 1)
                if not market_data:
                    continue
                
                current_price = market_data[-1]["close"]
                
                # Vérifier les conditions de sortie
                exit_signal = exit_strategy_manager.check_exit_conditions(
                    agent_id=agent.db_id,
                    symbol=symbol,
                    current_price=current_price,
                    smart_money_signal=smart_data.get("signal", "NEUTRAL") if smart_data else "NEUTRAL",
                )
                
                if exit_signal.should_exit:
                    logger.warning(f"🚨 EXIT SIGNAL pour {agent_name}/{symbol}: {exit_signal.message}")
                    
                    # Exécuter la sortie automatiquement
                    quantity = position.get("qty", 0)
                    if quantity > 0:
                        exit_decision = {
                            "decision": "SELL",
                            "symbol": symbol,
                            "quantity": quantity,
                            "reasoning": f"AUTO EXIT: {exit_signal.reason.value} - {exit_signal.message}",
                            "confidence": 100,  # Sortie automatique = 100% sûr
                            "exit_reason": exit_signal.reason.value,
                        }
                        
                        success, msg = await agent.execute_trade(exit_decision)
                        
                        if success:
                            logger.info(f"✅ {agent_name}: Sortie auto {symbol} - {exit_signal.reason.value}")
                            
                            # Supprimer les niveaux de sortie
                            exit_strategy_manager.remove_position(agent.db_id, symbol)
                            
                            # Mettre à jour le circuit breaker
                            pnl_pct = exit_signal.current_pnl_pct
                            pnl_amount = position.get("qty", 0) * position.get("avg_price", 0) * pnl_pct
                            circuit_breaker.record_trade_result(
                                agent.db_id, pnl_amount, agent.current_capital
                            )
                            
                            # Broadcast
                            await broadcast_update({
                                "type": "auto_exit",
                                "agent": agent_name,
                                "symbol": symbol,
                                "reason": exit_signal.reason.value,
                                "pnl_pct": exit_signal.current_pnl_pct * 100,
                                "timestamp": datetime.now().isoformat(),
                            })
                        else:
                            logger.error(f"❌ {agent_name}: Échec sortie auto {symbol} - {msg}")
                
            except Exception as e:
                logger.error(f"Erreur vérification exit {agent_name}/{symbol}: {e}")


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


@app.get("/api/benchmarks")
async def get_benchmarks(period: str = "1h"):
    """
    Récupère les données de benchmark pour comparaison.
    
    Args:
        period: 1h, 24h, 7d, 30d, 3m, 6m, 1y, 5y
        
    Returns:
        S&P 500 et Berkshire Hathaway performance data
    """
    try:
        benchmarks = await benchmark_service.get_all_benchmarks(period=period)
        return {
            "success": True,
            "period": period,
            "benchmarks": benchmarks,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Erreur get_benchmarks: {e}")
        return {
            "success": False,
            "error": str(e),
            "benchmarks": {},
        }


@app.get("/api/performance/with-benchmarks")
async def get_performance_with_benchmarks(period: str = "1h"):
    """
    Récupère les performances des agents ET les benchmarks.
    Format unifié pour le graphique frontend.
    
    Args:
        period: 1h, 24h, 7d, 30d, 3m, 6m, 1y, 5y
    """
    try:
        # Convertir période en heures pour les agents
        period_to_hours = {
            "1h": 1,
            "24h": 24,
            "7d": 168,
            "30d": 720,
            "3m": 2160,
            "6m": 4320,
            "1y": 8760,
            "5y": 43800,
        }
        hours = period_to_hours.get(period, 1)
        
        # Récupérer en parallèle
        import asyncio
        
        # Données des agents
        agents_data = {}
        if supabase_client._initialized:
            agents_data = supabase_client.get_snapshots_for_chart(hours=hours)
        else:
            agents_data = {
                agent.name: [{
                    "time": datetime.now().isoformat(),
                    "capital": agent.current_capital,
                    "performance": agent.get_performance(),
                }]
                for name, agent in agent_manager.get_all_agents().items()
            }
        
        # Données des benchmarks
        benchmarks = await benchmark_service.get_all_benchmarks(period=period)
        benchmark_data = benchmark_service.format_benchmarks_for_chart(benchmarks, agents_data)
        
        # Fusionner
        all_data = {**agents_data, **benchmark_data}
        
        return {
            "success": True,
            "period": period,
            "hours": hours,
            "data": all_data,
            "benchmarks_info": {
                "sp500": {
                    "name": "S&P 500",
                    "performance": benchmarks.get("sp500", {}).get("total_performance_pct", 0),
                    "current_price": benchmarks.get("sp500", {}).get("current_price", 0),
                },
                "berkshire": {
                    "name": "Berkshire (Buffett)",
                    "performance": benchmarks.get("berkshire", {}).get("total_performance_pct", 0),
                    "current_price": benchmarks.get("berkshire", {}).get("current_price", 0),
                },
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Erreur get_performance_with_benchmarks: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": {},
        }


# === Routes Winning Patterns V2.4 ===

@app.get("/api/patterns/winning")
async def get_winning_patterns():
    """
    V2.4: Récupère les patterns gagnants identifiés.
    Permet aux IAs d'apprendre des succès passés.
    """
    try:
        from .core.winning_patterns_service import winning_patterns_service
        
        if not winning_patterns_service._initialized:
            return {"success": False, "error": "Winning Patterns Service non initialisé"}
        
        return {
            "success": True,
            "best_hours": winning_patterns_service.get_best_trading_hours(),
            "best_sectors": winning_patterns_service.get_best_sectors(),
            "best_rsi_ranges": winning_patterns_service.get_winning_rsi_ranges(),
            "top_setups": winning_patterns_service.get_best_setups(10),
            "context": winning_patterns_service.get_winning_patterns_context(),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Erreur get_winning_patterns: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/patterns/recommendation/{symbol}")
async def get_pattern_recommendation(
    symbol: str,
    rsi: float = None,
    volume_ratio: float = None,
):
    """
    V2.4: Donne une recommandation basée sur les patterns gagnants pour un symbole.
    
    Args:
        symbol: Symbole de l'action
        rsi: RSI actuel (optionnel)
        volume_ratio: Ratio de volume actuel (optionnel)
    """
    try:
        from .core.winning_patterns_service import winning_patterns_service
        
        if not winning_patterns_service._initialized:
            return {"success": False, "error": "Winning Patterns Service non initialisé"}
        
        current_hour = datetime.now().hour
        
        recommendation = winning_patterns_service.get_pattern_recommendation(
            symbol=symbol.upper(),
            current_rsi=rsi,
            current_hour=current_hour,
            volume_ratio=volume_ratio,
        )
        
        return {
            "success": True,
            "symbol": symbol.upper(),
            "recommendation": recommendation,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Erreur get_pattern_recommendation: {e}")
        return {"success": False, "error": str(e)}


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
