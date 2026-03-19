import yfinance as yf
import requests
import os
import mplfinance as mpf
import pandas as pd
import numpy as np
from supabase import create_client
from datetime import datetime, timedelta

# --- CONFIGURAZIONE AMBIENTE ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID') or os.environ.get('TELEGRAM_CHAT_ID')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

# --- PARAMETRI STRATEGIA ---
ALPHA = 0.00729735
MOLTIPLICATORE_QUANTUM = 2.618 
SOGLIA_NOTIFICA = 0.02
DISTANZA_INGRESSO = 0.006

# --- MAPPA ASSET COMPLETA ---
MAPPA_ASSET = {
    "^GSPC": {"mt5": "S&P500", "cat": "📈 INDICE USA", "tv": "SPX"},
    "^NDX":  {"mt5": "NAS100", "cat": "📈 INDICE TECH", "tv": "NDX"},
    "^DJI":  {"mt5": "DOW30", "cat": "📈 INDICE BLUECHIP", "tv": "DJI"},
    "^GDAXI": {"mt5": "GER40", "cat": "📈 INDICE DAX", "tv": "DAX"},
    "FTSEMIB.MI": {"mt5": "ITA40", "cat": "📈 INDICE MIB", "tv": "INDEX:FTSEMIB"},
    "^STOXX50E": {"mt5": "EU50", "cat": "📈 INDICE EUROPA", "tv": "SX5E"},
    "^FCHI": {"mt5": "FRA40", "cat": "📈 INDICE FRANCIA", "tv": "CAC40"},
    "GC=F": {"mt5": "GOLD", "cat": "⛏️ METALS", "tv": "GOLD"},
    "SI=F": {"mt5": "SILVER", "cat": "⛏️ METALS", "tv": "SILVER"},
    "HG=F": {"mt5": "COPPER", "cat": "⛏️ METALS", "tv": "COPPER"},
    "CL=F": {"mt5": "CRUDE OIL", "cat": "🛢️ ENERGY", "tv": "USOIL"},
    "NG=F": {"mt5": "NAT GAS", "cat": "🛢️ ENERGY", "tv": "NATGAS"},
    "BZ=F": {"mt5": "BRENT", "cat": "🛢️ ENERGY", "tv": "UKOIL"},
    "CSSPX.MI": {"mt5": "S&P500", "cat": "🇮🇹 ETF AZIONARI", "tv": "MIL:CSSPX"},
    "CNDX.MI":  {"mt5": "NAS100", "cat": "🇮🇹 ETF AZIONARI", "tv": "MIL:CNDX"},
    "DAX2ST.MI": {"mt5": "GER40", "cat": "🇮🇹 ETF AZIONARI", "tv": "MIL:DAX2ST"},
    "ETFMIB.MI": {"mt5": "ITA40", "cat": "🇮🇹 ETF AZIONARI", "tv": "MIL:ETFMIB"},
    "SWDA.MI": {"mt5": "WORLD", "cat": "🌍 ETF GLOBALI", "tv": "MIL:SWDA"},
    "SGLD.MI": {"mt5": "GOLD", "cat": "⛏️ ETC REALE", "tv": "MIL:SGLD"},
    "PHAG.MI": {"mt5": "SILVER", "cat": "⛏️ ETC REALE", "tv": "MIL:PHAG"},
    "BTCE.MI": {"mt5": "BTCUSD", "cat": "🌐 CRYPTO ETP", "tv": "MIL:BTCE"},
    "EURUSD=X": {"mt5": "EURUSD", "cat": "💱 FOREX", "tv": "FX:EURUSD"},
    "BTC-USD": {"mt5": "BTCUSD", "cat": "🌐 CRYPTO SPOT", "tv": "BTCUSD"}
}

CORRELAZIONI = {
    "CSSPX.MI": "^GSPC", "CNDX.MI": "^NDX", "DAX2ST.MI": "^GDAXI",
    "ETFMIB.MI": "FTSEMIB.MI", "SGLD.MI": "GC=F", "PHAG.MI": "SI=F",
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
    if not supabase: return
    try:
        # Usiamo 'sl' come da tua tabella
        res = supabase.table("segnali_trading").select("*").eq("ticker", ticker).eq("stato", "Pendente").execute()
        for rec in res.data:
            if (rec['fase'] == "Acc" and prezzo_ora <= rec['sl']) or (rec['fase'] == "Dist" and prezzo_ora >= rec['sl']):
                supabase.table("segnali_trading").update({"stato": "Invalidato"}).eq("id", rec['id']).execute()
    except: pass

def gestisci_tracking(ticker, fase, dist_attuale):
    if not supabase: return True, False, None, 999.0
    try:
        # Usiamo 'data_segnale' come da tua tabella
        limite = (datetime.now() - timedelta(hours=12)).isoformat()
        res = supabase.table("segnali_trading").select("*").eq("ticker", ticker).eq("fase", fase).gt("data_segnale", limite).execute()
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
    except: pass

# --- ESECUZIONE ---
def main():
    try:
        symbols = [line.strip() for line in open('tickers.txt', 'r') if line.strip() and not line.startswith('#')]
    except: return

    cache_risultati = {}

    for ticker in symbols:
        try:
            df = yf.download(ticker, period="3mo", interval="4h", progress=False, auto_adjust=True)
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
                    
                    # Generazione Grafico
                    plot_data = df.iloc[-60:]
                    alines = dict(alines=[[(plot_data.index[0], p_livello), (plot_data.index[-1], p_livello)], 
                                          [(plot_data.index[0], tp), (plot_data.index[-1], tp)], 
                                          [(plot_data.index[0], sl), (plot_data.index[-1], sl)]], 
                                  colors=['blue', 'green', 'red'], linestyle='-.')
                    mpf.plot(plot_data, type='candle', style='charles', savefig='plot.png', alines=alines, title=f"{ticker}")
                    
                    # Logica Combo
                    msg_indice = ""
                    indice_ref = CORRELAZIONI.get(ticker)
                    if indice_ref in cache_risultati:
                        d_ind = cache_risultati[indice_ref]
                        msg_indice = f"\n🔸 <b>INDICE:</b> {d_ind['prezzo']:.2f} (📍 {d_ind['distanza']:.2%})"

                    msg = (f"{asset_info['cat']} | {label}\n\n"
                           f"<b>Asset:</b> {ticker} (TV: <code>{asset_info['tv']}</code>)\n"
                           f"<b>Prezzo:</b> {prezzo_ora:.4f} (📍 {distanza:.2%}){msg_indice}\n\n"
                           f"🔵 <b>LIVELLO: {p_livello:.4f}</b>\n"
                           f"🟢 <b>TP: {tp:.4f}</b>\n"
                           f"🔴 <b>SL: {sl:.4f}</b>")
                    
                    send_telegram(msg, 'plot.png')
                    
                    if is_nuovo and supabase:
                        # Usiamo i nomi esatti della tua tabella
                        supabase.table("segnali_trading").insert({
                            "ticker": ticker, 
                            "prezzo_ingresso": float(p_livello), 
                            "tp": float(tp), 
                            "sl": float(sl), 
                            "fase": fase_attuale, 
                            "distanza_minima_raggiunta": float(distanza), 
                            "stato": "Pendente"
                        }).execute()
                        
        except Exception as e: print(f"Errore {ticker}: {e}")

if __name__ == "__main__":
    main()
