"""
Client Alpaca pour le trading.
Gère toutes les interactions avec l'API Alpaca (paper ou live trading).
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, GetAssetsRequest
from alpaca.trading.enums import OrderSide, TimeInForce, AssetClass, AssetStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockSnapshotRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed  # V2.5: Pour le feed IEX gratuit

from .config import settings
from .symbol_whitelist import filter_symbols, ALLOWED_SYMBOLS  # V2.5: Filtrage symboles

logger = logging.getLogger(__name__)


class AlpacaClient:
    """
    Client pour interagir avec l'API Alpaca.
    Supporte paper trading et live trading.
    """
    
    def __init__(self):
        """Initialise les clients Alpaca."""
        self.trading_client: Optional[TradingClient] = None
        self.data_client: Optional[StockHistoricalDataClient] = None
        self._initialized = False
    
    def initialize(self) -> bool:
        """
        Initialise la connexion à Alpaca.
        Returns: True si succès, False sinon.
        """
        if not settings.is_alpaca_configured():
            logger.warning("⚠️ Alpaca non configuré - clés API manquantes")
            return False
        
        try:
            # Client Trading
            self.trading_client = TradingClient(
                api_key=settings.alpaca_api_key,
                secret_key=settings.alpaca_api_secret,
                paper=settings.paper_trading
            )
            
            # Client Data (pour les données de marché)
            self.data_client = StockHistoricalDataClient(
                api_key=settings.alpaca_api_key,
                secret_key=settings.alpaca_api_secret
            )
            
            self._initialized = True
            logger.info("✅ Alpaca initialisé avec succès")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur initialisation Alpaca: {e}")
            return False
    
    def get_account(self) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations du compte.
        Returns: Dict avec infos compte ou None si erreur.
        """
        if not self._initialized:
            logger.error("Alpaca non initialisé")
            return None
        
        try:
            account = self.trading_client.get_account()
            return {
                "id": str(account.id),
                "status": account.status.value if account.status else "unknown",
                "currency": account.currency,
                "cash": float(account.cash) if account.cash else 0.0,
                "portfolio_value": float(account.portfolio_value) if account.portfolio_value else 0.0,
                "buying_power": float(account.buying_power) if account.buying_power else 0.0,
                "equity": float(account.equity) if account.equity else 0.0,
                "last_equity": float(account.last_equity) if account.last_equity else 0.0,
                "daytrade_count": account.daytrade_count,
                "pattern_day_trader": account.pattern_day_trader,
            }
        except Exception as e:
            logger.error(f"Erreur get_account: {e}")
            return None
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Récupère toutes les positions actuelles.
        Returns: Liste des positions.
        """
        if not self._initialized:
            logger.error("Alpaca non initialisé")
            return []
        
        try:
            positions = self.trading_client.get_all_positions()
            return [
                {
                    "symbol": pos.symbol,
                    "qty": float(pos.qty) if pos.qty else 0.0,
                    "market_value": float(pos.market_value) if pos.market_value else 0.0,
                    "cost_basis": float(pos.cost_basis) if pos.cost_basis else 0.0,
                    "unrealized_pl": float(pos.unrealized_pl) if pos.unrealized_pl else 0.0,
                    "unrealized_plpc": float(pos.unrealized_plpc) if pos.unrealized_plpc else 0.0,
                    "current_price": float(pos.current_price) if pos.current_price else 0.0,
                    "avg_entry_price": float(pos.avg_entry_price) if pos.avg_entry_price else 0.0,
                    "side": pos.side.value if pos.side else "long",
                }
                for pos in positions
            ]
        except Exception as e:
            logger.error(f"Erreur get_positions: {e}")
            return []
    
    def get_market_data(
        self, 
        symbol: str, 
        timeframe: str = "1Day", 
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Récupère les données historiques d'une action.
        
        Args:
            symbol: Symbole de l'action (ex: "AAPL")
            timeframe: Intervalle ("1Min", "5Min", "15Min", "1Hour", "1Day")
            limit: Nombre de barres à récupérer
            
        Returns: Liste des barres OHLCV
        """
        if not self._initialized:
            logger.error("Alpaca non initialisé")
            return []
        
        try:
            # Mapping timeframe
            tf_map = {
                "1Min": TimeFrame.Minute,
                "5Min": TimeFrame(5, "Min"),
                "15Min": TimeFrame(15, "Min"),
                "1Hour": TimeFrame.Hour,
                "1Day": TimeFrame.Day,
            }
            
            tf = tf_map.get(timeframe, TimeFrame.Day)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)  # 1 an de données max
            
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=tf,
                start=start_date,
                end=end_date,
                limit=limit,
                feed=DataFeed.IEX  # V2.5: Utiliser IEX feed (gratuit) au lieu de SIP
            )
            
            bars = self.data_client.get_stock_bars(request)
            
            # V2.5: Accéder via .data pour BarSet (fix compatibilité)
            bars_data = bars.data if hasattr(bars, 'data') else bars
            
            if symbol not in bars_data:
                return []
            
            return [
                {
                    "timestamp": bar.timestamp.isoformat() if hasattr(bar, 'timestamp') else bar.get('timestamp'),
                    "open": float(bar.open if hasattr(bar, 'open') else bar.get('open', 0)),
                    "high": float(bar.high if hasattr(bar, 'high') else bar.get('high', 0)),
                    "low": float(bar.low if hasattr(bar, 'low') else bar.get('low', 0)),
                    "close": float(bar.close if hasattr(bar, 'close') else bar.get('close', 0)),
                    "volume": int(bar.volume if hasattr(bar, 'volume') else bar.get('volume', 0)),
                    "vwap": float(bar.vwap) if (hasattr(bar, 'vwap') and bar.vwap) else bar.get('vwap'),
                }
                for bar in bars_data[symbol]
            ]
        except Exception as e:
            logger.error(f"Erreur get_market_data pour {symbol}: {e}")
            return []
    
    def submit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str = "limit",
        time_in_force: str = "day",
        limit_price: float = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Soumet un ordre d'achat ou de vente.
        
        V2.3: Utilise des ordres LIMIT par défaut pour éviter le slippage.
        
        Args:
            symbol: Symbole de l'action
            qty: Quantité à acheter/vendre
            side: "buy" ou "sell"
            order_type: "limit" (défaut) ou "market"
            time_in_force: "day", "gtc", "ioc", "fok"
            limit_price: Prix limite (requis pour ordre limit, calculé si absent)
            
        Returns: Détails de l'ordre ou None si erreur
        """
        if not self._initialized:
            logger.error("Alpaca non initialisé")
            return None
        
        try:
            order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
            
            tif_map = {
                "day": TimeInForce.DAY,
                "gtc": TimeInForce.GTC,
                "ioc": TimeInForce.IOC,
                "fok": TimeInForce.FOK,
            }
            tif = tif_map.get(time_in_force.lower(), TimeInForce.DAY)
            
            # === V2.3: ORDRES LIMIT PAR DÉFAUT ===
            if order_type.lower() == "limit":
                # Si pas de prix limite fourni, calculer un prix raisonnable
                if limit_price is None:
                    snapshot = self.get_latest_quote(symbol)
                    if snapshot:
                        if side.lower() == "buy":
                            # Pour un achat, on met le prix limite légèrement au-dessus du ask
                            # +0.1% pour avoir une bonne chance d'exécution
                            limit_price = round(snapshot["ask_price"] * 1.001, 2)
                        else:
                            # Pour une vente, on met le prix limite légèrement en-dessous du bid
                            # -0.1% pour avoir une bonne chance d'exécution
                            limit_price = round(snapshot["bid_price"] * 0.999, 2)
                    else:
                        # Fallback: utiliser les données de marché
                        market_data = self.get_market_data(symbol, "1Min", 1)
                        if market_data:
                            current_price = market_data[-1]["close"]
                            if side.lower() == "buy":
                                limit_price = round(current_price * 1.001, 2)
                            else:
                                limit_price = round(current_price * 0.999, 2)
                        else:
                            # Dernier recours: passer en ordre market
                            logger.warning(f"⚠️ Impossible d'obtenir le prix pour {symbol}, passage en ordre MARKET")
                            order_type = "market"
                
                if order_type.lower() == "limit" and limit_price:
                    order_request = LimitOrderRequest(
                        symbol=symbol,
                        qty=qty,
                        side=order_side,
                        time_in_force=tif,
                        limit_price=limit_price,
                    )
                    logger.info(f"📊 Ordre LIMIT: {side.upper()} {qty} {symbol} @ ${limit_price:.2f}")
                else:
                    order_request = MarketOrderRequest(
                        symbol=symbol,
                        qty=qty,
                        side=order_side,
                        time_in_force=tif
                    )
            else:
                # Ordre MARKET explicitement demandé
                order_request = MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=order_side,
                    time_in_force=tif
                )
                logger.info(f"⚠️ Ordre MARKET (slippage possible): {side.upper()} {qty} {symbol}")
            
            order = self.trading_client.submit_order(order_request)
            
            logger.info(f"✅ Ordre soumis: {side.upper()} {qty} {symbol}")
            
            return {
                "id": str(order.id),
                "client_order_id": order.client_order_id,
                "symbol": order.symbol,
                "qty": float(order.qty) if order.qty else qty,
                "side": order.side.value,
                "type": order.type.value if order.type else order_type,
                "limit_price": limit_price if order_type.lower() == "limit" else None,
                "status": order.status.value if order.status else "pending",
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
                "filled_at": order.filled_at.isoformat() if order.filled_at else None,
                "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur submit_order {side} {qty} {symbol}: {e}")
            return None
    
    def get_latest_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Récupère la dernière cotation (bid/ask) pour un symbole.
        
        Args:
            symbol: Symbole de l'action
            
        Returns: Dict avec bid_price, ask_price, etc. ou None
        """
        if not self._initialized:
            return None
        
        try:
            from alpaca.data.requests import StockLatestQuoteRequest
            
            request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quotes = self.data_client.get_stock_latest_quote(request)
            
            if symbol in quotes:
                quote = quotes[symbol]
                return {
                    "symbol": symbol,
                    "bid_price": float(quote.bid_price) if quote.bid_price else 0,
                    "bid_size": int(quote.bid_size) if quote.bid_size else 0,
                    "ask_price": float(quote.ask_price) if quote.ask_price else 0,
                    "ask_size": int(quote.ask_size) if quote.ask_size else 0,
                    "timestamp": quote.timestamp.isoformat() if quote.timestamp else None,
                }
            return None
        except Exception as e:
            logger.warning(f"⚠️ Erreur get_latest_quote pour {symbol}: {e}")
            return None
    
    def get_all_assets(self, tradable_only: bool = True) -> List[Dict[str, Any]]:
        """
        Liste tous les actifs disponibles.
        
        Args:
            tradable_only: Ne retourner que les actifs tradables
            
        Returns: Liste des actifs
        """
        if not self._initialized:
            logger.error("Alpaca non initialisé")
            return []
        
        try:
            request = GetAssetsRequest(
                asset_class=AssetClass.US_EQUITY,
                status=AssetStatus.ACTIVE if tradable_only else None
            )
            
            assets = self.trading_client.get_all_assets(request)
            
            # Filtrer par exchange principaux
            valid_exchanges = {"NYSE", "NASDAQ", "AMEX", "ARCA", "BATS"}
            
            return [
                {
                    "symbol": asset.symbol,
                    "name": asset.name,
                    "exchange": asset.exchange.value if asset.exchange else None,
                    "tradable": asset.tradable,
                    "fractionable": asset.fractionable,
                }
                for asset in assets
                if asset.exchange and asset.exchange.value in valid_exchanges
            ]
        except Exception as e:
            logger.error(f"Erreur get_all_assets: {e}")
            return []
    
    def get_movers(self, limit: int = 10) -> Dict[str, List[Dict[str, Any]]]:
        """
        Récupère les top movers du marché.
        V2.5: Filtré aux symboles S&P500/Nasdaq100 uniquement.
        
        Args:
            limit: Nombre de résultats par catégorie
            
        Returns: Dict avec gainers, losers, et high_volume
        """
        if not self._initialized:
            logger.error("Alpaca non initialisé")
            return {"gainers": [], "losers": [], "high_volume": []}
        
        try:
            # V2.5: Utiliser directement les symboles de la whitelist au lieu de get_all_assets
            symbols = list(ALLOWED_SYMBOLS)[:400]  # Utiliser les symboles autorisés
            
            if not symbols:
                return {"gainers": [], "losers": [], "high_volume": []}
            
            # Récupérer les snapshots par chunks
            all_snapshots = {}
            chunk_size = 100
            
            for i in range(0, len(symbols), chunk_size):
                chunk = symbols[i:i + chunk_size]
                try:
                    request = StockSnapshotRequest(
                        symbol_or_symbols=chunk,
                        feed=DataFeed.IEX  # V2.5: Utiliser IEX feed (gratuit)
                    )
                    snapshots = self.data_client.get_stock_snapshot(request)
                    all_snapshots.update(snapshots)
                except Exception as chunk_error:
                    logger.warning(f"Erreur snapshot chunk: {chunk_error}")
                    continue
            
            # Calculer les variations
            movers_data = []
            for symbol, snapshot in all_snapshots.items():
                if not snapshot or not snapshot.daily_bar or not snapshot.previous_daily_bar:
                    continue
                
                current = float(snapshot.daily_bar.close)
                previous = float(snapshot.previous_daily_bar.close)
                
                if previous == 0:
                    continue
                
                change_pct = ((current - previous) / previous) * 100
                volume = int(snapshot.daily_bar.volume)
                
                movers_data.append({
                    "symbol": symbol,
                    "price": current,
                    "change_pct": round(change_pct, 2),
                    "volume": volume,
                })
            
            # Trier par catégories
            sorted_by_gain = sorted(movers_data, key=lambda x: x["change_pct"], reverse=True)
            sorted_by_loss = sorted(movers_data, key=lambda x: x["change_pct"])
            sorted_by_volume = sorted(movers_data, key=lambda x: x["volume"], reverse=True)
            
            return {
                "gainers": sorted_by_gain[:limit],
                "losers": sorted_by_loss[:limit],
                "high_volume": sorted_by_volume[:limit],
            }
            
        except Exception as e:
            logger.error(f"Erreur get_movers: {e}")
            return {"gainers": [], "losers": [], "high_volume": []}
    
    def is_market_open(self) -> bool:
        """Vérifie si le marché est ouvert."""
        if not self._initialized:
            return False
        
        try:
            clock = self.trading_client.get_clock()
            return clock.is_open
        except Exception as e:
            logger.error(f"Erreur is_market_open: {e}")
            return False
    
    def get_market_hours(self) -> Optional[Dict[str, Any]]:
        """Récupère les heures d'ouverture du marché."""
        if not self._initialized:
            return None
        
        try:
            clock = self.trading_client.get_clock()
            return {
                "is_open": clock.is_open,
                "timestamp": clock.timestamp.isoformat() if clock.timestamp else None,
                "next_open": clock.next_open.isoformat() if clock.next_open else None,
                "next_close": clock.next_close.isoformat() if clock.next_close else None,
            }
        except Exception as e:
            logger.error(f"Erreur get_market_hours: {e}")
            return None


# Instance globale
alpaca_client = AlpacaClient()
