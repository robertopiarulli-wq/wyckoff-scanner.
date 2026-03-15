import yfinance as yf
import requests
import os
import mplfinance as mpf
import time
import numpy as np
import pandas as pd

TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def send_telegram(msg, img_path):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    with open(img_path, 'rb') as photo:
        requests.post(url, files={'photo': photo}, data={'chat_id': CHAT_ID, 'caption': msg})

with open('tickers.txt', 'r') as f:
    symbols = [line.strip() for line in f if line.strip() and not line.startswith('#')]

for ticker in symbols:
    print(f"Analizzo: {ticker}")
    try:
        df = yf.download(ticker, period="3mo", interval="1h", progress=False, auto_adjust=True)
        if df.empty or len(df) < 137: continue
        
        # --- APPIATTIMENTO DATI ---
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df = df.apply(pd.to_numeric, errors='coerce').dropna()
        df.columns = [c.capitalize() for c in df.columns]
        if 'Volume' not in df.columns: df['Volume'] = 0
        
        # --- CALCOLI ---
        high_r = df['High'].rolling(137).max().iloc[-1]
        low_r = df['Low'].rolling(137).min().iloc[-1]
        range_h = high_r - low_r
        
        p_livello = low_r - (range_h * 0.007 * 3.0) 
        tp = p_livello + (range_h * 0.015)
        sl = p_livello - (range_h * 0.005)
        
        prezzo = df['Close'].iloc[-1]
        distanza = abs(prezzo - p_livello) / p_livello
        
        # --- FILTRO SENTINELLA ---
        if distanza < 0.002: semaforo, stato = "🔴", "INGRESSO IMMEDIATO"
        elif distanza < 0.01: semaforo, stato = "🟡", "IN AVVICINAMENTO"
        else: continue # <--- QUI IL BOT SALTA I "LONTANI" E NON MANDA MSG
        
        # --- GRAFICO CON LINEE ---
        plot_data = df.iloc[-50:]
        alines = dict(alines=[
            [(plot_data.index[0], p_livello), (plot_data.index[-1], p_livello)], 
            [(plot_data.index[0], tp), (plot_data.index[-1], tp)],             
            [(plot_data.index[0], sl), (plot_data.index[-1], sl)]              
        ], colors=['blue', 'green', 'red'], linestyle='-.')
        
        mpf.plot(plot_data, type='candle', style='charles', savefig='plot.png', 
                 alines=alines, volume=False)
        
        # --- MESSAGGIO ---
        msg = (f"{semaforo} {ticker}\nStato: {stato}\n"
               f"P_Livello: {p_livello:.2f}\nTP: {tp:.2f} | SL: {sl:.2f}")
        
        send_telegram(msg, 'plot.png')
        print(f"Messaggio inviato per {ticker}")
        time.sleep(2)
        
    except Exception as e:
        print(f"Errore su {ticker}: {e}")
        continue
