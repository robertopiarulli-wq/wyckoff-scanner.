import yfinance as yf
import requests
import os
import mplfinance as mpf
import time
import pandas as pd
import numpy as np
from supabase import create_client
from datetime import datetime, timedelta

# --- CONFIGURAZIONE ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- PARAMETRI QUANTISTICI ---
ALPHA = 0.00729735
MOLTIPLICATORE_QUANTUM = 2.618 
SOGLIA_NOTIFICA = 0.02
DISTANZA_INGRESSO = 0.006

# --- MAPPA ASSET (Tieni ^GDAXI con l'accento!) ---
MAPPA_ASSET = {
    "EURUSD=X": {"mt5": "EURUSD", "cat": "💱 FOREX"},
    "GBPUSD=X": {"mt5": "GBPUSD", "cat": "💱 FOREX"},
    "USDJPY=X": {"mt5": "USDJPY", "cat": "💱 FOREX"},
    "AUDUSD=X": {"mt5": "AUDUSD", "cat": "💱 FOREX"},
    "USDCAD=X": {"mt5": "USDCAD", "cat": "💱 FOREX"},
    "USDCHF=X": {"mt5": "USDCHF", "cat": "💱 FOREX"},
    "NZDUSD=X": {"mt5": "NZDUSD", "cat": "💱 FOREX"},
    "EURJPY=X": {"mt5": "EURJPY", "cat": "💱 FOREX"},
    "GBPJPY=X": {"mt5": "GBPJPY", "cat": "💱 FOREX"},
    "AUDJPY=X": {"mt5": "AUDJPY", "cat": "💱 FOREX"},
    "ES=F": {"mt5": "S&P500", "cat": "📈 INDICI"},
    "NQ=F": {"mt5": "NAS100", "cat": "📈 INDICI"},
    "YM=F": {"mt5": "US30", "cat": "📈 INDICI"},
    "RTY=F": {"mt5": "RUSSELL2000", "cat": "📈 INDICI"},
    "^GDAXI": {"mt5": "GER40", "cat": "📈 INDICI"},
    "GC=F": {"mt5": "GOLD", "cat": "⛏️ METALS"},
    "SI=F": {"mt5": "SILVER", "cat": "⛏️ METALS"},
    "HG=F": {"mt5": "COPPER", "cat": "⛏️ METALS"},
    "CL=F": {"mt5": "CRUDE OIL", "cat": "🛢️ ENERGY"},
    "NG=F": {"mt5": "NAT GAS", "cat": "🛢️ ENERGY"},
    "BTC-USD": {"mt5": "BTCUSD", "cat": "🌐 CRYPTO"},
    "ETH-USD": {"mt5": "ETHUSD", "cat": "🌐 CRYPTO"},
    "SOL-USD": {"mt5": "SOLUSD", "cat": "🌐 CRYPTO"},
    "CT=F": {"mt5": "COTTON", "cat": "🌾 COMMODITIES"}
}

# --- FUNZIONI TECNICHE ---
def calcola_atr(df, window=14):
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(window).mean().iloc[-1]

def get_info_asset(ticker):
    return MAPPA_ASSET.get(ticker, {"mt5": ticker, "cat": "📊 ALTRO"})

def pulisci_invalidati(ticker, prezzo_ora):
    try:
        res = supabase.table("segnali_trading").select("*").eq("ticker", ticker).eq("stato", "Pendente").execute()
        for rec in res.data:
            fase, sl, id_rec = rec['fase'], rec['sl'], rec['id']
            if (fase == "Acc" and prezzo_ora <= sl) or (fase == "Dist" and prezzo_ora >= sl):
                supabase.table("segnali_trading").update({"stato": "Invalidato"}).eq("id", id_rec).execute()
                print(f"--- [INVALIDATO] {ticker}: SL toccato prima del livello. ---")
    except: pass

def gestisci_tracking(ticker, fase, dist_attuale):
    try:
        limite = (datetime.now() - timedelta(hours=12)).isoformat()
        res = supabase.table("segnali_trading").select("*").eq("ticker", ticker).eq("fase", fase).gt("data_segnale", limite).execute()
        if not res.data: return True, False, None, None
        record = res.data[0]
        dist_prec = record.get('distanza_minima_raggiunta', 999.0)
        if dist_attuale < (dist_prec - 0.001):
            supabase.table("segnali_trading").update({"distanza_minima_raggiunta": dist_attuale}).eq("id", record['id']).execute()
            return False, True, record['id'], dist_prec
        return False, False, record['id'], dist_prec
    except: return False, False, None, None

