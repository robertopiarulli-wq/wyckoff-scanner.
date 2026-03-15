import yfinance as yf
import requests
import os
import mplfinance as mpf
import numpy as np

TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']

# Mappa Ticker -> Nome MT5
MT5_MAP = {"HG=F": "HG1!", "GC=F": "XAUUSD", "BTC-USD": "BTCUSD", "EURUSD=X": "EURUSD"}

def send_telegram(msg, img_path):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    with open(img_path, 'rb') as photo:
        requests.post(url, files={'photo': photo}, data={'chat_id': CHAT_ID, 'caption': msg})

with open('tickers.txt', 'r') as f:
    symbols = [line.strip() for line in f if line.strip() and not line.startswith('#')]

for ticker in symbols:
    try:
        df = yf.download(ticker, period="3mo", interval="1h", progress=False, auto_adjust=True)
        if df.empty or len(df) < 137: continue
            
        high_r = df['High'].rolling(137).max().iloc[-1]
        low_r = df['Low'].rolling(137).min().iloc[-1]
        range_h = high_r - low_r
        
        # Calcolo P_Livello (Spring se prezzo > low_r, Upthrust se prezzo < high_r)
        p_livello = low_r - (range_h * 0.007 * 3.0) 
        tp, sl = p_livello + (range_h * 0.03), p_livello - (range_h * 0.01)
        
        prezzo = df['Close'].iloc[-1]
        distanza = abs(prezzo - p_livello) / p_livello
        
        # Semaforo
        if distanza < 0.002: semaforo, stato = "🔴", "INGRESSO IMMEDIATO"
        elif distanza < 0.01: semaforo, stato = "🟡", "IN AVVICINAMENTO"
        else: semaforo, stato = "⚪", "LONTANO"
        
        # Fase Wyckoff semplificata
        fase = "ACCUMULAZIONE" if prezzo > low_r else "DISTRIBUZIONE"
        
        msg = (f"{semaforo} {MT5_MAP.get(ticker, ticker)}\n"
               f"Stato: {stato}\nFase: {fase}\n"
               f"BUY LIMIT: {p_livello:.2f}\n"
               f"TP: {tp:.2f} | SL: {sl:.2f}")

        # Grafico
        mpf.plot(df.iloc[-50:], type='candle', style='charles', savefig='plot.png',
                 hlines=dict(hlines=[p_livello, tp, sl], colors=['blue', 'green', 'red'], linestyle='-.'))
        
        send_telegram(msg, 'plot.png')
    except Exception: continue
