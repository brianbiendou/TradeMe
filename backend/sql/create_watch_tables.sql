-- =====================================================
-- TABLES POUR LA VEILLE TECHNOLOGIQUE DES IAS
-- À exécuter dans Supabase SQL Editor
-- =====================================================

-- Table principale des analyses de veille
CREATE TABLE IF NOT EXISTS ai_watch_reports (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    agent_id UUID REFERENCES agents(id) ON DELETE CASCADE,
    agent_name TEXT NOT NULL,
    
    -- Type d'analyse
    report_type TEXT NOT NULL CHECK (report_type IN (
        'hourly_watch',      -- Veille horaire (marché fermé)
        'market_analysis',   -- Analyse à l'ouverture
        'position_review',   -- Revue des positions (toutes les 5 min)
        'opportunity_scan',  -- Scan d'opportunités
        'news_digest'        -- Digest des actualités
    )),
    
    -- Contenu de l'analyse
    market_status TEXT NOT NULL CHECK (market_status IN ('open', 'closed', 'pre_market', 'after_hours')),
    analysis_summary TEXT NOT NULL,           -- Résumé de l'analyse
    key_insights JSONB DEFAULT '[]',          -- Points clés découverts
    opportunities JSONB DEFAULT '[]',         -- Opportunités identifiées
    risks JSONB DEFAULT '[]',                 -- Risques identifiés
    watchlist JSONB DEFAULT '[]',             -- Actions à surveiller
    
    -- Décisions préparées
    planned_actions JSONB DEFAULT '[]',       -- Actions planifiées pour l'ouverture
    confidence_level INTEGER DEFAULT 0 CHECK (confidence_level BETWEEN 0 AND 100),
    
    -- Questions posées par l'IA
    questions_asked JSONB DEFAULT '[]',       -- Questions que l'IA s'est posée
    answers JSONB DEFAULT '[]',               -- Réponses trouvées
    
    -- Sources utilisées
    sources_consulted JSONB DEFAULT '[]',     -- Sources consultées (news, etc.)
    
    -- Métadonnées
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processing_time_ms INTEGER,               -- Temps de traitement en ms
    tokens_used INTEGER DEFAULT 0             -- Tokens LLM utilisés
);

-- Table pour les opportunités détectées
CREATE TABLE IF NOT EXISTS watch_opportunities (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    agent_id UUID REFERENCES agents(id) ON DELETE CASCADE,
    watch_report_id UUID REFERENCES ai_watch_reports(id) ON DELETE CASCADE,
    
    symbol TEXT NOT NULL,
    company_name TEXT,
    
    -- Analyse de l'opportunité
    opportunity_type TEXT NOT NULL CHECK (opportunity_type IN (
        'breakout',          -- Cassure imminente
        'momentum',          -- Momentum fort
        'news_catalyst',     -- Catalyseur news
        'technical_setup',   -- Configuration technique
        'undervalued',       -- Sous-évalué
        'earnings_play',     -- Jeu sur les résultats
        'sector_rotation'    -- Rotation sectorielle
    )),
    
    direction TEXT NOT NULL CHECK (direction IN ('bullish', 'bearish', 'neutral')),
    
    -- Métriques
    expected_move_pct DECIMAL(8, 2),          -- Mouvement attendu en %
    timeframe TEXT,                            -- Horizon (minutes, hours, days)
    entry_price DECIMAL(12, 4),               -- Prix d'entrée suggéré
    target_price DECIMAL(12, 4),              -- Prix cible
    stop_loss DECIMAL(12, 4),                 -- Stop loss
    
    -- Scoring
    confidence INTEGER DEFAULT 0 CHECK (confidence BETWEEN 0 AND 100),
    risk_reward_ratio DECIMAL(5, 2),
    priority INTEGER DEFAULT 0 CHECK (priority BETWEEN 1 AND 5),  -- 1 = urgent, 5 = peut attendre
    
    -- Raisonnement
    reasoning TEXT,
    supporting_data JSONB DEFAULT '{}',
    
    -- Suivi
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'acted', 'expired', 'cancelled')),
    acted_at TIMESTAMP WITH TIME ZONE,
    result JSONB,                             -- Résultat si actioned
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE       -- Quand l'opportunité expire
);

