"""Script pour liquider toutes les positions Alpaca."""
from app.core.alpaca_client import AlpacaClient

client = AlpacaClient()
client.initialize()

# Récupérer toutes les positions
positions = client.get_positions()
print("=== POSITIONS ACTUELLES ===")
for p in positions:
    print(f"{p['symbol']}: {p['qty']} actions @ ${p['current_price']} (P/L: ${p['unrealized_pl']})")

print("\n=== LIQUIDATION DE TOUTES LES POSITIONS ===")
# Liquider chaque position
for p in positions:
    symbol = p['symbol']
    qty = float(p['qty'])
    if qty > 0:
        result = client.submit_order(symbol, qty, 'sell')
        if result:
            print(f"✅ VENDU {qty} {symbol}")
        else:
            print(f"❌ Erreur vente {symbol}")

print("\n=== VÉRIFICATION ===")
# Vérifier le compte
account = client.get_account()
print(f"Cash: ${account['cash']}")
print(f"Portfolio Value: ${account['portfolio_value']}")
print(f"Buying Power: ${account['buying_power']}")
