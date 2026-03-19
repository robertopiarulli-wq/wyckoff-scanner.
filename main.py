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
SOGLIA_NOTIFICA = 0.018 # Leggermente più stretto per il cecchino

MAPPA_ASSET = {
    "^GSPC": {"mt5": "S&P500", "cat": "📈 INDICE USA", "tv": "SPX"},
    "^NDX":  {"mt5": "NAS100", "cat": "📈 INDICE TECH", "tv": "NDX"},
    "^GDAXI": {"mt5": "GER40", "cat": "📈 INDICE DAX", "tv": "DAX"},
    "FTSEMIB.MI": {"mt5": "ITA40", "cat": "📈 INDICE MIB", "tv": "FTSEMIB"},
    "GC=F": {"mt5": "GOLD", "cat": "⛏️ METALS", "tv": "GC1!"},
    "CSSPX.MI": {"mt5": "S&P500", "cat": "🇮🇹 ETF USA", "tv": "MIL:CSSPX"},
    "ANX.MI": {"mt5": "NAS100", "cat": "🇮🇹 ETF TECH", "tv": "MIL:ANX"},
    "SGLD.MI": {"mt5": "GOLD", "cat": "⛏️ ETC ORO", "tv": "MIL:SGLD"},
    "BTCE.DE": {"mt5": "BTC", "cat": "🌐 CRYPTO", "tv": "XETR:BTCE"},
    "ETH-USD": {"mt5": "ETH", "cat": "🌐 CRYPTO", "tv": "ETHUSD"}
}

CORRELAZIONI = {
    "CSSPX.MI": "^GSPC", "ANX.MI": "^NDX", "SGLD.MI": "GC=F", "BTCE.DE": "BTC-USD"
}

# --- FUNZIONI TECNICHE CECCHINO ---
def calcola_indicatori(df):
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Bollinger Bands
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['StdDev'] = df['Close'].rolling(window=20).std()
    df['UpperB'] = df['MA20'] + (df['StdDev'] * 2)
    df['LowerB'] = df['MA20'] - (df['StdDev'] * 2)
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
    
    # 1. Scansione e Analisi Tecnica
    for ticker in symbols:
        try:
            df = yf.download(ticker, period="1mo", interval="1h", progress=False, auto_adjust=True)
            if df.empty or len(df) < 137: continue
            df.columns = [str(c[0] if isinstance(c, tuple) else c).capitalize() for c in df.columns]
            df = calcola_indicatori(df)
            
            prezzo = df['Close'].iloc[-1]
            rsi = df['RSI'].iloc[-1]
            high_r, low_r = df['High'].rolling(137).max().iloc[-1], df['Low'].rolling(137).min().iloc[-1]
            range_h = high_r - low_r
            is_acc = prezzo < (high_r + low_r) / 2
            
            livello = low_r - (range_h * ALPHA * MOLTIPLICATORE_QUANTUM) if is_acc else high_r + (range_h * ALPHA * MOLTIPLICATORE_QUANTUM)
            distanza = abs(prezzo - livello) / livello
            
            cache[ticker] = {
                "prezzo": prezzo, "rsi": rsi, "dist": distanza, "lvl": livello,
                "fase": "Acc" if is_acc else "Dist", "df": df,
                "upB": df['UpperB'].iloc[-1], "loB": df['LowerB'].iloc[-1]
            }
        except: continue

    # 2. Notifica Cecchino
    for ticker, d in cache.items():
        if d['dist'] < SOGLIA_NOTIFICA:
            # Filtri Cecchino
            conf_rsi = (d['fase'] == "Acc" and d['rsi'] < 40) or (d['fase'] == "Dist" and d['rsi'] > 60)
            conf_bb = (d['fase'] == "Acc" and d['prezzo'] < d['df']['MA20'].iloc[-1]) or (d['fase'] == "Dist" and d['prezzo'] > d['df']['MA20'].iloc[-1])
            
            # Se nessuna conferma è attiva e la distanza non è "critica", salta (Il Cecchino riposa)
            if not conf_rsi and d['dist'] > 0.005: continue 

            asset_info = MAPPA_ASSET.get(ticker, {"cat": "📊 ASSET", "tv": ticker})
            ref = CORRELAZIONI.get(ticker)
            msg_idx = f"\n🔗 <b>INDICE ({ref}):</b> {cache[ref]['prezzo']:.2f} (📍 {cache[ref]['dist']:.2%})" if ref in cache else ""

            # UI Messaggio
            rsi_icon = "✅" if conf_rsi else "⚠️"
            bb_icon = "✅" if conf_bb else "⚠️"
            
            msg = (f"{asset_info['cat']} | 🎯 <b>MODALITÀ CECCHINO</b>\n\n"
                   f"<b>Asset:</b> {ticker}\n"
                   f"<b>Prezzo:</b> {d['prezzo']:.4f} (📍 {d['dist']:.2%}){msg_idx}\n\n"
                   f"🛡️ <b>CONFERME TECNICHE:</b>\n"
                   f"{rsi_icon} RSI: {d['rsi']:.1f}\n"
                   f"{bb_icon} Posizione Bande: OK\n\n"
                   f"🔵 <b>LIVELLO: {d['lvl']:.4f}</b>")

            # Grafico con Bande di Bollinger
            plot_data = d['df'].iloc[-50:]
            add_plots = [
                mpf.make_addplot(plot_data['UpperB'], color='gray', width=0.7),
                mpf.make_addplot(plot_data['LowerB'], color='gray', width=0.7)
            ]
            mpf.plot(plot_data, type='candle', style='charles', addplot=add_plots, savefig='plot.png', 
                     hlines=dict(hlines=[d['lvl']], colors=['blue'], linestyle='-.'))
            
            send_telegram(msg, 'plot.png')

if __name__ == "__main__":
    main()