def send_telegram(msg, img_path):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    try:
        with open(img_path, 'rb') as photo:
            requests.post(url, files={'photo': photo}, data={'chat_id': CHAT_ID, 'caption': msg, 'parse_mode': 'HTML'})
    except: pass

# --- ESECUZIONE ---
try:
    symbols = [line.strip() for line in open('tickers.txt', 'r') if line.strip() and not line.startswith('#')]
except: exit(1)

for ticker in symbols:
    try:
        df = yf.download(ticker, period="3mo", interval="4h", progress=False, auto_adjust=True)
        if df.empty or len(df) < 137: continue
        df.columns = [str(c[0] if isinstance(c, tuple) else c).capitalize() for c in df.columns]
        
        prezzo_ora = df['Close'].iloc[-1]
        atr = calcola_atr(df)
        
        # 1. Pulisce setup falliti
        pulisci_invalidati(ticker, prezzo_ora)
        
        # 2. Calcolo Livelli Wyckoff-Quantum
        high_r, low_r = df['High'].rolling(137).max().iloc[-1], df['Low'].rolling(137).min().iloc[-1]
        range_h = high_r - low_r
        mid_p = (high_r + low_r) / 2.0
        is_acc = prezzo_ora < mid_p
        fase_attuale = "Acc" if is_acc else "Dist"
        
        p_livello = low_r - (range_h * ALPHA * MOLTIPLICATORE_QUANTUM) if is_acc else high_r + (range_h * ALPHA * MOLTIPLICATORE_QUANTUM)
        
        # SL DINAMICO: 1.5 * ATR (Molto più sicuro)
        distanza_sl = atr * 1.5
        sl = p_livello - distanza_sl if is_acc else p_livello + distanza_sl
        tp = p_livello + (range_h * 1.37) if is_acc else p_livello - (range_h * 1.37)
        
        distanza = abs(prezzo_ora - p_livello) / p_livello
        
        if distanza < SOGLIA_NOTIFICA:
            is_nuovo, is_migliorato, rec_id, dist_old = gestisci_tracking(ticker, fase_attuale, distanza)
            
            if is_nuovo or is_migliorato:
                asset_info = get_info_asset(ticker)
                label = "🎯 <b>UPDATE: AVVICINAMENTO</b>" if is_migliorato else ("🔴 <b>INGRESSO</b>" if distanza < DISTANZA_INGRESSO else "🟡 <b>AVVICINAMENTO</b>")
                info_dist = f"<b>{distanza:.2%}</b>" + (f" (Era {dist_old:.2%})" if is_migliorato else "")

                # Plot
                plot_data = df.iloc[-50:]
                alines = dict(alines=[[(plot_data.index[0], p_livello), (plot_data.index[-1], p_livello)], 
                                      [(plot_data.index[0], tp), (plot_data.index[-1], tp)],             
                                      [(plot_data.index[0], sl), (plot_data.index[-1], sl)]], colors=['blue', 'green', 'red'], linestyle='-.')
                mpf.plot(plot_data, type='candle', style='charles', savefig='plot.png', alines=alines)
                
                msg = (f"{asset_info['cat']}\n{label}\n\n"
                       f"<b>MT5:</b> <code>{asset_info['mt5']}</code>\n"
                       f"<b>Prezzo:</b> {prezzo_ora:.4f}\n\n"
                       f"🔵 <b>LIVELLO: {p_livello:.4f}</b>\n"
                       f"📍 Distanza: {info_dist}\n\n"
                       f"🟢 <b>TP: {tp:.4f}</b>\n"
                       f"🔴 <b>SL: {sl:.4f}</b> (Dinamico ATR)\n\n"
                       f"{'✅ <i>Vicinanza ottimale per inserimento.</i>' if is_migliorato else ''}")
                
                send_telegram(msg, 'plot.png')
                if is_nuovo:
                    supabase.table("segnali_trading").insert({"ticker": ticker, "prezzo_ingresso": float(p_livello), "tp": float(tp), "sl": float(sl), "fase": fase_attuale, "distanza_minima_raggiunta": float(distanza), "stato": "Pendente"}).execute()
                    
    except Exception as e: print(f"Errore {ticker}: {e}")
