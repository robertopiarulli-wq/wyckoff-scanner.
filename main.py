import yfinance as yf
import requests
import os
import matplotlib.pyplot as plt

# Recupera i segreti da GitHub Actions
TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']

def send_telegram(ticker, name, semaforo, p_livello, img_path):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    with open(img_path, 'rb') as photo:
        caption = f"{semaforo} {name} ({ticker})\nLivello: {p_livello:.2f}"
        files = {'photo': photo}
        data = {'chat_id': CHAT_ID, 'caption': caption}
        requests.post(url, files=files, data=data)

# Leggiamo i ticker dal file
with open('tickers.txt', 'r') as f:
    symbols = [line.strip() for line in f if line.strip()]

for ticker in symbols:
    data = yf.download(ticker, period="3mo", interval="1h")
    
    # Logica Wyckoff
    high_r = data['High'].rolling(137).max().iloc[-1]
    low_r = data['Low'].rolling(137).min().iloc[-1]
    range_h = high_r - low_r
    p_livello = low_r - (range_h * 0.007 * 3.0) 
    
    # Semaforo
    distanza = abs(data['Close'].iloc[-1] - p_livello) / p_livello
    if distanza < 0.002:
        semaforo = "🔴"
    elif distanza < 0.01:
        semaforo = "🟡"
    else:
        continue # Ignora se grigio (lontano)

    # Generazione Grafico
    plt.figure(figsize=(10, 5))
    plt.plot(data['Close'][-100:], label='Prezzo')
    plt.axhline(y=p_livello, color='blue', linestyle='--', label='P_Livello')
    plt.title(f"Setup Wyckoff: {ticker}")
    plt.legend()
    plt.savefig("plot.png")
    plt.close()
    
    # Invio
    send_telegram(ticker, ticker, semaforo, p_livello, "plot.png")
