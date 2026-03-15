import yfinance as yf
import requests
import os
import mplfinance as mpf
import time
import numpy as np
import pandas as pd

# Configurazione API
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def send_telegram(msg, img_path):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    with open(img_path, 'rb') as photo:
        requests.post(url, files={'photo': photo}, data={'chat_id': CHAT_ID, 'caption': msg})

# Caricamento Ticker
with open('tickers.txt', 'r') as f:
    symbols = [line.strip() for line in f if line.strip() and not line.startswith('#')]

# Ciclo Analisi
for ticker in symbols:
    print(f"Analizzo: {ticker}")
    try:
        # Scarico dati H4 come da tua operatività
        df = yf.download(ticker, period="1mo", interval="4h", progress=False, auto_adjust=True)
        if df.empty or len(df) < 50: continue
        
        # Pulizia dati (Gestione MultiIndex)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.apply(pd.to_numeric, errors='coerce').dropna()
        df.columns = [c.capitalize() for c in df.columns]
        
        # --- CALCOLO PROFESSIONALE (stile MT5) ---
        # ATR (Average True Range) su 14 periodi per la volatilità
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr = true_range.rolling(window=14).mean().iloc[-1]
        
        # Supporto/Resistenza dinamica
        p_livello = df['Low'].rolling(window=20).mean().iloc[-1]
        
        # TP/SL basati su ATR
        tp = p_livello + (atr * 2.0)
        sl = p_livello - (atr * 1.0)
        
        # Distanza per il filtro
        prezzo = df['Close'].iloc[-1]
        distanza = abs(prezzo - p_livello) / p_livello
        
        # Filtro Sentinella: Solo se vicino al livello
        if distanza < 0.015:
            stato = "🔴 INGRESSO" if distanza < 0.005 else "🟡 AVVICINAMENTO"
            
            # Grafico con linee (ATR-calibrated)
            plot_data = df.iloc[-40:]
            alines = dict(alines=[
                [(plot_data.index[0], p_livello), (plot_data.index[-1], p_livello)], 
                [(plot_data.index[0], tp), (plot_data.index[-1], tp)],             
                [(plot_data.index[0], sl), (plot_data.index[-1], sl)]              
            ], colors=['blue', 'green', 'red'], linestyle='-.')
            
            mpf.plot(plot_data, type='candle', style='charles', savefig='plot.png', alines=alines, volume=False)
            
            # Messaggio
            msg = (f"{stato} {ticker}\n"
                   f"Livello: {p_livello:.2f}\n"
                   f"TP: {tp:.2f} | SL: {sl:.2f}")
            
            send_telegram(msg, 'plot.png')
            print(f"Messaggio inviato per {ticker}")
            time.sleep(2)
        else:
            continue
            
    except Exception as e:
        print(f"Errore su {ticker}: {e}")
        continue
