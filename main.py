import yfinance as yf
import requests
import os
import mplfinance as mpf
import time
import numpy as np
import pandas as pd

# Costanti Quantum/Wyckoff
ALPHA = 0.00729735

TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def send_telegram(msg, img_path):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    try:
        with open(img_path, 'rb') as photo:
            requests.post(url, files={'photo': photo}, data={'chat_id': CHAT_ID, 'caption': msg})
    except Exception as e:
        print(f"Errore invio Telegram: {e}")

# --- LETTURA E PULIZIA TICKERS ---
def get_clean_tickers():
    with open('tickers.txt', 'r') as f:
        # Pulisce spazi, rimuove righe vuote e commenti
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

symbols = get_clean_tickers()

# --- LOGICA CALCOLO QUANTUM ---
def calcola_quantum_wyckoff(df):
    high_r = df['High'].rolling(137).max().iloc[-1]
    low_r = df['Low'].rolling(137).min().iloc[-1]
    range_h = high_r - low_r
    mid_p = (high_r + low_r) / 2.0
    is_acc = df['Close'].iloc[-1] < mid_p
    p_livello = low_r - (range_h * ALPHA * 3.0) if is_acc else high_r + (range_h * ALPHA * 3.0)
    sl = p_livello - (p_livello * ALPHA) if is_acc else p_livello + (p_livello * ALPHA)
    tp = p_livello + (range_h * 1.37) if is_acc else p_livello - (range_h * 1.37)
    return p_livello, sl, tp

# --- CICLO ANALISI ---
for ticker in symbols:
    print(f"Analizzo: {ticker}")
    try:
        # Download robusto
        df = yf.download(ticker, period="3mo", interval="4h", progress=False, auto_adjust=True)
        
        # Gestione formati Yahoo
        if isinstance(df, tuple): df = df[0]
        if df.empty or len(df) < 137: continue
        
        # Pulizia colonne
        df.columns = [str(c[0] if isinstance(c, tuple) else c).capitalize() for c in df.columns]
        df = df.apply(pd.to_numeric, errors='coerce').dropna()
        
        p_livello, sl, tp = calcola_quantum_wyckoff(df)
        prezzo = df['Close'].iloc[-1]
        distanza = abs(prezzo - p_livello) / p_livello
        
        if distanza < 0.015:
            stato = "🔴 INGRESSO" if distanza < 0.005 else "🟡 AVVICINAMENTO"
            
            # Grafico
            plot_data = df.iloc[-50:]
            alines = dict(alines=[
                [(plot_data.index[0], p_livello), (plot_data.index[-1], p_livello)], 
                [(plot_data.index[0], tp), (plot_data.index[-1], tp)],             
                [(plot_data.index[0], sl), (plot_data.index[-1], sl)]              
            ], colors=['blue', 'green', 'red'], linestyle='-.')
            
            mpf.plot(plot_data, type='candle', style='charles', savefig='plot.png', alines=alines)
            
            msg = f"{stato} {ticker}\nLivello: {p_livello:.4f}\nTP: {tp:.4f} | SL: {sl:.4f}"
            send_telegram(msg, 'plot.png')
            time.sleep(2)
            
    except Exception as e:
        print(f"Errore critico su {ticker}: {e}")
        continue
