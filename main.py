import yfinance as yf
import requests
import os
import mplfinance as mpf
import time
import numpy as np
import pandas as pd
from supabase import create_client
from datetime import datetime, timedelta

# --- CONFIGURAZIONE ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- PARAMETRI RITARATI ---
ALPHA = 0.00729735
MOLTIPLICATORE_QUANTUM = 2.618  # Ridotto da 3.0 per intercettare inversioni anticipate
SOGLIA_NOTIFICA = 0.02         # Alzata al 2% per monitoraggio preventivo
DISTANZA_INGRESSO = 0.006      # Soglia per definire lo stato "INGRESSO"

# --- MAPPATURA ASSET ---
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
    "DAX=F": {"mt5": "GER40", "cat": "📈 INDICI"},
    "^GDAXI": {"mt5": "GER40", "cat": "📈 INDICI"},
    "GC=F": {"mt5": "GOLD (XAUUSD)", "cat": "⛏️ METALS"},
    "SI=F": {"mt5": "SILVER (XAGUSD)", "cat": "⛏️ METALS"},
    "HG=F": {"mt5": "COPPER", "cat": "⛏️ METALS"},
    "PL=F": {"mt5": "PLATINUM", "cat": "⛏️ METALS"},
    "CL=F": {"mt5": "CRUDE OIL", "cat": "🛢️ ENERGY"},
    "NG=F": {"mt5": "NAT GAS", "cat": "🛢️ ENERGY"},
    "BTC-USD": {"mt5": "BTCUSD", "cat": "🌐 CRYPTO"},
    "ETH-USD": {"mt5": "ETHUSD", "cat": "🌐 CRYPTO"},
    "SOL-USD": {"mt5": "SOLUSD", "cat": "🌐 CRYPTO"},
    "ADA-USD": {"mt5": "ADAUSD", "cat": "🌐 CRYPTO"},
    "XRP-USD": {"mt5": "XRPUSD", "cat": "🌐 CRYPTO"},
    "DOT-USD": {"mt5": "DOTUSD", "cat": "🌐 CRYPTO"}
}

def get_info_asset(ticker):
    info = MAPPA_ASSET.get(ticker, {"mt5": ticker, "cat": "📊 ALTRO"})
    return info["cat"], info["mt5"]

def is_duplicato(ticker, fase):
    try:
        limite_tempo = (datetime.now() - timedelta(hours=12)).isoformat()
        res = supabase.table("segnali_trading").select("id").eq("ticker", ticker).eq("fase", fase).gt("data_segnale", limite_tempo).execute()
        return len(res.data) > 0
    except: return False

def send_telegram(msg, img_path):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    try:
        with open(img_path, 'rb') as photo:
            requests.post(url, files={'photo': photo}, data={'chat_id': CHAT_ID, 'caption': msg, 'parse_mode': 'HTML'})
    except Exception as e: print(f"Errore Telegram: {e}")

# --- ANALISI ---
symbols = [line.strip() for line in open('tickers.txt', 'r') if line.strip() and not line.startswith('#')]

for ticker in symbols:
    try:
        df = yf.download(ticker, period="3mo", interval="4h", progress=False, auto_adjust=True)
        if df.empty or len(df) < 137: continue
        
        df.columns = [str(c[0] if isinstance(c, tuple) else c).capitalize() for c in df.columns]
        
        high_r, low_r = df['High'].rolling(137).max().iloc[-1], df['Low'].rolling(137).min().iloc[-1]
        range_h, mid_p = high_r - low_r, (high_r + low_r) / 2.0
        is_acc = df['Close'].iloc[-1] < mid_p
        fase_attuale = "Acc" if is_acc else "Dist"
        
        # CALCOLO RITARATO
        p_livello = low_r - (range_h * ALPHA * MOLTIPLICATORE_QUANTUM) if is_acc else high_r + (range_h * ALPHA * MOLTIPLICATORE_QUANTUM)
        sl = p_livello - (p_livello * ALPHA * 1.5) if is_acc else p_livello + (p_livello * ALPHA * 1.5)
        tp = p_livello + (range_h * 1.37) if is_acc else p_livello - (range_h * 1.37)
        
        prezzo_chiusura = df['Close'].iloc[-1]
        distanza = abs(prezzo_chiusura - p_livello) / p_livello
        
        if distanza < SOGLIA_NOTIFICA:
            if is_duplicato(ticker, fase_attuale): continue
            
            cat, mt5_sym = get_info_asset(ticker)
            stato = "🔴 <b>INGRESSO</b>" if distanza < DISTANZA_INGRESSO else "🟡 <b>AVVICINAMENTO</b>"
            
            # Grafico
            plot_data = df.iloc[-50:]
            alines = dict(alines=[[(plot_data.index[0], p_livello), (plot_data.index[-1], p_livello)], 
                                  [(plot_data.index[0], tp), (plot_data.index[-1], tp)],             
                                  [(plot_data.index[0], sl), (plot_data.index[-1], sl)]], 
                          colors=['blue', 'green', 'red'], linestyle='-.')
            mpf.plot(plot_data, type='candle', style='charles', savefig='plot.png', alines=alines)
            
            msg = (f"{cat}\n"
                   f"{stato}\n\n"
                   f"<b>Ticker Yahoo:</b> {ticker}\n"
                   f"<b>Simbolo MT5:</b> <code>{mt5_sym}</code>\n"
                   f"<b>Fase:</b> {'Accumulazione' if is_acc else 'Distribuzione'}\n"
                   f"<b>Prezzo Attuale:</b> {prezzo_chiusura:.4f}\n\n"
                   f"🔵 <b>LIVELLO QUANTICO: {p_livello:.4f}</b>\n"
                   f"🟢 TARGET PROFIT: {tp:.4f}\n"
                   f"🔴 STOP LOSS: {sl:.4f}\n\n"
                   f"<i>Distanza dal livello: {distanza:.2%}</i>")
            
            send_telegram(msg, 'plot.png')
            supabase.table("segnali_trading").insert({"ticker": ticker, "prezzo_ingresso": float(p_livello), "tp": float(tp), "sl": float(sl), "fase": fase_attuale}).execute()
            time.sleep(2)
            
    except Exception as e: print(f"Errore su {ticker}: {e}")
