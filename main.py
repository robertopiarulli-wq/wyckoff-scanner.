import yfinance as yf
import requests
import os
import matplotlib.pyplot as plt
import numpy as np

TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']

def send_telegram(name, ticker, semaforo, p_livello, img_path):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    with open(img_path, 'rb') as photo:
        caption = f"{semaforo} {name} ({ticker})\nLivello: {p_livello:.2f}"
        files = {'photo': photo}
        data = {'chat_id': CHAT_ID, 'caption': caption}
        requests.post(url, files=files, data=data)

with open('tickers.txt', 'r') as f:
    symbols = [line.strip() for line in f if line.strip() and not line.startswith('#')]

for ticker in symbols:
    try:
        # Download con auto_adjust=True per pulire i dati
        df = yf.download(ticker, period="3mo", interval="1h", progress=False, auto_adjust=True)
        
        if df.empty or len(df) < 137:
            continue
            
        # Forza la trasformazione in array numpy piatti per evitare l'ambiguità
        high_s = df['High'].values
        low_s = df['Low'].values
        close_s = df['Close'].values
        
        # Calcolo rolling manuale su array numpy per evitare conflitti con Pandas Series
        def rolling_min(arr, window):
            return np.min([arr[i-window+1:i+1] for i in range(window-1, len(arr))], axis=0)
        
        def rolling_max(arr, window):
            return np.max([arr[i-window+1:i+1] for i in range(window-1, len(arr))], axis=0)

        high_r = np.max(high_s[-137:])
        low_r = np.min(low_s[-137:])
        
        range_h = high_r - low_r
        p_livello = low_r - (range_h * 0.007 * 3.0) 
        
        prezzo_attuale = close_s[-1]
        distanza = abs(prezzo_attuale - p_livello) / p_livello
        
        # Logica Semaforo
        if distanza < 0.002: semaforo = "🔴"
        elif distanza < 0.01: semaforo = "🟡"
        else: continue 

        # Grafico
        plt.figure(figsize=(10, 5))
        plt.plot(close_s[-100:], label='Prezzo')
        plt.axhline(y=p_livello, color='blue', linestyle='--', label='P_Livello')
        plt.title(f"Setup Wyckoff: {ticker}")
        plt.legend()
        plt.savefig("plot.png")
        plt.close()
        
        send_telegram(ticker, ticker, semaforo, p_livello, "plot.png")
        
    except Exception as e:
        print(f"Errore su {ticker}: {e}")
        continue
