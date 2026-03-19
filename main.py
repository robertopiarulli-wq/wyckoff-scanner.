import yfinance as yf
import requests
import os
import mplfinance as mpf
import pandas as pd
import numpy as np
from supabase import create_client
from datetime import datetime

# --- CONFIGURAZIONE ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID') or os.environ.get('TELEGRAM_CHAT_ID')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

# --- PARAMETRI ---
ALPHA = 0.00729735
MOLTIPLICATORE_QUANTUM = 2.618 
SOGLIA_NOTIFICA = 0.02

MAPPA_ASSET = {
    "^GSPC": {"mt5": "S&P500", "cat": "📈 INDICE USA", "tv": "SPX"},
    "^NDX":  {"mt5": "NAS100", "cat": "📈 INDICE TECH", "tv": "NDX"},
    "^GDAXI": {"mt5": "GER40", "cat": "📈 INDICE DAX", "tv": "DAX"},
    "FTSEMIB.MI": {"mt5": "ITA40", "cat": "📈 INDICE MIB", "tv": "FTSEMIB"},
    "GC=F": {"mt5": "GOLD", "cat": "⛏️ METALS", "tv": "GC1!"},
    "CSSPX.MI": {"mt5": "S&P500", "cat": "🇮🇹 ETF USA", "tv": "MIL:CSSPX"},
    "ANX.MI": {"mt5": "NAS100", "cat": "🇮🇹 ETF TECH", "tv": "MIL:ANX"},
    "SGLD.MI": {"mt5": "GOLD", "cat": "⛏️ ETC ORO", "tv": "MIL:SGLD"},
    "BTCE.DE": {"mt5": "BTC", "cat": "🌐 CRYPTO", "tv": "XETR:BTCE"}
}

CORRELAZIONI = {"CSSPX.MI": "^GSPC", "ANX.MI": "^NDX", "SGLD.MI": "GC=F"}

def calcola_indicatori(df):
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    # Bollinger
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['StdDev'] = df['Close'].rolling(window=20).std()
    df['UpperB'] = df['MA20'] + (df['StdDev'] * 2)
    df['LowerB'] = df['MA20'] - (df['StdDev'] * 2)
    # ATR per SL
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    df['ATR'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()
    return df

def send_telegram(msg, img_path):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    try:
        with open(img_path, 'rb') as photo:
            requests.post(url, files={'photo': photo}, data={'chat_id': CHAT_ID, 'caption': msg, 'parse_mode': 'HTML'})
    except: pass

def main():
    try:
        symbols = [line.strip() for line in open('tickers.txt', 'r') if line.strip() and not line.startswith('#')]
    except: return
    cache = {}
    for ticker in symbols:
        try:
            df = yf.download(ticker, period="1mo", interval="1h", progress=False, auto_adjust=True)
            if df.empty or len(df) < 137: continue
            df.columns = [str(c[0] if isinstance(c, tuple) else c).capitalize() for c in df.columns]
            df = calcola_indicatori(df)
            prezzo = df['Close'].iloc[-1]
            high_r, low_r = df['High'].rolling(137).max().iloc[-1], df['Low'].rolling(137).min().iloc[-1]
            range_h = high_r - low_r
            mid_p = (high_r + low_r) / 2
            is_acc = prezzo < mid_p
            
            lvl = low_r - (range_h * ALPHA * MOLTIPLICATORE_QUANTUM) if is_acc else high_r + (range_h * ALPHA * MOLTIPLICATORE_QUANTUM)
            tp = lvl + (range_h * 1.37) if is_acc else lvl - (range_h * 1.37)
            sl = lvl - (df['ATR'].iloc[-1] * 1.5) if is_acc else lvl + (df['ATR'].iloc[-1] * 1.5)
            
            cache[ticker] = {
                "p": prezzo, "rsi": df['RSI'].iloc[-1], "dist": abs(prezzo - lvl)/lvl, "lvl": lvl, "tp": tp, "sl": sl,
                "fase": "ACCUMULAZIONE" if is_acc else "DISTRIBUZIONE",
                "trend": "RIBAZZISTA (Sotto Media)" if prezzo < mid_p else "RIALZISTA (Sopra Media)",
                "df": df
            }
        except: continue

    for ticker, d in cache.items():
        if d['dist'] < SOGLIA_NOTIFICA:
            asset = MAPPA_ASSET.get(ticker, {"cat": "📊 ASSET", "tv": ticker})
            ref = CORRELAZIONI.get(ticker)
            msg_idx = f"\n🔗 <b>INDICE ({ref}):</b> {cache[ref]['p']:.2f} (📍 {cache[ref]['dist']:.2%})" if ref in cache else ""
            
            tipo_ordine = "BUY LIMIT" if d['fase'] == "ACCUMULAZIONE" else "SELL LIMIT"
            istruzione = "COMPRARE su debolezza" if d['fase'] == "ACCUMULAZIONE" else "VENDERE su forza"
            
            msg = (f"{asset['cat']} | 🎯 <b>CECCHINO</b>\n\n"
                   f"<b>Asset:</b> {ticker}\n"
                   f"<b>Fase Wyckoff:</b> {d['fase']}\n"
                   f"<b>Trend Attuale:</b> {d['trend']}\n"
                   f"<b>Prezzo:</b> {d['p']:.4f} (📍 {d['dist']:.2%}){msg_idx}\n\n"
                   f"⚙️ <b>OPERATIVITÀ CONTRARIAN:</b>\n"
                   f"Tipo: <code>{tipo_ordine}</code> ({istruzione})\n"
                   f"🔵 <b>ENTRY: {d['lvl']:.4f}</b>\n"
                   f"🟢 <b>TP: {d['tp']:.4f}</b>\n"
                   f"🔴 <b>SL: {d['sl']:.4f}</b>\n\n"
                   f"🛡️ <b>CONFERME RSI:</b> {'✅' if (d['rsi']<40 or d['rsi']>60) else '⚠️'} ({d['rsi']:.1f})")

            plot_data = d['df'].iloc[-50:]
            ap = [mpf.make_addplot(plot_data['UpperB'], color='gray', width=0.8),
                  mpf.make_addplot(plot_data['LowerB'], color='gray', width=0.8)]
            mpf.plot(plot_data, type='candle', style='charles', addplot=ap, savefig='plot.png', 
                     hlines=dict(hlines=[d['lvl'], d['tp'], d['sl']], colors=['blue', 'green', 'red'], linestyle='-.'))
            send_telegram(msg, 'plot.png')

if __name__ == "__main__":
    main()
