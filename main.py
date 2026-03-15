import yfinance as yf
import requests
import os
import mplfinance as mpf
import time
import pandas as pd

print("Avvio script...") # Debug 1

TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def send_telegram(msg, img_path):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    with open(img_path, 'rb') as photo:
        files = {'photo': photo}
        data = {'chat_id': CHAT_ID, 'caption': msg}
        requests.post(url, files=files, data=data)
    print("Messaggio inviato.") # Debug 2

with open('tickers.txt', 'r') as f:
    symbols = [line.strip() for line in f if line.strip() and not line.startswith('#')]
print(f"Ticker trovati: {len(symbols)}") # Debug 3

for ticker in symbols:
    print(f"Analizzo: {ticker}") # Debug 4
    try:
        df = yf.download(ticker, period="3mo", interval="1h", progress=False, auto_adjust=True)
        # Forza la selezione del prezzo se è multi-indice
        close_price = df['Close'].iloc[-1]
        if isinstance(close_price, pd.Series): close_price = close_price.iloc[-1]
        
        high_r = df['High'].max() if isinstance(df['High'], (float, int)) else df['High'].rolling(137).max().iloc[-1]
        low_r = df['Low'].min() if isinstance(df['Low'], (float, int)) else df['Low'].rolling(137).min().iloc[-1]
        
        range_h = high_r - low_r
        p_livello = low_r - (range_h * 0.007 * 3.0) 
        
        distanza = abs(close_price - p_livello) / p_livello
        
        # LOGICA TEST: Inviamo tutto
        semaforo = "🔴" if distanza < 0.002 else ("🟡" if distanza < 0.01 else "⚪")
        stato = "INGRESSO" if distanza < 0.002 else ("AVVICINAMENTO" if distanza < 0.01 else "LONTANO")
        
        msg = f"{semaforo} {ticker}\nStato: {stato}\nTarget: {p_livello:.2f}"
        mpf.plot(df.iloc[-50:], type='candle', style='charles', savefig='plot.png')
        send_telegram(msg, 'plot.png')
        time.sleep(2)
        print(f"Finito {ticker}") # Debug 5
    except Exception as e:
        print(f"Errore su {ticker}: {e}") # Debug 6
        continue
