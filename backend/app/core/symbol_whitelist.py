"""
V2.5: Whitelist des symboles autorisés (S&P 500 + Nasdaq 100)
Filtre les symboles exotiques non supportés par Alpaca Free Tier.
"""
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# S&P 500 + NASDAQ 100 SYMBOLS (Alpaca Free Tier Compatible)
# ============================================================================

SP500_SYMBOLS = {
    # Technology
    "AAPL", "MSFT", "GOOGL", "GOOG", "META", "NVDA", "AVGO", "ADBE", "CRM", "CSCO",
    "ORCL", "ACN", "IBM", "INTC", "AMD", "QCOM", "TXN", "NOW", "INTU", "AMAT",
    "MU", "ADI", "LRCX", "KLAC", "SNPS", "CDNS", "MCHP", "FTNT", "PANW", "CRWD",
    "HPQ", "HPE", "DELL", "KEYS", "ZBRA", "EPAM", "CTSH", "IT", "AKAM", "FFIV",
    
    # Finance
    "JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "SCHW", "AXP", "SPGI",
    "CME", "ICE", "MCO", "MSCI", "COF", "USB", "PNC", "TFC", "BK", "STT",
    "AIG", "MET", "PRU", "AFL", "MMC", "AON", "TRV", "CB", "ALL", "PGR",
    "HIG", "CINF", "L", "GL", "WRB", "RE", "BRO", "AJG", "WLTW", "RJF",
    
    # Healthcare
    "UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK", "TMO", "ABT", "DHR", "BMY",
    "AMGN", "GILD", "VRTX", "REGN", "ISRG", "MDT", "SYK", "BDX", "EW", "BSX",
    "ZBH", "DXCM", "IDXX", "IQV", "A", "MTD", "WAT", "ALGN", "HOLX", "TFX",
    "CVS", "CI", "ELV", "HUM", "CNC", "HCA", "UHS", "DVA", "VTRS", "ZTS",
    
    # Consumer Discretionary
    "AMZN", "TSLA", "HD", "MCD", "NKE", "LOW", "SBUX", "TJX", "BKNG", "MAR",
    "HLT", "GM", "F", "CMG", "YUM", "DPZ", "ORLY", "AZO", "BBY", "EBAY",
    "ETSY", "ROST", "TGT", "DG", "DLTR", "KMX", "GPC", "AAP", "LKQ", "POOL",
    "DHI", "LEN", "PHM", "NVR", "TOL", "GRMN", "EXPE", "LVS", "WYNN", "MGM",
    
    # Consumer Staples
    "PG", "KO", "PEP", "COST", "WMT", "PM", "MO", "MDLZ", "CL", "KMB",
    "GIS", "K", "HSY", "SJM", "CAG", "CPB", "HRL", "MKC", "CHD", "CLX",
    "EL", "STZ", "TAP", "BF.B", "KHC", "TSN", "KR", "SYY", "ADM", "BG",
    
    # Energy
    "XOM", "CVX", "COP", "EOG", "SLB", "PXD", "MPC", "PSX", "VLO", "OXY",
    "DVN", "HES", "HAL", "BKR", "FANG", "APA", "MRO", "CTRA", "OKE", "WMB",
    "KMI", "ET", "LNG", "TRGP", "EPD",
    
    # Industrials
    "CAT", "DE", "UNP", "UPS", "FDX", "HON", "RTX", "LMT", "BA", "GD",
    "NOC", "GE", "MMM", "EMR", "ETN", "ITW", "PH", "ROK", "DOV", "SWK",
    "IR", "OTIS", "CARR", "JCI", "TT", "PCAR", "FAST", "CTAS", "PAYX", "CPRT",
    "WM", "RSG", "VRSK", "XYL", "NDSN", "GNRC", "HUBB", "PWR", "AME", "CSX",
    "NSC", "JBHT", "CHRW", "EXPD", "DAL", "UAL", "AAL", "LUV", "ALK",
    
    # Materials
    "LIN", "APD", "SHW", "ECL", "DD", "DOW", "PPG", "NEM", "FCX", "NUE",
    "STLD", "VMC", "MLM", "MOS", "CF", "ALB", "IFF", "FMC", "CE", "EMN",
    "AVY", "SEE", "IP", "PKG", "WRK", "AMCR", "BALL",
    
    # Real Estate
    "AMT", "PLD", "CCI", "EQIX", "SPG", "PSA", "O", "WELL", "DLR", "AVB",
    "EQR", "VTR", "ARE", "MAA", "UDR", "ESS", "PEAK", "HST", "REG", "KIM",
    "BXP", "SLG", "VNO", "HIW", "CBRE", "CSGP", "IRM",
    
    # Utilities
    "NEE", "DUK", "SO", "D", "AEP", "EXC", "SRE", "XEL", "ED", "PEG",
    "WEC", "ES", "AWK", "AEE", "DTE", "CMS", "CNP", "NI", "FE", "EVRG",
    "PPL", "AES", "EIX", "NRG", "ETR", "CEG",
    
    # Communication Services
    "T", "VZ", "CMCSA", "TMUS", "DIS", "NFLX", "CHTR", "WBD", "PARA", "FOX",
    "FOXA", "NWS", "NWSA", "LYV", "EA", "TTWO", "MTCH", "ZG", "Z", "IPG",
    "OMC",
}

