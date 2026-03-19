import yfinance as yf
import requests
import os
import mplfinance as mpf
import pandas as pd
import numpy as np
from supabase import create_client
from datetime import datetime, timedelta

# --- CONFIGURAZIONE ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID') or os.environ.get('TELEGRAM_CHAT_ID')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

# --- PARAMETRI QUANTUM ---
ALPHA = 0.00729735
MOLTIPLICATORE_QUANTUM = 2.618 
SOGLIA_NOTIFICA = 0.02
DISTANZA_INGRESSO = 0.006

MAPPA_ASSET = {
    "^GSPC": {"mt5": "S&P500", "cat": "📈 INDICE USA", "tv": "SPX"},
    "^NDX":  {"mt5": "NAS100", "cat": "📈 INDICE TECH", "tv": "NDX"},
    "^GDAXI": {"mt5": "GER40", "cat": "📈 INDICE DAX", "tv": "DAX"},
    "FTSEMIB.MI": {"mt5": "ITA40", "cat": "📈 INDICE MIB", "tv": "FTSEMIB"},
    "GC=F": {"mt5": "GOLD", "cat": "⛏️ METALS", "tv": "GC1!"},
    "SI=F": {"mt5": "SILVER", "cat": "⛏️ METALS", "tv": "SI1!"},
    "CL=F": {"mt5": "OIL", "cat": "🛢️ ENERGY", "tv": "CL1!"},
    "CSSPX.MI": {"mt5": "S&P500", "cat": "🇮🇹 ETF USA", "tv": "MIL:CSSPX"},
    "ANX.MI": {"mt5": "NAS100", "cat": "🇮🇹 ETF TECH", "tv": "MIL:ANX"},
    "SGLD.MI": {"mt5": "GOLD", "cat": "⛏️ ETC ORO", "tv": "MIL:SGLD"},
    "PHAG.MI": {"mt5": "SILVER", "cat": "⛏️ ETC ARGENTO", "tv": "MIL:PHAG"},
    "BTCE.DE": {"mt5": "BTC", "cat": "🌐 CRYPTO", "tv": "XETR:BTCE"},
    "ETH-USD": {"mt5": "ETH", "cat": "🌐 CRYPTO", "tv": "ETHUSD"},
    "IK00.MI": {"mt5": "BTP", "cat": "🏦 BOND ITA", "tv": "MIL:IK00"},
    "EURUSD=X": {"mt5": "EURUSD", "cat": "💱 FOREX", "tv": "EURUSD"}
}

CORRELAZIONI = {
    "CSSPX.MI": "^GSPC", "ANX.MI": "^NDX", "DAX2ST.MI": "^GDAXI",
    "ETFMIB.MI": "FTSEMIB.MI", "SGLD.MI": "GC=F", "PHAG.MI": "SI=F",
    "BTCE.DE": "BTC-USD", "IK00.MI": "FTSEMIB.MI"
}

# --- FUNZIONI ---
def calcola_atr(df, window=14):
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    return ranges.max(axis=1).rolling(window).mean().iloc[-1]

def send_telegram(msg, img_path):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    try:
        with open(img_path, 'rb') as photo:
            requests.post(url, files={'photo': photo}, data={'chat_id': CHAT_ID, 'caption': msg, 'parse_mode': 'HTML'})
    except Exception as e: print(f"Errore invio: {e}")

