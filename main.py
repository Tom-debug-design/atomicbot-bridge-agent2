import os, time, random, csv, requests
try:
    from binance.client import Client
except ImportError:
    Client = None

MODE = os.getenv("MODE", "backtest")  # "backtest" eller "live"
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")
TOKENS = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","ADAUSDT","DOGEUSDT","MATICUSDT","AVAXUSDT","LINKUSDT"]

START_BALANCE = 1000.0
balance = START_BALANCE
holdings = {symbol: 0.0 for symbol in TOKENS}
trade_log = []
auto_buy_pct = 0.1

# --- ML helpers (dummy) ---
def ai_pick_strategy(trade_log):
    # TODO: Decision Tree/ML/Trend! Nå: enkel statistikk
    recents = [t for t in trade_log[-30:] if t["action"] == "SELL"]
    if not recents: return random.choice(["RSI","EMA","RANDOM"])
    best = max(["RSI","EMA","RANDOM"], key=lambda s: sum(t["pnl"] for t in recents if t["strategy"]==s))
    return best

def send_discord(msg):
    print("DISCORD:", msg)
    try: requests.post(DISCORD_WEBHOOK, json={"content": msg})
    except: pass

def load_backtest_data(filename="backtest_data.csv"):
    data = []
    with open(filename, newline="") as f:
        for row in csv.DictReader(f):
            data.append(row)
    return data

def get_live_price(symbol):
    if not Client: return None
    try:
        c = Client(API_KEY, API_SECRET)
        ticker = c.get_symbol_ticker(symbol=symbol)
        return float(ticker["price"])
    except Exception as e:
        print("Binance price err:", e)
        return None

def get_price(symbol, idx, bt_data=None):
    if MODE == "backtest" and bt_data:
        return float(bt_data[idx % len(bt_data)][symbol])
    return get_live_price(symbol)

def choose_strategy(trade_log):
    if len(trade_log) > 10:
        return ai_pick_strategy(trade_log)
    return random.choice(["RSI", "EMA", "RANDOM"])

def get_signal(strategy, price, holdings):
    if price is None: return "HOLD"
    if strategy == "RSI":
        if price < 25 and holdings == 0: return "BUY"
        elif price > 60 and holdings > 0: return "SELL"
        else: return "HOLD"
    elif strategy == "EMA":
        if int(price) % 2 == 0 and holdings == 0: return "BUY"
        elif int(price) % 5 == 0 and holdings > 0: return "SELL"
        else: return "HOLD"
    else:
        return random.choice(["BUY", "SELL", "HOLD"])

def handle_trade(symbol, action, price, strategy):
    global balance, holdings, trade_log, auto_buy_pct
    if price is None: return
    amount_usd = balance * auto_buy_pct if action == "BUY" else holdings[symbol] * price
    qty = round(amount_usd / price, 6) if action == "BUY" else holdings[symbol]
    pnl = 0.0
    if action == "BUY" and balance >= amount_usd and qty > 0:
        balance -= amount_usd
        holdings[symbol] += qty
        send_discord(f"🔵 BUY {symbol}: {qty} at ${price:.2f}, new balance ${balance:.2f}")
        trade_log.append({"symbol": symbol, "action": "BUY", "price": price,
                          "qty": qty, "timestamp": time.time(), "strategy": strategy, "pnl": 0.0})
    elif action == "SELL" and holdings[symbol] > 0:
        proceeds = qty * price
        last_buy = next((t for t in reversed(trade_log) if t["symbol"] == symbol and t["action"] == "BUY"), None)
        pnl = ((price - last_buy["price"]) / last_buy["price"] * 100) if last_buy else 0.0
        balance += proceeds
        holdings[symbol] = 0.0
        send_discord(f"🔴 SELL {symbol}: {qty} at ${price:.2f}, PnL: {pnl:.2f}%, balance: ${balance:.2f}")
        trade_log.append({"symbol": symbol, "action": "SELL", "price": price,
                          "qty": qty, "timestamp": time.time(), "strategy": strategy, "pnl": pnl})

def hourly_report():
    total_trades = len(trade_log)
    realized_pnl = sum(t.get("pnl", 0) for t in trade_log if t["action"] == "SELL")
    msg = f"📊 Hourly Report: Trades: {total_trades}, Realized PnL: {realized_pnl:.2f}%, Balance: ${balance:.2f}"
    send_discord(msg)

def ai_feedback():
    best = ai_pick_strategy(trade_log)
    send_discord(f"🤖 AI: Best strategy last 30: {best}")

def auto_tune(trade_log):
    global auto_buy_pct
    recent = [t for t in trade_log[-10:] if t["action"] == "SELL"]
    pnl_sum = sum(t.get("pnl", 0) for t in recent)
    if recent and pnl_sum > 0 and auto_buy_pct < 0.25:
        auto_buy_pct += 0.01
        send_discord(f"🔧 AI auto-tuning: Øker buy% til {auto_buy_pct*100:.1f}")
    elif recent and pnl_sum < 0 and auto_buy_pct > 0.05:
        auto_buy_pct -= 0.01
        send_discord(f"🔧 AI auto-tuning: Senker buy% til {auto_buy_pct*100:.1f}")

send_discord(f"🟢 AtomicBot {MODE} starter…")

if MODE == "backtest":
    # --- Dummy backtestdata generator hvis ingen CSV finnes ---
    import pandas as pd
    import numpy as np
    if not os.path.exists("backtest_data.csv"):
        prices = {tok: np.abs(np.random.normal(50, 20, 5000)) for tok in TOKENS}
        df = pd.DataFrame(prices)
        df.to_csv("backtest_data.csv", index=False)
        print("Laget backtest_data.csv med 5000 rader for backtest!")
    bt_data = load_backtest_data()
else:
    bt_data = None

idx = 0
last_report = time.time()
while True:
    for symbol in TOKENS:
        price = get_price(symbol, idx, bt_data)
        strategy = choose_strategy(trade_log)
        action = get_signal(strategy, price, holdings[symbol])
        print(f"{symbol} | Pris: {price} | Strategy: {strategy} | Signal: {action}")
        if action in ("BUY", "SELL"):
            handle_trade(symbol, action, price, strategy)
    idx += 1
    # Rapporter hvert 60 sek
    if time.time() - last_report > 60:
        hourly_report()
        ai_feedback()
        auto_tune(trade_log)
        last_report = time.time()
    time.sleep(1 if MODE=="backtest" else 30)  # Backtest = rask loop, live = rolig loop
