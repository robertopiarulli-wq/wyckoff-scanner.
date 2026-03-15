import MetaTrader5 as mt5
import pandas as pd
import requests
import os

# Configurazione Telegram
TOKEN = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['CHAT_ID']

def send_msg(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text={msg}"
    requests.get(url)

if mt5.initialize():
    symbols = ["EURUSD", "XAUUSD", "HG1!"] # Puoi aggiungere i tuoi ticker
    for s in symbols:
        rates = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_H4, 0, 200)
        df = pd.DataFrame(rates)
        
        high_r = df['high'].rolling(137).max().iloc[-1]
        low_r = df['low'].rolling(137).min().iloc[-1]
        range_h = high_r - low_r
        
        p_livello = low_r - (range_h * 0.007 * 3.0) 
        
        if abs(df['close'].iloc[-1] - p_livello) / p_livello < 0.005:
            send_msg(f"SEGNALE WYCKOFF: {s} è vicino al P_Livello: {p_livello:.4f}")
    
    mt5.shutdown()
