-- =====================================================
-- TRADEME - MÉMOIRE RAG & DONNÉES ALTERNATIVES
-- À exécuter dans le SQL Editor de Supabase
-- =====================================================

-- Activer pgvector pour la recherche sémantique
CREATE EXTENSION IF NOT EXISTS vector;

-- =====================================================
-- TABLE: trade_memories
-- Stocke les souvenirs de chaque trade avec contexte complet
-- Permet aux IAs d'apprendre de leurs erreurs
-- =====================================================
CREATE TABLE IF NOT EXISTS trade_memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    trade_id UUID REFERENCES trades(id) ON DELETE SET NULL,
    
    -- Contexte du trade
    symbol VARCHAR(10) NOT NULL,
    decision VARCHAR(10) NOT NULL,
    entry_price DECIMAL(15, 4) NOT NULL,
    exit_price DECIMAL(15, 4),
    quantity DECIMAL(15, 4) NOT NULL,
    
    -- Résultat (rempli à la clôture)
    pnl DECIMAL(15, 2),
    pnl_percent DECIMAL(10, 4),
    success BOOLEAN,  -- true si gain, false si perte
    holding_duration_hours INTEGER,
    
    -- Contexte marché au moment du trade
    market_sentiment VARCHAR(20),  -- BULLISH, BEARISH, NEUTRAL
    vix_level DECIMAL(10, 2),
    sector VARCHAR(50),
    market_trend VARCHAR(20),  -- UP, DOWN, SIDEWAYS
    
    -- Indicateurs techniques
    rsi_value DECIMAL(5, 2),
    volume_ratio DECIMAL(10, 2),  -- vs moyenne
    price_vs_sma20 DECIMAL(10, 4),  -- % au-dessus/dessous SMA20
    
    -- Données alternatives au moment du trade
    dark_pool_ratio DECIMAL(5, 4),
    options_sentiment VARCHAR(20),  -- BULLISH, BEARISH, NEUTRAL
    insider_activity VARCHAR(20),  -- BUYING, SELLING, NONE
    
    -- Le raisonnement de l'IA
    reasoning TEXT,
    confidence INTEGER,
    
    -- Leçon apprise (générée après clôture)
    lesson_learned TEXT,
    
    -- Embedding pour recherche sémantique (optionnel)
    embedding vector(1536),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    closed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index pour recherche rapide
CREATE INDEX idx_memories_agent ON trade_memories(agent_id);
CREATE INDEX idx_memories_symbol ON trade_memories(symbol);
CREATE INDEX idx_memories_success ON trade_memories(success);
CREATE INDEX idx_memories_sector ON trade_memories(sector);
CREATE INDEX idx_memories_created ON trade_memories(created_at DESC);

-- Index pour recherche vectorielle (si pgvector activé)
-- CREATE INDEX idx_memories_embedding ON trade_memories USING ivfflat (embedding vector_cosine_ops);

-- =====================================================
-- TABLE: market_context
-- Stocke le contexte de marché pour analyse historique
-- =====================================================
CREATE TABLE IF NOT EXISTS market_context (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Indices majeurs
    spy_price DECIMAL(15, 4),
    spy_change_pct DECIMAL(10, 4),
    qqq_price DECIMAL(15, 4),
    qqq_change_pct DECIMAL(10, 4),
    
    -- Volatilité
    vix_level DECIMAL(10, 2),
    
    -- Sentiment général
    market_sentiment VARCHAR(20),
    fear_greed_index INTEGER,  -- 0-100
    
    -- Dark Pool & Options (données alternatives)
    dark_pool_volume_ratio DECIMAL(5, 4),  -- % du volume total
    put_call_ratio DECIMAL(10, 4),
    options_gamma_exposure DECIMAL(15, 2),
    
    -- Top movers
    top_gainers JSONB,  -- [{symbol, change_pct}, ...]
    top_losers JSONB,
    
    -- Volume
    market_volume_ratio DECIMAL(10, 2),  -- vs moyenne 20 jours
    
    snapshot_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_context_time ON market_context(snapshot_at DESC);

-- =====================================================
-- TABLE: smart_money_signals
-- Signaux de "Smart Money" (Dark Pools, Options, Insiders)
-- =====================================================
CREATE TABLE IF NOT EXISTS smart_money_signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    symbol VARCHAR(10) NOT NULL,
    signal_type VARCHAR(30) NOT NULL,  -- DARK_POOL, OPTIONS_FLOW, INSIDER
    
    -- Détails du signal
    direction VARCHAR(10) NOT NULL,  -- BULLISH, BEARISH
    strength VARCHAR(10) NOT NULL,  -- LOW, MEDIUM, HIGH
    
    -- Dark Pool spécifique
    dark_pool_volume DECIMAL(20, 2),
    dark_pool_pct DECIMAL(5, 4),
    
    -- Options spécifique
    options_volume INTEGER,
    options_premium DECIMAL(15, 2),
    call_put_ratio DECIMAL(10, 4),
    unusual_activity BOOLEAN DEFAULT FALSE,
    
    -- Insider spécifique
    insider_name VARCHAR(100),
    insider_title VARCHAR(100),
    transaction_type VARCHAR(20),  -- BUY, SELL
    transaction_value DECIMAL(15, 2),
    
    -- Métadonnées
    source VARCHAR(50),
    raw_data JSONB,
    
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_signals_symbol ON smart_money_signals(symbol);
CREATE INDEX idx_signals_type ON smart_money_signals(signal_type);
CREATE INDEX idx_signals_time ON smart_money_signals(detected_at DESC);
CREATE INDEX idx_signals_direction ON smart_money_signals(direction);

-- =====================================================
-- TABLE: agent_statistics
-- Statistiques détaillées par agent pour Kelly Criterion
-- =====================================================
CREATE TABLE IF NOT EXISTS agent_statistics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    
    -- Statistiques globales
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(5, 4) DEFAULT 0,
    
    -- Ratios de gains/pertes
    avg_win_pct DECIMAL(10, 4) DEFAULT 0,
    avg_loss_pct DECIMAL(10, 4) DEFAULT 0,
    win_loss_ratio DECIMAL(10, 4) DEFAULT 0,  -- avg_win / avg_loss
    
    -- Par niveau de confiance
    stats_by_confidence JSONB DEFAULT '{}',
    -- Ex: {"70-80": {"trades": 10, "wins": 7}, "80-90": {"trades": 5, "wins": 4}}
    
    -- Par secteur
    stats_by_sector JSONB DEFAULT '{}',
    
    -- Par type de signal
    stats_by_signal JSONB DEFAULT '{}',
    
    -- Kelly optimal calculé
    kelly_fraction DECIMAL(5, 4) DEFAULT 0.25,
    optimal_position_pct DECIMAL(5, 4) DEFAULT 0.02,
    
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(agent_id)
);

