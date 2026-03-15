import yfinance as yf
import requests
import os

# Configurazione Telegram
TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']

def send_msg(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text={msg}"
    requests.get(url)

# Simboli (Ticker Yahoo Finance: HG=F per Rame, BTC-USD per Bitcoin)
symbols = {"HG=F": "Rame", "BTC-USD": "Bitcoin", "GC=F": "Oro"}

for ticker, name in symbols.items():
    data = yf.download(ticker, period="6mo", interval="1h")
    
    # Calcolo Wyckoff
    high_r = data['High'].rolling(137).max().iloc[-1]
    low_r = data['Low'].rolling(137).min().iloc[-1]
    range_h = high_r - low_r
    
    # Calcolo p_livello (Costante 3.0)
    p_livello = low_r - (range_h * 0.007 * 3.0) 
    
    # Verifica soglia (se il prezzo è entro lo 0.5% dal P_Livello)
    if abs(data['Close'].iloc[-1] - p_livello) / p_livello < 0.005:
        send_msg(f"SEGNALE WYCKOFF: {name} ({ticker}) è vicino al P_Livello: {p_livello:.2f}")
