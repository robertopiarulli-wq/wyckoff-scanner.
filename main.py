import yfinance as yf
import requests
import os
import matplotlib.pyplot as plt
import pandas as pd

TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']

def send_telegram(name, ticker, semaforo, p_livello, img_path):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    with open(img_path, 'rb') as photo:
        caption = f"{semaforo} {name} ({ticker})\nLivello: {p_livello:.2f}"
        files = {'photo': photo}
        data = {'chat_id': CHAT_ID, 'caption': caption}
        requests.post(url, files=files, data=data)

# Leggiamo i ticker dal file
with open('tickers.txt', 'r') as f:
    symbols = [line.strip() for line in f if line.strip() and not line.startswith('#')]

for ticker in symbols:
    try:
        data = yf.download(ticker, period="3mo", interval="1h", progress=False)
        
        # Filtro sicurezza: se il download fallisce o il ticker non esiste
        if data.empty or len(data) < 137:
            continue
            
        high_r = data['High'].rolling(137).max().iloc[-1]
        low_r = data['Low'].rolling(137).min().iloc[-1]
        range_h = high_r - low_r
        p_livello = low_r - (range_h * 0.007 * 3.0) 
        
        distanza = abs(data['Close'].iloc[-1] - p_livello) / p_livello
        
        if distanza < 0.002: semaforo = "🔴"
        elif distanza < 0.01: semaforo = "🟡"
        else: continue 

        plt.figure(figsize=(10, 5))
        plt.plot(data['Close'][-100:].values, label='Prezzo')
        plt.axhline(y=p_livello, color='blue', linestyle='--', label='P_Livello')
        plt.title(f"Setup Wyckoff: {ticker}")
        plt.legend()
        plt.savefig("plot.png")
        plt.close()
        
        send_telegram(ticker, ticker, semaforo, p_livello, "plot.png")
    except Exception as e:
        print(f"Errore su {ticker}: {e}")
        continue
