import yfinance as yf
import requests
import os
import matplotlib.pyplot as plt

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
        # download per singolo ticker evita i conflitti di MultiIndex
        df = yf.download(ticker, period="3mo", interval="1h", progress=False)
        
        if df.empty or len(df) < 137:
            continue
            
        # Assicuriamoci di lavorare con serie singole
        high_s = df['High']
        low_s = df['Low']
        close_s = df['Close']
        
        high_r = high_s.rolling(137).max().iloc[-1]
        low_r = low_s.rolling(137).min().iloc[-1]
        range_h = high_r - low_r
        p_livello = low_r - (range_h * 0.007 * 3.0) 
        
        prezzo_attuale = close_s.iloc[-1]
        distanza = abs(prezzo_attuale - p_livello) / p_livello
        
        if distanza < 0.002: semaforo = "🔴"
        elif distanza < 0.01: semaforo = "🟡"
        else: continue 

        plt.figure(figsize=(10, 5))
        plt.plot(close_s[-100:].values, label='Prezzo')
        plt.axhline(y=p_livello, color='blue', linestyle='--', label='P_Livello')
        plt.title(f"Setup Wyckoff: {ticker}")
        plt.legend()
        plt.savefig("plot.png")
        plt.close()
        
        send_telegram(ticker, ticker, semaforo, p_livello, "plot.png")
    except Exception as e:
        print(f"Errore su {ticker}: {e}")
        continue
