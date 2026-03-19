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

# --- PARAMETRI QUANTISTICI ---
ALPHA = 0.00729735
MOLTIPLICATORE_QUANTUM = 2.618 
SOGLIA_NOTIFICA = 0.02
DISTANZA_INGRESSO = 0.006

# --- MAPPA ASSET COMPLETA ---
MAPPA_ASSET = {
    "EURUSD=X": {"mt5": "EURUSD", "cat": "💱 FOREX", "tv": "FX:EURUSD"},
    "GBPUSD=X": {"mt5": "GBPUSD", "cat": "💱 FOREX", "tv": "FX:GBPUSD"},
    "ES=F": {"mt5": "S&P500", "cat": "📈 INDICI", "tv": "SPX"},
    "NQ=F": {"mt5": "NAS100", "cat": "📈 INDICI", "tv": "NDX"},
    "^GDAXI": {"mt5": "GER40", "cat": "📈 INDICI", "tv": "DAX"},
    "FTSEMIB.MI": {"mt5": "ITA40", "cat": "📈 INDICI", "tv": "INDEX:FTSEMIB"},
    "GC=F": {"mt5": "GOLD", "cat": "⛏️ METALS", "tv": "GOLD"},
    "SI=F": {"mt5": "SILVER", "cat": "⛏️ METALS", "tv": "SILVER"},
    "CL=F": {"mt5": "CRUDE OIL", "cat": "🛢️ ENERGY", "tv": "USOIL"},
    "BTC-USD": {"mt5": "BTCUSD", "cat": "🌐 CRYPTO", "tv": "BTCUSD"},
    "ETH-USD": {"mt5": "ETHUSD", "cat": "🌐 CRYPTO", "tv": "ETHUSD"},
    # --- NUOVI ETF OPERATIVI ---
    "CSSPX.MI": {"mt5": "S&P500", "cat": "🇮🇹 ETF", "tv": "MIL:CSSPX"},
    "CNDX.MI":  {"mt5": "NAS100", "cat": "🇮🇹 ETF", "tv": "MIL:CNDX"},
    "DAX2ST.MI": {"mt5": "GER40", "cat": "🇮🇹 ETF", "tv": "MIL:DAX2ST"},
    "SGLD.MI": {"mt5": "GOLD", "cat": "⛏️ ETC", "tv": "MIL:SGLD"},
    "BTCE.MI": {"mt5": "BTCUSD", "cat": "🌐 ETP", "tv": "MIL:BTCE"}
}

# --- MAPPA CORRELAZIONI (ETF -> INDICE) ---
CORRELAZIONI = {
    "CSSPX.MI": "ES=F",
    "CNDX.MI": "NQ=F",
    "DAX2ST.MI": "^GDAXI",
    "SGLD.MI": "GC=F",
    "BTCE.MI": "BTC-USD"
}

# --- FUNZIONI TECNICHE ---
def calcola_atr(df, window=14):
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    return ranges.max(axis=1).rolling(window).mean().iloc[-1]

def pulisci_invalidati(ticker, prezzo_ora):
    try:
        res = supabase.table("segnali_trading").select("*").eq("ticker", ticker).eq("stato", "Pendente").execute()
        for rec in res.data:
            if (rec['fase'] == "Acc" and prezzo_ora <= rec['sl']) or (rec['fase'] == "Dist" and prezzo_ora >= rec['sl']):
                supabase.table("segnali_trading").update({"stato": "Invalidato"}).eq("id", rec['id']).execute()
    except: pass

def gestisci_tracking(ticker, fase, dist_attuale):
    try:
        limite = (datetime.now() - timedelta(hours=12)).isoformat()
        res = supabase.table("segnali_trading").select("*").eq("ticker", ticker).eq("fase", fase).gt("created_at", limite).execute()
        if not res.data: return True, False, None, 999.0
        record = res.data[0]
        dist_prec = record.get('distanza_minima_raggiunta', 999.0)
        if dist_attuale < (dist_prec - 0.001):
            supabase.table("segnali_trading").update({"distanza_minima_raggiunta": dist_attuale}).eq("id", record['id']).execute()
            return False, True, record['id'], dist_prec
        return False, False, record['id'], dist_prec
    except: return True, False, None, 999.0

