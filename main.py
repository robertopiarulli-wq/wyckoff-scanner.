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
ALPHA = 0.00729735

# --- MAPPATURA CATEGORIE E MT5 ---
# Aggiungi qui i tuoi ticker se ne mancano
MAPPA_ASSET = {
    # FOREX
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
    # INDICI
    "ES=F": {"mt5": "S&P500", "cat": "📈 INDICI"},
    "NQ=F": {"mt5": "NAS100", "cat": "📈 INDICI"},
    "YM=F": {"mt5": "US30", "cat": "📈 INDICI"},
    "RTY=F": {"mt5": "RUSSELL2000", "cat": "📈 INDICI"},
    "DAX=F": {"mt5": "GER40", "cat": "📈 INDICI"},
    "^GDAXI": {"mt5": "GER40", "cat": "📈 INDICI"},
    # COMMODITIES
    "GC=F": {"mt5": "GOLD (XAUUSD)", "cat": "⛏️ METALS"},
    "SI=F": {"mt5": "SILVER (XAGUSD)", "cat": "⛏️ METALS"},
    "HG=F": {"mt5": "COPPER", "cat": "⛏️ METALS"},
    "PL=F": {"mt5": "PLATINUM", "cat": "⛏️ METALS"},
    "CL=F": {"mt5": "CRUDE OIL", "cat": "🛢️ ENERGY"},
    "NG=F": {"mt5": "NAT GAS", "cat": "🛢️ ENERGY"},
    # CRYPTO
    "BTC-USD": {"mt5": "BTCUSD", "cat": "🌐 CRYPTO"},
    "ETH-USD": {"mt5": "ETHUSD", "cat": "🌐 CRYPTO"},
    "SOL-USD": {"mt5": "SOLUSD", "cat": "🌐 CRYPTO"},
    "ADA-USD": {"mt5": "ADAUSD", "cat": "🌐 CRYPTO"},
    "XRP-USD": {"mt5": "XRPUSD", "cat": "🌐 CRYPTO"}
}

def get_info_asset(ticker):
    # Ritorna categoria e simbolo MT5, se non trova usa valori di default
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

# --- LOGICA CORE ---
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
        
        p_livello = low_r - (range_h * ALPHA * 3.0) if is_acc else high_r + (range_h * ALPHA * 3.0)
        sl = p_livello - (p_livello * ALPHA) if is_acc else p_livello + (p_livello * ALPHA)
        tp = p_livello + (range_h * 1.37) if is_acc else p_livello - (range_h * 1.37)
        
        distanza = abs(df['Close'].iloc[-1] - p_livello) / p_livello
        
        if distanza < 0.015:
            if is_duplicato(ticker, fase_attuale): continue
            
            cat, mt5_sym = get_info_asset(ticker)
            stato = "🔴 <b>INGRESSO</b>" if distanza < 0.005 else "🟡 <b>AVVICINAMENTO</b>"
            
            # Grafico
            plot_data = df.iloc[-50:]
            alines = dict(alines=[[(plot_data.index[0], p_livello), (plot_data.index[-1], p_livello)], 
                                  [(plot_data.index[0], tp), (plot_data.index[-1], tp)],             
                                  [(plot_data.index[0], sl), (plot_data.index[-1], sl)]], 
                          colors=['blue', 'green', 'red'], linestyle='-.')
            mpf.plot(plot_data, type='candle', style='charles', savefig='plot.png', alines=alines)
            
            msg = (f"{cat}\n"
                   f"{stato}\n\n"
                   f"<b>Ticker:</b> {ticker}\n"
                   f"<b>Simbolo MT5:</b> <code>{mt5_sym}</code>\n"
                   f"<b>Fase:</b> {'Accumulazione' if is_acc else 'Distribuzione'}\n"
                   f"<b>Prezzo:</b> {df['Close'].iloc[-1]:.4f}\n\n"
                   f"🔵 <b>LIVELLO: {p_livello:.4f}</b>\n"
                   f"🟢 TP: {tp:.4f}\n"
                   f"🔴 SL: {sl:.4f}")
            
            send_telegram(msg, 'plot.png')
            supabase.table("segnali_trading").insert({"ticker": ticker, "prezzo_ingresso": float(p_livello), "tp": float(tp), "sl": float(sl), "fase": fase_attuale}).execute()
            time.sleep(2)
            
    except Exception as e: print(f"Errore su {ticker}: {e}")
