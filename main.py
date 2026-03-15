import yfinance as yf
import requests
import os
import matplotlib.pyplot as plt

TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']

def send_photo(ticker, p_livello, img_path):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    files = {'photo': open(img_path, 'rb')}
    data = {'chat_id': CHAT_ID, 'caption': f"Segnale Wyckoff: {ticker} vicino a {p_livello:.2f}"}
    requests.post(url, files=files, data=data)

symbols = {"HG=F": "Rame", "BTC-USD": "Bitcoin"}

for ticker, name in symbols.items():
    data = yf.download(ticker, period="3mo", interval="1h")
    
    high_r = data['High'].rolling(137).max().iloc[-1]
    low_r = data['Low'].rolling(137).min().iloc[-1]
    range_h = high_r - low_r
    p_livello = low_r - (range_h * 0.007 * 3.0) 
    
    if abs(data['Close'].iloc[-1] - p_livello) / p_livello < 0.005:
        # Generazione Grafico
        plt.figure(figsize=(10, 5))
        plt.plot(data['Close'][-100:], label='Prezzo')
        plt.axhline(y=p_livello, color='blue', linestyle='--', label='P_Livello')
        plt.title(f"Setup Wyckoff: {name}")
        plt.legend()
        plt.savefig("plot.png")
        plt.close()
        
        # Invio su Telegram
        send_photo(name, p_livello, "plot.png")