NASDAQ100_SYMBOLS = {
    # Already in SP500 but important for Nasdaq
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA", "AVGO", "COST",
    "ADBE", "AMD", "PEP", "CSCO", "NFLX", "TMUS", "CMCSA", "INTC", "INTU", "QCOM",
    "TXN", "AMGN", "HON", "SBUX", "ISRG", "AMAT", "BKNG", "ADI", "GILD", "VRTX",
    "ADP", "MDLZ", "REGN", "LRCX", "PANW", "MU", "SNPS", "CDNS", "KLAC", "MELI",
    "PYPL", "ASML", "ORLY", "MAR", "CTAS", "ABNB", "MCHP", "FTNT", "PCAR", "CHTR",
    "AEP", "DXCM", "PDD", "MRNA", "PAYX", "KDP", "LULU", "MNST", "CPRT", "AZN",
    "ODFL", "ADSK", "KHC", "WDAY", "CRWD", "IDXX", "EXC", "CEG", "FAST", "ROST",
    "EA", "VRSK", "XEL", "BKR", "GEHC", "CTSH", "ZS", "ILMN", "FANG", "ANSS",
    "TTD", "DDOG", "ON", "CDW", "GFS", "TEAM", "BIIB", "WBD", "EBAY", "DLTR",
    "ENPH", "SIRI", "ZM", "OKTA", "RIVN", "LCID", "ARM", "SMCI", "COIN", "MRVL",
}

# Combined whitelist
ALLOWED_SYMBOLS = SP500_SYMBOLS | NASDAQ100_SYMBOLS

# Popular/Liquid additions (covered by Alpaca Free)
POPULAR_ADDITIONS = {
    "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "ARKK", "ARKG", "ARKF",  # ETFs
    "PLTR", "SOFI", "HOOD", "RBLX", "SNOW", "U", "DASH", "UBER", "LYFT",  # Growth
    "AI", "PATH", "UPST", "AFRM", "SQ", "SHOP", "SE", "MELI", "NU",  # Fintech
    "NET", "BILL", "HUBS", "TWLO", "DOCN", "MDB", "CFLT", "ESTC",  # Cloud
    "ROKU", "SPOT", "PINS", "SNAP", "TWTR", "PTON",  # Consumer Tech
}

ALLOWED_SYMBOLS = ALLOWED_SYMBOLS | POPULAR_ADDITIONS


def is_symbol_allowed(symbol: str) -> bool:
    """
    Vérifie si un symbole est dans la whitelist.
    
    Args:
        symbol: Symbole de l'action
        
    Returns:
        True si le symbole est autorisé
    """
    if not symbol:
        return False
    return symbol.upper().strip() in ALLOWED_SYMBOLS


def filter_symbols(symbols: list) -> list:
    """
    Filtre une liste de symboles pour ne garder que les autorisés.
    
    Args:
        symbols: Liste de symboles
        
    Returns:
        Liste filtrée
    """
    filtered = [s for s in symbols if is_symbol_allowed(s)]
    removed = [s for s in symbols if not is_symbol_allowed(s)]
    if removed:
        logger.debug(f"🚫 Symboles filtrés (non supportés): {removed}")
    return filtered


def get_alternative_symbol(rejected_symbol: str) -> str | None:
    """
    Suggère un symbole alternatif quand un symbole est rejeté.
    Basé sur le secteur probable.
    
    Args:
        rejected_symbol: Symbole qui a été rejeté
        
    Returns:
        Un symbole alternatif du même secteur ou None
    """
    # Mapping simplifié des secteurs vers des leaders
    sector_leaders = {
        "tech": ["AAPL", "MSFT", "GOOGL", "NVDA", "META", "AMD", "CRM", "ORCL"],
        "finance": ["JPM", "BAC", "GS", "MS", "C", "WFC", "BLK", "SCHW"],
        "healthcare": ["UNH", "JNJ", "PFE", "ABBV", "MRK", "LLY", "TMO", "ABT"],
        "consumer": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "TGT", "COST"],
        "energy": ["XOM", "CVX", "COP", "SLB", "OXY", "MPC", "PSX", "VLO"],
        "industrial": ["CAT", "DE", "UNP", "HON", "GE", "BA", "RTX", "LMT"],
    }
    
    # Heuristique simple basée sur le nom du symbole
    symbol_upper = rejected_symbol.upper()
    
    # Warrants (W suffix) → Tech
    if symbol_upper.endswith("W") or ".RT" in symbol_upper:
        import random
        return random.choice(sector_leaders["tech"])
    
    # Retourner un leader tech par défaut
    import random
    return random.choice(sector_leaders["tech"])


def validate_and_replace_symbol(symbol: str) -> tuple[str, bool]:
    """
    Valide un symbole et le remplace si nécessaire.
    
    Args:
        symbol: Symbole à valider
        
    Returns:
        (symbole_valide, a_été_remplacé)
    """
    if not symbol:
        return "", False
        
    symbol = symbol.upper().strip()
    
    if is_symbol_allowed(symbol):
        return symbol, False
    
    # Symbole non autorisé, essayer de le remplacer
    alternative = get_alternative_symbol(symbol)
    if alternative:
        logger.warning(f"🔄 Symbole {symbol} non supporté → remplacé par {alternative}")
        return alternative, True
    
    return "", True


# Statistiques
def get_whitelist_stats() -> dict:
    """Retourne des stats sur la whitelist."""
    return {
        "total_symbols": len(ALLOWED_SYMBOLS),
        "sp500_count": len(SP500_SYMBOLS),
        "nasdaq100_count": len(NASDAQ100_SYMBOLS),
        "popular_additions": len(POPULAR_ADDITIONS),
        "sample_symbols": list(ALLOWED_SYMBOLS)[:20]
    }


# Log au chargement
logger.info(f"📋 Whitelist chargée: {len(ALLOWED_SYMBOLS)} symboles (S&P500 + Nasdaq100)")