-- Table pour le suivi des positions en temps réel
CREATE TABLE IF NOT EXISTS position_reviews (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    agent_id UUID REFERENCES agents(id) ON DELETE CASCADE,
    
    symbol TEXT NOT NULL,
    position_type TEXT NOT NULL CHECK (position_type IN ('long', 'short')),
    
    -- État de la position
    entry_price DECIMAL(12, 4) NOT NULL,
    current_price DECIMAL(12, 4) NOT NULL,
    quantity INTEGER NOT NULL,
    
    -- P&L
    unrealized_pnl DECIMAL(12, 2),
    unrealized_pnl_pct DECIMAL(8, 2),
    
    -- Décision de l'IA
    decision TEXT NOT NULL CHECK (decision IN (
        'hold',              -- Garder
        'add',               -- Renforcer
        'reduce',            -- Réduire
        'close',             -- Fermer
        'move_stop'          -- Ajuster le stop
    )),
    new_stop_loss DECIMAL(12, 4),
    new_target DECIMAL(12, 4),
    
    reasoning TEXT NOT NULL,
    confidence INTEGER DEFAULT 0 CHECK (confidence BETWEEN 0 AND 100),
    
    -- Contexte
    market_conditions JSONB DEFAULT '{}',
    technical_indicators JSONB DEFAULT '{}',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index pour les performances
CREATE INDEX IF NOT EXISTS idx_watch_reports_agent ON ai_watch_reports(agent_id);
CREATE INDEX IF NOT EXISTS idx_watch_reports_created ON ai_watch_reports(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_watch_reports_type ON ai_watch_reports(report_type);
CREATE INDEX IF NOT EXISTS idx_watch_reports_market_status ON ai_watch_reports(market_status);

CREATE INDEX IF NOT EXISTS idx_opportunities_agent ON watch_opportunities(agent_id);
CREATE INDEX IF NOT EXISTS idx_opportunities_symbol ON watch_opportunities(symbol);
CREATE INDEX IF NOT EXISTS idx_opportunities_status ON watch_opportunities(status);
CREATE INDEX IF NOT EXISTS idx_opportunities_created ON watch_opportunities(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_position_reviews_agent ON position_reviews(agent_id);
CREATE INDEX IF NOT EXISTS idx_position_reviews_symbol ON position_reviews(symbol);
CREATE INDEX IF NOT EXISTS idx_position_reviews_created ON position_reviews(created_at DESC);

-- Vue pour les dernières analyses
CREATE OR REPLACE VIEW latest_watch_reports AS
SELECT 
    w.*,
    a.name as agent_display_name,
    a.current_capital,
    a.initial_capital
FROM ai_watch_reports w
JOIN agents a ON w.agent_id = a.id
ORDER BY w.created_at DESC;

-- Vue pour les opportunités actives
CREATE OR REPLACE VIEW active_opportunities AS
SELECT 
    o.*,
    a.name as agent_display_name
FROM watch_opportunities o
JOIN agents a ON o.agent_id = a.id
WHERE o.status = 'pending'
  AND (o.expires_at IS NULL OR o.expires_at > NOW())
ORDER BY o.priority ASC, o.confidence DESC;

-- Fonction pour nettoyer les vieilles données (garder 30 jours)
CREATE OR REPLACE FUNCTION cleanup_old_watch_data()
RETURNS void AS $$
BEGIN
    -- Supprimer les rapports de plus de 30 jours
    DELETE FROM ai_watch_reports WHERE created_at < NOW() - INTERVAL '30 days';
    
    -- Supprimer les opportunités expirées de plus de 7 jours
    DELETE FROM watch_opportunities 
    WHERE status != 'pending' AND created_at < NOW() - INTERVAL '7 days';
    
    -- Supprimer les reviews de plus de 7 jours
    DELETE FROM position_reviews WHERE created_at < NOW() - INTERVAL '7 days';
END;
$$ LANGUAGE plpgsql;

-- Activer RLS
ALTER TABLE ai_watch_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE watch_opportunities ENABLE ROW LEVEL SECURITY;
ALTER TABLE position_reviews ENABLE ROW LEVEL SECURITY;

-- Policies (accès public en lecture pour l'API)
CREATE POLICY "Allow all access to watch reports" ON ai_watch_reports FOR ALL USING (true);
CREATE POLICY "Allow all access to opportunities" ON watch_opportunities FOR ALL USING (true);
CREATE POLICY "Allow all access to position reviews" ON position_reviews FOR ALL USING (true);
