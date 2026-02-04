-- =====================================================
-- TRADEME - SCHEMA SUPABASE
-- À exécuter dans le SQL Editor de Supabase
-- =====================================================

-- Activer les extensions nécessaires
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- TABLE: agents
-- Stocke les informations des agents IA
-- =====================================================
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) NOT NULL UNIQUE,
    model VARCHAR(100) NOT NULL,
    personality TEXT,
    initial_capital DECIMAL(15, 2) NOT NULL DEFAULT 1000.00,
    current_capital DECIMAL(15, 2) NOT NULL DEFAULT 1000.00,
    total_fees DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    total_profit DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    trade_count INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,
    last_autocritique TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index pour recherche rapide par nom
CREATE INDEX idx_agents_name ON agents(name);

-- =====================================================
-- TABLE: trades
-- Historique de tous les trades
-- =====================================================
CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    decision VARCHAR(10) NOT NULL CHECK (decision IN ('BUY', 'SELL', 'HOLD')),
    symbol VARCHAR(10) NOT NULL,
    quantity DECIMAL(15, 4) NOT NULL,
    price DECIMAL(15, 4) NOT NULL,
    total_value DECIMAL(15, 2) GENERATED ALWAYS AS (quantity * price) STORED,
    reasoning TEXT,
    confidence INTEGER CHECK (confidence >= 0 AND confidence <= 100),
    risk_level VARCHAR(10) CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH')),
    executed BOOLEAN DEFAULT FALSE,
    order_id VARCHAR(100),
    pnl DECIMAL(15, 2) DEFAULT 0.00,
    fees DECIMAL(15, 2) DEFAULT 1.00,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index pour recherche par agent et date
CREATE INDEX idx_trades_agent ON trades(agent_id);
CREATE INDEX idx_trades_created ON trades(created_at DESC);
CREATE INDEX idx_trades_symbol ON trades(symbol);

-- =====================================================
-- TABLE: positions
-- Positions actuelles de chaque agent
-- =====================================================
CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    symbol VARCHAR(10) NOT NULL,
    quantity DECIMAL(15, 4) NOT NULL,
    avg_entry_price DECIMAL(15, 4) NOT NULL,
    current_price DECIMAL(15, 4),
    unrealized_pnl DECIMAL(15, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(agent_id, symbol)
);

CREATE INDEX idx_positions_agent ON positions(agent_id);

-- =====================================================
-- TABLE: performance_snapshots
-- Snapshots périodiques pour les graphiques
-- =====================================================
CREATE TABLE IF NOT EXISTS performance_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    capital DECIMAL(15, 2) NOT NULL,
    performance_pct DECIMAL(10, 4) NOT NULL,
    total_profit DECIMAL(15, 2) NOT NULL,
    total_fees DECIMAL(15, 2) NOT NULL,
    trade_count INTEGER NOT NULL,
    snapshot_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_snapshots_agent ON performance_snapshots(agent_id);
CREATE INDEX idx_snapshots_time ON performance_snapshots(snapshot_at DESC);

-- =====================================================
-- TABLE: autocritiques
-- Historique des autocritiques des agents
-- =====================================================
CREATE TABLE IF NOT EXISTS autocritiques (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    trade_count_at_time INTEGER,
    performance_at_time DECIMAL(10, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_autocritiques_agent ON autocritiques(agent_id);

-- =====================================================
-- TABLE: market_data_cache
-- Cache des données de marché
-- =====================================================
CREATE TABLE IF NOT EXISTS market_data_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(10) NOT NULL,
    timeframe VARCHAR(20) NOT NULL,
    data JSONB NOT NULL,
    cached_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    UNIQUE(symbol, timeframe)
);

CREATE INDEX idx_market_cache_symbol ON market_data_cache(symbol);

-- =====================================================
-- TABLE: trading_sessions
-- Sessions de trading (pour tracking)
-- =====================================================
CREATE TABLE IF NOT EXISTS trading_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    market_open BOOLEAN DEFAULT TRUE,
    total_trades INTEGER DEFAULT 0,
    notes TEXT
);

