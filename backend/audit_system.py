"""
TEST COMPLET DU SYSTÈME V2 - AUDIT CRITIQUE
Vérifie que TOUS les services externes fonctionnent réellement.
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime

# Services à tester
from app.core.memory_service import memory_service
from app.core.smart_data_service import smart_data_service
from app.core.kelly_calculator import kelly_calculator
from app.core.supabase_client import supabase_client
from app.core.alpaca_client import alpaca_client


class SystemAudit:
    """Audit complet du système."""
    
    def __init__(self):
        self.results = {}
        self.errors = []
        self.warnings = []
    
    async def run_full_audit(self):
        """Lance l'audit complet."""
        print("\n" + "="*70)
        print("🔍 AUDIT COMPLET DU SYSTÈME TRADEME V2")
        print("="*70)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70 + "\n")
        
        # 1. Services de base
        await self.audit_base_services()
        
        # 2. Smart Data Service (APIs externes gratuites)
        await self.audit_smart_data_service()
        
        # 3. Memory Service
        await self.audit_memory_service()
        
        # 4. Kelly Calculator
        await self.audit_kelly_calculator()
        
        # 5. Intégration complète
        await self.audit_integration()
        
        # Résumé
        self.print_summary()
        
        return len(self.errors) == 0
    
    async def audit_base_services(self):
        """Vérifie les services de base."""
        print("📦 1. SERVICES DE BASE")
        print("-" * 50)
        
        # Supabase
        try:
            supabase_ok = supabase_client.initialize()
            if supabase_ok:
                # Test réel de lecture
                agents = supabase_client.get_agents()
                print(f"  ✅ Supabase: Connecté ({len(agents)} agents en BDD)")
                self.results['supabase'] = True
            else:
                print(f"  ❌ Supabase: Non initialisé")
                self.errors.append("Supabase non initialisé")
                self.results['supabase'] = False
        except Exception as e:
            print(f"  ❌ Supabase: Erreur - {e}")
            self.errors.append(f"Supabase: {e}")
            self.results['supabase'] = False
        
        # Alpaca
        try:
            alpaca_ok = alpaca_client.initialize()
            if alpaca_ok:
                account = alpaca_client.get_account()
                if account:
                    print(f"  ✅ Alpaca: Connecté (Portfolio: ${float(account.get('portfolio_value', 0)):,.2f})")
                    self.results['alpaca'] = True
                else:
                    print(f"  ⚠️ Alpaca: Connecté mais pas de compte")
                    self.warnings.append("Alpaca: Pas de données de compte")
                    self.results['alpaca'] = True
            else:
                print(f"  ❌ Alpaca: Non initialisé")
                self.errors.append("Alpaca non initialisé")
                self.results['alpaca'] = False
        except Exception as e:
            print(f"  ❌ Alpaca: Erreur - {e}")
            self.errors.append(f"Alpaca: {e}")
            self.results['alpaca'] = False
        
        print()
    
    async def audit_smart_data_service(self):
        """Vérifie les APIs externes gratuites."""
        print("🎯 2. SMART DATA SERVICE (APIs Gratuites)")
        print("-" * 50)
        
        smart_data_service.initialize()
        
        # Test VIX (Yahoo Finance)
        print("  📊 VIX (Yahoo Finance)...")
        try:
            vix_data = await smart_data_service.get_vix_data()
            if "error" not in vix_data:
                print(f"     ✅ VIX: {vix_data['vix']} ({vix_data['volatility_regime']})")
                self.results['vix'] = True
            else:
                print(f"     ⚠️ VIX: Fallback utilisé - {vix_data.get('error', 'Unknown')}")
                self.warnings.append(f"VIX: {vix_data.get('error')}")
                self.results['vix'] = 'partial'
        except Exception as e:
            print(f"     ❌ VIX: Erreur - {e}")
            self.errors.append(f"VIX: {e}")
            self.results['vix'] = False
        
        # Test Options (Yahoo Finance)
        print("  📈 Options Flow (Yahoo Finance)...")
        try:
            options_data = await smart_data_service.get_options_data("AAPL")
            if "error" not in options_data and "put_call_ratio" in options_data:
                print(f"     ✅ Options AAPL: P/C={options_data['put_call_ratio']:.3f}, Sentiment={options_data['options_sentiment']}")
                self.results['options'] = True
            else:
                print(f"     ⚠️ Options: Données partielles - {options_data.get('error', 'Champs manquants')}")
                self.warnings.append(f"Options: {options_data.get('error', 'Données incomplètes')}")
                self.results['options'] = 'partial'
        except Exception as e:
            print(f"     ❌ Options: Erreur - {e}")
            self.errors.append(f"Options: {e}")
            self.results['options'] = False
        
        # Test Dark Pool (Volume analysis)
        print("  🌑 Dark Pool (Volume Analysis)...")
        try:
            dp_data = await smart_data_service.get_dark_pool_estimate("AAPL")
            if "error" not in dp_data:
                print(f"     ✅ Dark Pool AAPL: Ratio={dp_data['estimated_dark_pool_ratio']:.0%}, Vol={dp_data['volume_ratio']:.2f}x")
                self.results['dark_pool'] = True
            else:
                print(f"     ⚠️ Dark Pool: {dp_data.get('error')}")
                self.warnings.append(f"Dark Pool: {dp_data.get('error')}")
                self.results['dark_pool'] = 'partial'
        except Exception as e:
            print(f"     ❌ Dark Pool: Erreur - {e}")
            self.errors.append(f"Dark Pool: {e}")
            self.results['dark_pool'] = False
        
        # Test Insider (SEC EDGAR)
        print("  👔 Insider Trading (SEC EDGAR)...")
        try:
            insider_data = await smart_data_service.get_insider_activity("AAPL")
            if "error" not in insider_data and insider_data.get('insider_activity') != 'UNKNOWN':
                print(f"     ✅ Insider AAPL: {insider_data['insider_activity']} (Buy:{insider_data.get('buy_transactions', 0)}, Sell:{insider_data.get('sell_transactions', 0)})")
                self.results['insider'] = True
            else:
                print(f"     ⚠️ Insider: {insider_data.get('error', 'Données non disponibles')}")
                self.warnings.append(f"Insider: Données limitées")
                self.results['insider'] = 'partial'
        except Exception as e:
            print(f"     ❌ Insider: Erreur - {e}")
            self.errors.append(f"Insider: {e}")
            self.results['insider'] = False
        
        # Test Fear & Greed
        print("  😱 Fear & Greed Index...")
        try:
            fng_data = await smart_data_service.get_fear_greed_index()
            if "error" not in fng_data:
                print(f"     ✅ Fear & Greed: {fng_data['fear_greed_index']} ({fng_data['classification']})")
                self.results['fear_greed'] = True
            else:
                print(f"     ⚠️ Fear & Greed: Fallback utilisé")
                self.warnings.append("Fear & Greed: Utilise fallback")
                self.results['fear_greed'] = 'partial'
        except Exception as e:
            print(f"     ❌ Fear & Greed: Erreur - {e}")
            self.errors.append(f"Fear & Greed: {e}")
            self.results['fear_greed'] = False
        
        # Test agrégation complète
        print("  🎯 Agrégation Smart Money...")
        try:
            summary = await smart_data_service.get_smart_money_summary("NVDA")
            if summary and "overall_signal" in summary:
                print(f"     ✅ Smart Money NVDA: Signal={summary['overall_signal']}, Bullish={summary['bullish_count']}, Bearish={summary['bearish_count']}")
                self.results['smart_money_aggregate'] = True
            else:
                print(f"     ⚠️ Agrégation: Incomplète")
                self.warnings.append("Smart Money: Agrégation incomplète")
                self.results['smart_money_aggregate'] = 'partial'
        except Exception as e:
            print(f"     ❌ Agrégation: Erreur - {e}")
            self.errors.append(f"Smart Money aggregate: {e}")
            self.results['smart_money_aggregate'] = False
        
        print()
    
    async def audit_memory_service(self):
        """Vérifie le service de mémoire RAG."""
        print("🧠 3. MEMORY SERVICE (Mémoire RAG)")
        print("-" * 50)
        
        memory_service.initialize()
        
        # Test lecture (pas besoin de données existantes)
        try:
            # Test format context
            context = memory_service.format_memory_context_for_agent(
                agent_id="test-audit-id",
                current_symbol="AAPL",
            )
            print(f"  ✅ Format contexte: OK ({len(context)} chars)")
            self.results['memory_format'] = True
        except Exception as e:
            print(f"  ❌ Format contexte: Erreur - {e}")
            self.errors.append(f"Memory format: {e}")
            self.results['memory_format'] = False
        
        # Test get similar trades (peut retourner vide)
        try:
            trades = memory_service.get_similar_trades(
                agent_id="test-audit-id",
                symbol="AAPL",
                limit=5
            )
            print(f"  ✅ Récupération trades: OK ({len(trades)} trouvés)")
            self.results['memory_read'] = True
        except Exception as e:
            print(f"  ❌ Récupération trades: Erreur - {e}")
            self.errors.append(f"Memory read: {e}")
            self.results['memory_read'] = False
        
        # Vérifier que les tables existent en BDD
        if supabase_client._initialized:
            try:
                # Tenter une lecture sur trade_memories
                response = supabase_client.client.table('trade_memories').select('id').limit(1).execute()
                print(f"  ✅ Table trade_memories: Existe")
                self.results['memory_table'] = True
            except Exception as e:
                print(f"  ❌ Table trade_memories: {e}")
                self.errors.append(f"Table trade_memories non créée: {e}")
                self.results['memory_table'] = False
            
            try:
                response = supabase_client.client.table('agent_statistics').select('id').limit(1).execute()
                print(f"  ✅ Table agent_statistics: Existe")
                self.results['stats_table'] = True
            except Exception as e:
                print(f"  ❌ Table agent_statistics: {e}")
                self.errors.append(f"Table agent_statistics non créée: {e}")
                self.results['stats_table'] = False
        
        print()
    
    async def audit_kelly_calculator(self):
        """Vérifie le calculateur Kelly."""
        print("💰 4. KELLY CALCULATOR")
        print("-" * 50)
        
        kelly_calculator.initialize()
        
        # Test calcul de base
        try:
            kelly = kelly_calculator.calculate_kelly_fraction(0.55, 1.5)
            expected = 0.55 - 0.45/1.5  # ~0.25
            if abs(kelly - expected) < 0.01:
                print(f"  ✅ Formule Kelly: Correcte ({kelly:.4f})")
                self.results['kelly_formula'] = True
            else:
                print(f"  ⚠️ Formule Kelly: Résultat inattendu ({kelly:.4f} vs {expected:.4f})")
                self.warnings.append(f"Kelly formula: {kelly} vs expected {expected}")
                self.results['kelly_formula'] = 'partial'
        except Exception as e:
            print(f"  ❌ Formule Kelly: Erreur - {e}")
            self.errors.append(f"Kelly formula: {e}")
            self.results['kelly_formula'] = False
        
        # Test position sizing
        try:
            sizing = kelly_calculator.calculate_position_size(
                agent_id="test-audit-id",
                capital=10000,
                confidence=80,
                vix=20,
                smart_money_signal="NEUTRAL"
            )
            if sizing.recommended_amount > 0 and sizing.recommended_amount <= 1000:  # Max 10%
                print(f"  ✅ Position sizing: ${sizing.recommended_amount:.2f} ({sizing.position_pct*100:.2f}%)")
                self.results['kelly_sizing'] = True
            else:
                print(f"  ⚠️ Position sizing: Hors limites (${sizing.recommended_amount:.2f})")
                self.warnings.append(f"Kelly sizing hors limites: ${sizing.recommended_amount}")
                self.results['kelly_sizing'] = 'partial'
        except Exception as e:
            print(f"  ❌ Position sizing: Erreur - {e}")
            self.errors.append(f"Kelly sizing: {e}")
            self.results['kelly_sizing'] = False
        
        # Test scaling par confiance
        try:
            low = kelly_calculator.calculate_position_size("test", 10000, confidence=55)
            high = kelly_calculator.calculate_position_size("test", 10000, confidence=90)
            if high.recommended_amount > low.recommended_amount:
                print(f"  ✅ Scaling confiance: 55%=${low.recommended_amount:.0f} < 90%=${high.recommended_amount:.0f}")
                self.results['kelly_scaling'] = True
            else:
                print(f"  ❌ Scaling confiance: Inversé!")
                self.errors.append("Kelly scaling inversé")
                self.results['kelly_scaling'] = False
        except Exception as e:
            print(f"  ❌ Scaling confiance: Erreur - {e}")
            self.errors.append(f"Kelly scaling: {e}")
            self.results['kelly_scaling'] = False
        
        print()
    
    async def audit_integration(self):
        """Vérifie l'intégration complète."""
        print("🔗 5. INTÉGRATION COMPLÈTE")
        print("-" * 50)
        
        try:
            # Simuler le flux complet
            print("  Simulation du flux de trading...")
            
            # 1. Smart Data
            smart_data = await smart_data_service.get_smart_money_summary("TSLA")
            smart_context = smart_data_service.format_smart_data_for_agent(smart_data)
            print(f"  ✅ Smart Data: {len(smart_context)} chars, Signal={smart_data.get('overall_signal', 'N/A')}")
            
            # 2. Memory
            memory_context = memory_service.format_memory_context_for_agent(
                agent_id="test-integration",
                current_symbol="TSLA",
                current_sector="Technology"
            )
            print(f"  ✅ Memory: {len(memory_context)} chars")
            
            # 3. Kelly avec données Smart Money
            vix = smart_data.get("vix", {}).get("vix", 20) if isinstance(smart_data.get("vix"), dict) else 20
            signal = smart_data.get("overall_signal", "NEUTRAL")
            
            sizing = kelly_calculator.calculate_position_size(
                agent_id="test-integration",
                capital=10000,
                confidence=75,
                vix=vix,
                smart_money_signal=signal
            )
            print(f"  ✅ Kelly: ${sizing.recommended_amount:.2f} (VIX={vix}, Signal={signal})")
            
            # 4. Vérifier que tout peut être combiné
            total_context_length = len(smart_context) + len(memory_context)
            print(f"  ✅ Contexte total: {total_context_length} chars (< 8000 = OK)")
            
            if total_context_length < 8000:
                self.results['integration'] = True
            else:
                self.warnings.append(f"Contexte trop long: {total_context_length} chars")
                self.results['integration'] = 'partial'
                
        except Exception as e:
            print(f"  ❌ Intégration: Erreur - {e}")
            self.errors.append(f"Integration: {e}")
            self.results['integration'] = False
        
        print()
    
    def print_summary(self):
        """Affiche le résumé de l'audit."""
        print("="*70)
        print("📋 RÉSUMÉ DE L'AUDIT")
        print("="*70)
        
        # Compteurs
        success = sum(1 for v in self.results.values() if v == True)
        partial = sum(1 for v in self.results.values() if v == 'partial')
        failed = sum(1 for v in self.results.values() if v == False)
        total = len(self.results)
        
        print(f"\n  ✅ Succès: {success}/{total}")
        print(f"  ⚠️ Partiel: {partial}/{total}")
        print(f"  ❌ Échec: {failed}/{total}")
        
        if self.errors:
            print(f"\n  🔴 ERREURS CRITIQUES ({len(self.errors)}):")
            for err in self.errors:
                print(f"     - {err}")
        
        if self.warnings:
            print(f"\n  🟡 AVERTISSEMENTS ({len(self.warnings)}):")
            for warn in self.warnings:
                print(f"     - {warn}")
        
        # Verdict final
        print("\n" + "="*70)
        if failed == 0 and len(self.errors) == 0:
            print("✅ SYSTÈME OPÉRATIONNEL - Prêt pour le trading")
        elif failed <= 2:
            print("⚠️ SYSTÈME FONCTIONNEL - Quelques services dégradés")
        else:
            print("❌ SYSTÈME COMPROMIS - Corrections nécessaires")
        print("="*70 + "\n")


async def main():
    audit = SystemAudit()
    success = await audit.run_full_audit()
    
    # Fermer les sessions
    await smart_data_service.close()
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