# --- CORE ---
def main():
    try:
        symbols = [line.strip() for line in open('tickers.txt', 'r') if line.strip() and not line.startswith('#')]
    except: return

    cache_risultati = {}
    segnali_da_inviare = []

    # 1. Fase di Scansione e Cache
    for ticker in symbols:
        try:
            df = yf.download(ticker, period="1mo", interval="1h", progress=False, auto_adjust=True)
            if df.empty or len(df) < 137: continue
            df.columns = [str(c[0] if isinstance(c, tuple) else c).capitalize() for c in df.columns]
            
            prezzo_ora = df['Close'].iloc[-1]
            high_r, low_r = df['High'].rolling(137).max().iloc[-1], df['Low'].rolling(137).min().iloc[-1]
            range_h, mid_p = (high_r - low_r), (high_r + low_r) / 2.0
            is_acc = prezzo_ora < mid_p
            
            p_livello = low_r - (range_h * ALPHA * MOLTIPLICATORE_QUANTUM) if is_acc else high_r + (range_h * ALPHA * MOLTIPLICATORE_QUANTUM)
            distanza = abs(prezzo_ora - p_livello) / p_livello
            
            # Salviamo in cache per la combo
            cache_risultati[ticker] = {
                "prezzo": prezzo_ora, 
                "distanza": distanza, 
                "livello": p_livello,
                "fase": "Acc" if is_acc else "Dist",
                "df": df,
                "atr": calcola_atr(df)
            }
            
            if distanza < SOGLIA_NOTIFICA:
                segnali_da_inviare.append(ticker)
                
        except Exception as e: print(f"Errore scansione {ticker}: {e}")

    # 2. Fase di Notifica con Logica Combo
    for ticker in segnali_da_inviare:
        try:
            d = cache_risultati[ticker]
            asset_info = MAPPA_ASSET.get(ticker, {"mt5": ticker, "cat": "📊 ASSET", "tv": ticker})
            
            # Calcolo livelli operativi
            tp = d['livello'] + ((d['df']['High'].rolling(137).max().iloc[-1] - d['df']['Low'].rolling(137).min().iloc[-1]) * 1.37) if d['fase'] == "Acc" else d['livello'] - ((d['df']['High'].rolling(137).max().iloc[-1] - d['df']['Low'].rolling(137).min().iloc[-1]) * 1.37)
            sl = d['livello'] - (d['atr'] * 1.5) if d['fase'] == "Acc" else d['livello'] + (d['atr'] * 1.5)

            # Costruzione Messaggio Combo
            msg_indice = ""
            ref = CORRELAZIONI.get(ticker)
            if ref and ref in cache_risultati:
                inf_ref = cache_risultati[ref]
                msg_indice = f"\n\n🔗 <b>COMPARAZIONE INDICE ({ref}):</b>\nPrezzo: {inf_ref['prezzo']:.2f}\n📍 Distanza Livello: {inf_ref['distanza']:.2%}"

            label = "🔴 <b>INGRESSO</b>" if d['distanza'] < DISTANZA_INGRESSO else "🟡 <b>AVVICINAMENTO</b>"
            msg = (f"{asset_info['cat']} | {label}\n\n"
                   f"<b>Asset:</b> {ticker} (TV: <code>{asset_info['tv']}</code>)\n"
                   f"<b>Prezzo:</b> {d['prezzo']:.4f} (📍 {d['distanza']:.2%}){msg_indice}\n\n"
                   f"🔵 <b>ENTRY: {d['livello']:.4f}</b>\n"
                   f"🟢 <b>TP: {tp:.4f}</b>\n"
                   f"🔴 <b>SL: {sl:.4f}</b>")

            # Grafico
            plot_data = d['df'].iloc[-60:]
            alines = dict(alines=[[(plot_data.index[0], d['livello']), (plot_data.index[-1], d['livello'])],
                                  [(plot_data.index[0], tp), (plot_data.index[-1], tp)],
                                  [(plot_data.index[0], sl), (plot_data.index[-1], sl)]],
                          colors=['blue', 'green', 'red'], linestyle='-.')
            mpf.plot(plot_data, type='candle', style='charles', savefig='plot.png', alines=alines, title=f"{ticker} (1h)")
            
            send_telegram(msg, 'plot.png')
            
            # Database
            if supabase:
                supabase.table("segnali_trading").insert({
                    "ticker": ticker, "prezzo_ingresso": float(d['livello']), "tp": float(tp), "sl": float(sl),
                    "fase": d['fase'], "distanza_minima_raggiunta": float(d['distanza']), "stato": "Pendente"
                }).execute()

        except Exception as e: print(f"Errore notifica {ticker}: {e}")

if __name__ == "__main__":
    main()
