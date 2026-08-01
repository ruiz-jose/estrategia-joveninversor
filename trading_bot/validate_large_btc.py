import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DEFAULT_CONFIG
from engine.data_fetcher import DataFetcher
from engine.backtester import Backtester

fetcher = DataFetcher()

print("=================================================================")
print("  VALIDACIÓN CUANTITATIVA - MUESTRA HISTÓRICA AMPLIADA BITCOIN")
print("=================================================================\n")

# Run backtests for 1d, 4h, 1h on BTC/USDT with 2000 candles limit
for tf, candle_count in [("1d", 2000), ("4h", 2000), ("1h", 2000)]:
    try:
        print(f"--> Obteniendo {candle_count} velas históricas de BTC/USDT en temporalidad {tf}...")
        df = fetcher.fetch_ohlcv("BTC/USDT", tf, limit=candle_count)
        
        start_date = str(df['timestamp'].iloc[0]).split()[0]
        end_date = str(df['timestamp'].iloc[-1]).split()[0]
        start_price = df['close'].iloc[0]
        end_price = df['close'].iloc[-1]
        
        cfg = DEFAULT_CONFIG.copy()
        cfg["symbol"] = "BTC/USDT"
        cfg["timeframe"] = tf
        
        bt = Backtester(cfg)
        res = bt.run(df)
        s = res["summary"]
        
        print(f"Período evaluado: {start_date} a {end_date} ({len(df)} velas)")
        print(f"Precio inicial BTC: ${start_price:,.2f}  -->  Precio final BTC: ${end_price:,.2f}")
        print(f"Capital Inicial: ${s['initial_capital']:,.2f}")
        print(f"Balance Final Bot: ${s['final_balance']:,.2f}")
        print(f"Retorno Neto Bot: {s['total_return_pct']:+.2f}% (${s['total_net_pnl']:+,.2f})")
        print(f"Total Operaciones: {s['total_trades']} ({s['winning_trades']} Ganadas / {s['losing_trades']} Perdidas)")
        print(f"Win Rate %: {s['win_rate']:.2f}%")
        print(f"Profit Factor: {s['profit_factor']:.2f}")
        print(f"Drawdown Máximo: {s['max_drawdown']:.2f}%")
        print(f"Sharpe Ratio: {s['sharpe_ratio']:.2f}")
        print("-" * 65 + "\n")
    except Exception as e:
        print(f"Error procesando {tf}: {e}")