CREATE INDEX idx_stats_agent ON agent_statistics(agent_id);

-- =====================================================
-- FONCTION: update_agent_statistics
-- Recalcule les stats d'un agent après chaque trade fermé
-- =====================================================
CREATE OR REPLACE FUNCTION update_agent_statistics(p_agent_id UUID)
RETURNS void AS $$
DECLARE
    v_total INTEGER;
    v_wins INTEGER;
    v_losses INTEGER;
    v_avg_win DECIMAL;
    v_avg_loss DECIMAL;
BEGIN
    -- Compter les trades fermés
    SELECT 
        COUNT(*),
        COUNT(*) FILTER (WHERE success = true),
        COUNT(*) FILTER (WHERE success = false)
    INTO v_total, v_wins, v_losses
    FROM trade_memories
    WHERE agent_id = p_agent_id AND success IS NOT NULL;
    
    -- Calculer les moyennes
    SELECT 
        COALESCE(AVG(pnl_percent) FILTER (WHERE success = true), 0),
        COALESCE(ABS(AVG(pnl_percent) FILTER (WHERE success = false)), 0.01)
    INTO v_avg_win, v_avg_loss
    FROM trade_memories
    WHERE agent_id = p_agent_id AND success IS NOT NULL;
    
    -- Upsert les statistiques
    INSERT INTO agent_statistics (agent_id, total_trades, winning_trades, losing_trades, win_rate, avg_win_pct, avg_loss_pct, win_loss_ratio, kelly_fraction)
    VALUES (
        p_agent_id,
        v_total,
        v_wins,
        v_losses,
        CASE WHEN v_total > 0 THEN v_wins::DECIMAL / v_total ELSE 0 END,
        v_avg_win,
        v_avg_loss,
        CASE WHEN v_avg_loss > 0 THEN v_avg_win / v_avg_loss ELSE 1 END,
        -- Kelly = W - (1-W)/R, plafonné à 0.25
        LEAST(0.25, GREATEST(0, 
            (CASE WHEN v_total > 0 THEN v_wins::DECIMAL / v_total ELSE 0 END) - 
            (1 - CASE WHEN v_total > 0 THEN v_wins::DECIMAL / v_total ELSE 0 END) / 
            NULLIF(CASE WHEN v_avg_loss > 0 THEN v_avg_win / v_avg_loss ELSE 1 END, 0)
        ))
    )
    ON CONFLICT (agent_id) DO UPDATE SET
        total_trades = EXCLUDED.total_trades,
        winning_trades = EXCLUDED.winning_trades,
        losing_trades = EXCLUDED.losing_trades,
        win_rate = EXCLUDED.win_rate,
        avg_win_pct = EXCLUDED.avg_win_pct,
        avg_loss_pct = EXCLUDED.avg_loss_pct,
        win_loss_ratio = EXCLUDED.win_loss_ratio,
        kelly_fraction = EXCLUDED.kelly_fraction,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- VUE: agent_memory_summary
-- Résumé de la mémoire par agent
-- =====================================================
CREATE OR REPLACE VIEW agent_memory_summary AS
SELECT 
    a.id AS agent_id,
    a.name AS agent_name,
    COUNT(tm.id) AS total_memories,
    COUNT(*) FILTER (WHERE tm.success = true) AS successful_trades,
    COUNT(*) FILTER (WHERE tm.success = false) AS failed_trades,
    ROUND(AVG(tm.pnl_percent) FILTER (WHERE tm.success = true), 2) AS avg_win_pct,
    ROUND(AVG(tm.pnl_percent) FILTER (WHERE tm.success = false), 2) AS avg_loss_pct,
    MODE() WITHIN GROUP (ORDER BY tm.sector) AS favorite_sector,
    ROUND(AVG(tm.confidence), 0) AS avg_confidence
FROM agents a
LEFT JOIN trade_memories tm ON a.id = tm.agent_id
GROUP BY a.id, a.name;

-- =====================================================
-- VUE: recent_smart_signals
-- Signaux Smart Money des dernières 24h
-- =====================================================
CREATE OR REPLACE VIEW recent_smart_signals AS
SELECT 
    symbol,
    signal_type,
    direction,
    strength,
    dark_pool_pct,
    options_volume,
    unusual_activity,
    detected_at
FROM smart_money_signals
WHERE detected_at > NOW() - INTERVAL '24 hours'
ORDER BY detected_at DESC;
