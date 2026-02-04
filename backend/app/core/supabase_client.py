"""
Client Supabase pour TradeMe.
Gère toutes les interactions avec la base de données.
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from supabase import create_client, Client
from .config import settings

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Client pour interagir avec Supabase."""
    
    def __init__(self):
        self.client: Optional[Client] = None
        self._initialized = False
    
    def initialize(self) -> bool:
        """Initialise la connexion Supabase."""
        if self._initialized:
            return True
        
        if not settings.supabase_url or not settings.supabase_key:
            logger.error("Supabase URL ou Key manquante")
            return False
        
        try:
            self.client = create_client(
                settings.supabase_url,
                settings.supabase_key
            )
            self._initialized = True
            logger.info("✅ Supabase client initialisé")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur initialisation Supabase: {e}")
            return False
    
    # =====================================================
    # AGENTS
    # =====================================================
    
    def get_agents(self) -> List[Dict[str, Any]]:
        """Récupère tous les agents."""
        if not self._initialized:
            return []
        
        try:
            response = self.client.table('agents').select('*').execute()
            return response.data
        except Exception as e:
            logger.error(f"Erreur get_agents: {e}")
            return []
    
    def get_agent_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Récupère un agent par son nom."""
        if not self._initialized:
            return None
        
        try:
            response = self.client.table('agents').select('*').eq('name', name).single().execute()
            return response.data
        except Exception as e:
            logger.error(f"Erreur get_agent_by_name: {e}")
            return None
    
    def upsert_agent(self, agent_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Crée ou met à jour un agent."""
        if not self._initialized:
            return None
        
        try:
            response = self.client.table('agents').upsert(
                agent_data,
                on_conflict='name'
            ).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Erreur upsert_agent: {e}")
            return None
    
    def update_agent_capital(
        self, 
        agent_id: str, 
        current_capital: float,
        total_fees: float = None,
        total_profit: float = None,
        trade_count: int = None,
        winning_trades: int = None,
        losing_trades: int = None
    ) -> bool:
        """Met à jour le capital d'un agent."""
        if not self._initialized:
            return False
        
        try:
            update_data = {'current_capital': current_capital}
            if total_fees is not None:
                update_data['total_fees'] = total_fees
            if total_profit is not None:
                update_data['total_profit'] = total_profit
            if trade_count is not None:
                update_data['trade_count'] = trade_count
            if winning_trades is not None:
                update_data['winning_trades'] = winning_trades
            if losing_trades is not None:
                update_data['losing_trades'] = losing_trades
            
            self.client.table('agents').update(update_data).eq('id', agent_id).execute()
            return True
        except Exception as e:
            logger.error(f"Erreur update_agent_capital: {e}")
            return False
    
    def update_agent_autocritique(self, agent_id: str, autocritique: str) -> bool:
        """Met à jour l'autocritique d'un agent."""
        if not self._initialized:
            return False
        
        try:
            self.client.table('agents').update({
                'last_autocritique': autocritique
            }).eq('id', agent_id).execute()
            return True
        except Exception as e:
            logger.error(f"Erreur update_agent_autocritique: {e}")
            return False
    
    # =====================================================
    # TRADES
    # =====================================================
    
    def insert_trade(self, trade_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Insère un nouveau trade."""
        if not self._initialized:
            return None
        
        try:
            response = self.client.table('trades').insert(trade_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Erreur insert_trade: {e}")
            return None
    
    def get_trades(
        self, 
        agent_id: str = None, 
        limit: int = 100,
        since: datetime = None
    ) -> List[Dict[str, Any]]:
        """Récupère les trades."""
        if not self._initialized:
            return []
        
        try:
            query = self.client.table('trades').select('*, agents(name)')
            
            if agent_id:
                query = query.eq('agent_id', agent_id)
            if since:
                query = query.gte('created_at', since.isoformat())
            
            response = query.order('created_at', desc=True).limit(limit).execute()
            return response.data
        except Exception as e:
            logger.error(f"Erreur get_trades: {e}")
            return []
    
    def get_recent_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Récupère les trades récents via la vue."""
        if not self._initialized:
            return []
        
        try:
            response = self.client.table('recent_trades').select('*').limit(limit).execute()
            return response.data
        except Exception as e:
            logger.error(f"Erreur get_recent_trades: {e}")
            return []
    
    # =====================================================
    # POSITIONS
    # =====================================================
    
    def upsert_position(self, position_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Crée ou met à jour une position."""
        if not self._initialized:
            return None
        
        try:
            response = self.client.table('positions').upsert(
                position_data,
                on_conflict='agent_id,symbol'
            ).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Erreur upsert_position: {e}")
            return None
    
    def delete_position(self, agent_id: str, symbol: str) -> bool:
        """Supprime une position (quand vendue)."""
        if not self._initialized:
            return False
        
        try:
            self.client.table('positions').delete().eq(
                'agent_id', agent_id
            ).eq('symbol', symbol).execute()
            return True
        except Exception as e:
            logger.error(f"Erreur delete_position: {e}")
            return False
    
    def get_positions_by_agent(self, agent_id: str) -> List[Dict[str, Any]]:
        """Récupère les positions d'un agent."""
        if not self._initialized:
            return []
        
        try:
            response = self.client.table('positions').select('*').eq(
                'agent_id', agent_id
            ).execute()
            return response.data
        except Exception as e:
            logger.error(f"Erreur get_positions_by_agent: {e}")
            return []
    
    # =====================================================
    # PERFORMANCE SNAPSHOTS
    # =====================================================
    
    def insert_snapshot(self, snapshot_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Insère un snapshot de performance."""
        if not self._initialized:
            return None
        
        try:
            response = self.client.table('performance_snapshots').insert(snapshot_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Erreur insert_snapshot: {e}")
            return None
    
    def get_snapshots(
        self, 
        agent_id: str = None, 
        since: datetime = None,
        limit: int = 500
    ) -> List[Dict[str, Any]]:
        """Récupère les snapshots de performance."""
        if not self._initialized:
            return []
        
        try:
            query = self.client.table('performance_snapshots').select('*, agents(name)')
            
            if agent_id:
                query = query.eq('agent_id', agent_id)
            if since:
                query = query.gte('snapshot_at', since.isoformat())
            
            response = query.order('snapshot_at', desc=False).limit(limit).execute()
            return response.data
        except Exception as e:
            logger.error(f"Erreur get_snapshots: {e}")
            return []
    
    def get_snapshots_for_chart(
        self, 
        hours: int = 1
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Récupère les snapshots pour les graphes, groupés par agent.
        """
        if not self._initialized:
            return {}
        
        since = datetime.utcnow() - timedelta(hours=hours)
        snapshots = self.get_snapshots(since=since)
        
        # Grouper par agent
        result = {}
        for snap in snapshots:
            agent_name = snap.get('agents', {}).get('name', 'Unknown')
            if agent_name not in result:
                result[agent_name] = []
            result[agent_name].append({
                'time': snap['snapshot_at'],
                'capital': float(snap['capital']),
                'performance': float(snap['performance_pct']),
            })
        
        return result
    
    # =====================================================
    # AUTOCRITIQUES
    # =====================================================
    
    def insert_autocritique(self, autocritique_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Insère une autocritique."""
        if not self._initialized:
            return None
        
        try:
            response = self.client.table('autocritiques').insert(autocritique_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Erreur insert_autocritique: {e}")
            return None
    
    def get_autocritiques(self, agent_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Récupère les autocritiques d'un agent."""
        if not self._initialized:
            return []
        
        try:
            response = self.client.table('autocritiques').select('*').eq(
                'agent_id', agent_id
            ).order('created_at', desc=True).limit(limit).execute()
            return response.data
        except Exception as e:
            logger.error(f"Erreur get_autocritiques: {e}")
            return []
    
    # =====================================================
    # LEADERBOARD
    # =====================================================
    
    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """Récupère le leaderboard."""
        if not self._initialized:
            return []
        
        try:
            response = self.client.table('leaderboard').select('*').execute()
            return response.data
        except Exception as e:
            logger.error(f"Erreur get_leaderboard: {e}")
            return []
    
    # =====================================================
    # TRADING SESSIONS
    # =====================================================
    
    def start_trading_session(self) -> Optional[str]:
        """Démarre une nouvelle session de trading."""
        if not self._initialized:
            return None
        
        try:
            response = self.client.table('trading_sessions').insert({
                'market_open': True,
                'total_trades': 0
            }).execute()
            return response.data[0]['id'] if response.data else None
        except Exception as e:
            logger.error(f"Erreur start_trading_session: {e}")
            return None
    
    def end_trading_session(self, session_id: str, total_trades: int = 0) -> bool:
        """Termine une session de trading."""
        if not self._initialized:
            return False
        
        try:
            self.client.table('trading_sessions').update({
                'ended_at': datetime.utcnow().isoformat(),
                'market_open': False,
                'total_trades': total_trades
            }).eq('id', session_id).execute()
            return True
        except Exception as e:
            logger.error(f"Erreur end_trading_session: {e}")
            return False


# Instance singleton
supabase_client = SupabaseClient()