-- =====================================================
-- FONCTIONS
-- =====================================================

-- Fonction pour mettre à jour updated_at automatiquement
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers pour updated_at
CREATE TRIGGER trigger_agents_updated
    BEFORE UPDATE ON agents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trigger_positions_updated
    BEFORE UPDATE ON positions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Fonction pour calculer le win rate
CREATE OR REPLACE FUNCTION calculate_win_rate(agent_uuid UUID)
RETURNS DECIMAL AS $$
DECLARE
    total_trades INTEGER;
    wins INTEGER;
BEGIN
    SELECT winning_trades, (winning_trades + losing_trades)
    INTO wins, total_trades
    FROM agents
    WHERE id = agent_uuid;
    
    IF total_trades = 0 THEN
        RETURN 0;
    END IF;
    
    RETURN (wins::DECIMAL / total_trades) * 100;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- VUES
-- =====================================================

-- Vue du leaderboard
CREATE OR REPLACE VIEW leaderboard AS
SELECT 
    a.id,
    a.name,
    a.model,
    a.initial_capital,
    a.current_capital,
    ROUND(((a.current_capital - a.initial_capital) / a.initial_capital) * 100, 2) AS performance_pct,
    a.total_profit,
    a.total_fees,
    a.trade_count,
    CASE 
        WHEN (a.winning_trades + a.losing_trades) = 0 THEN 0
        ELSE ROUND((a.winning_trades::DECIMAL / (a.winning_trades + a.losing_trades)) * 100, 2)
    END AS win_rate,
    a.updated_at
FROM agents a
ORDER BY performance_pct DESC;

-- Vue des trades récents
CREATE OR REPLACE VIEW recent_trades AS
SELECT 
    t.id,
    a.name AS agent_name,
    t.decision,
    t.symbol,
    t.quantity,
    t.price,
    t.total_value,
    t.confidence,
    t.pnl,
    t.created_at
FROM trades t
JOIN agents a ON t.agent_id = a.id
ORDER BY t.created_at DESC
LIMIT 100;

-- Vue des positions par agent
CREATE OR REPLACE VIEW positions_summary AS
SELECT 
    a.name AS agent_name,
    p.symbol,
    p.quantity,
    p.avg_entry_price,
    p.current_price,
    p.unrealized_pnl,
    ROUND(((p.current_price - p.avg_entry_price) / p.avg_entry_price) * 100, 2) AS change_pct
FROM positions p
JOIN agents a ON p.agent_id = a.id
WHERE p.quantity > 0;

-- =====================================================
-- DONNÉES INITIALES
-- =====================================================

-- Insérer les agents par défaut
INSERT INTO agents (name, model, personality, initial_capital)
VALUES 
    ('Grok', 'x-ai/grok-beta', 'Sniper / Contrarian - Biotech & Pharma', 1000.00),
    ('DeepSeek', 'deepseek/deepseek-r1', 'Analyste Technique - RSI, MACD, Patterns', 1000.00),
    ('GPT', 'openai/gpt-4o', 'Investisseur Long Terme - Fondamentaux', 1000.00),
    ('Consortium', 'collaborative', 'Agent Collaboratif - Vote/Pondération', 1000.00)
ON CONFLICT (name) DO NOTHING;

-- =====================================================
-- POLICIES RLS (Row Level Security)
-- À activer si nécessaire
-- =====================================================

-- Pour l'instant, on garde les tables en mode public
-- ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
-- etc.

-- =====================================================
-- COMMENTAIRES
-- =====================================================

COMMENT ON TABLE agents IS 'Agents IA de trading avec leurs performances';
COMMENT ON TABLE trades IS 'Historique de tous les trades exécutés';
COMMENT ON TABLE positions IS 'Positions actuelles de chaque agent';
COMMENT ON TABLE performance_snapshots IS 'Snapshots pour graphiques de performance';
COMMENT ON TABLE autocritiques IS 'Historique des autocritiques des agents';
