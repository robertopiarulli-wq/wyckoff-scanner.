import yfinance as yf
import requests
import os
import mplfinance as mpf
import pandas as pd
import numpy as np

TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']

# Mappa Ticker Yahoo -> Nome MT5
MT5_MAP = {
    "HG=F": "HG1!", "GC=F": "XAUUSD", "BTC-USD": "BTCUSD", 
    "EURUSD=X": "EURUSD", "CL=F": "WTI", "ES=F": "US500"
}

def send_telegram(mt5_name, ticker, semaforo, p_livello, tp, sl, img_path):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    with open(img_path, 'rb') as photo:
        caption = (f"{semaforo} {mt5_name} (Yahoo: {ticker})\n"
                   f"P_Livello: {p_livello:.2f}\n"
                   f"TP: {tp:.2f} | SL: {sl:.2f}")
        requests.post(url, files={'photo': photo}, data={'chat_id': CHAT_ID, 'caption': caption})

with open('tickers.txt', 'r') as f:
    symbols = [line.strip() for line in f if line.strip() and not line.startswith('#')]

for ticker in symbols:
    try:
        df = yf.download(ticker, period="3mo", interval="1h", progress=False, auto_adjust=True)
        if df.empty or len(df) < 137: continue
            
        high_r = df['High'].rolling(137).max().iloc[-1]
        low_r = df['Low'].rolling(137).min().iloc[-1]
        range_h = high_r - low_r
        
        p_livello = low_r - (range_h * 0.007 * 3.0) 
        # Logica arbitraria TP/SL basata su Range
        tp = p_livello + (range_h * 0.015)
        sl = p_livello - (range_h * 0.005)
        
        prezzo = df['Close'].iloc[-1]
        distanza = abs(prezzo - p_livello) / p_livello
        # Aumentiamo la soglia a 0.5 (50%) per forzare il bot a inviare messaggi if distanza > 0.5: continue
        semaforo = "🔴" if distanza < 0.002 else "🟡"

        # Grafico a candele
        plot_df = df.iloc[-50:] # Ultimi 50 periodi
        alines = [dict(alines=[(plot_df.index[0], p_livello), (plot_df.index[-1], p_livello)], colors='blue', linestyle='--'),
                  dict(alines=[(plot_df.index[0], tp), (plot_df.index[-1], tp)], colors='green', linestyle='-'),
                  dict(alines=[(plot_df.index[0], sl), (plot_df.index[-1], sl)], colors='red', linestyle='-')]
        
        mpf.plot(plot_df, type='candle', style='charles', savefig='plot.png', alines=alines, title=ticker)
        
        mt5_name = MT5_MAP.get(ticker, ticker)
        send_telegram(mt5_name, ticker, semaforo, p_livello, tp, sl, 'plot.png')
        
    except Exception as e:
        continue