def send_telegram(msg, img_path):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    try:
        with open(img_path, 'rb') as photo:
            requests.post(url, files={'photo': photo}, data={'chat_id': CHAT_ID, 'caption': msg, 'parse_mode': 'HTML'})
    except Exception as e: print(f"Errore Invio: {e}")

# --- ESECUZIONE ---
try:
    symbols = [line.strip() for line in open('tickers.txt', 'r') if line.strip() and not line.startswith('#')]
except: exit(1)

# Cache dei risultati per le correlazioni
cache_risultati = {}

for ticker in symbols:
    try:
        df = yf.download(ticker, period="4mo", interval="4h", progress=False, auto_adjust=True)
        if df.empty or len(df) < 137: continue
        df.columns = [str(c[0] if isinstance(c, tuple) else c).capitalize() for c in df.columns]
        
        prezzo_ora = df['Close'].iloc[-1]
        atr = calcola_atr(df)
        pulisci_invalidati(ticker, prezzo_ora)
        
        high_r, low_r = df['High'].rolling(137).max().iloc[-1], df['Low'].rolling(137).min().iloc[-1]
        range_h, mid_p = (high_r - low_r), (high_r + low_r) / 2.0
        is_acc = prezzo_ora < mid_p
        fase_attuale = "Acc" if is_acc else "Dist"
        
        p_livello = low_r - (range_h * ALPHA * MOLTIPLICATORE_QUANTUM) if is_acc else high_r + (range_h * ALPHA * MOLTIPLICATORE_QUANTUM)
        sl = p_livello - (atr * 1.5) if is_acc else p_livello + (atr * 1.5)
        tp = p_livello + (range_h * 1.37) if is_acc else p_livello - (range_h * 1.37)
        distanza = abs(prezzo_ora - p_livello) / p_livello
        
        cache_risultati[ticker] = {"prezzo": prezzo_ora, "distanza": distanza}

        if distanza < SOGLIA_NOTIFICA:
            is_nuovo, is_migliorato, rec_id, dist_old = gestisci_tracking(ticker, fase_attuale, distanza)
            
            if is_nuovo or is_migliorato:
                asset_info = MAPPA_ASSET.get(ticker, {"mt5": ticker, "cat": "📊 ALTRO", "tv": ticker})
                label = "🎯 <b>UPDATE</b>" if is_migliorato else ("🔴 <b>INGRESSO</b>" if distanza < DISTANZA_INGRESSO else "🟡 <b>AVVICINAMENTO</b>")
                
                # Plot
                plot_data = df.iloc[-50:]
                alines = dict(alines=[[(plot_data.index[0], p_livello), (plot_data.index[-1], p_livello)], 
                                      [(plot_data.index[0], tp), (plot_data.index[-1], tp)], 
                                      [(plot_data.index[0], sl), (plot_data.index[-1], sl)]], colors=['blue', 'green', 'red'], linestyle='-.')
                mpf.plot(plot_data, type='candle', style='charles', savefig='plot.png', alines=alines, title=f"{ticker} Quantum")
                
                # Controllo Correlazione
                msg_indice = ""
                indice_ref = CORRELAZIONI.get(ticker)
                if indice_ref in cache_risultati:
                    msg_indice = f"\n🔸 <b>INDICE:</b> {cache_risultati[indice_ref]['prezzo']:.2f} (Dist: {cache_risultati[indice_ref]['distanza']:.2%})"

                msg = (f"{asset_info['cat']} | {label}\n\n"
                       f"<b>Asset:</b> {ticker} (TV: <code>{asset_info['tv']}</code>)\n"
                       f"<b>Prezzo:</b> {prezzo_ora:.4f} (📍 {distanza:.2%}){msg_indice}\n\n"
                       f"🔵 <b>LIVELLO: {p_livello:.4f}</b>\n"
                       f"🟢 <b>TP: {tp:.4f}</b>\n"
                       f"🔴 <b>SL: {sl:.4f}</b>\n\n"
                       f"{'✅ <i>Vicinanza ottimale.</i>' if is_migliorato else ''}")
                
                send_telegram(msg, 'plot.png')
                if is_nuovo and supabase:
                    supabase.table("segnali_trading").insert({
                        "ticker": ticker, "prezzo_ingresso": float(p_livello), "tp": float(tp), "sl": float(sl), 
                        "fase": fase_attuale, "distanza_minima_raggiunta": float(distanza), "stato": "Pendente"
                    }).execute()
                    
    except Exception as e: print(f"Errore {ticker}: {e}")
