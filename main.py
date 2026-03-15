import yfinance as yf
import requests
import os
import mplfinance as mpf
import time
import pandas as pd

# Costanti del tuo sistema
ALPHA = 0.00729735

def calcola_quantum_wyckoff(df):
    # 1. Calcolo Range (Lookback 137)
    high_r = df['High'].rolling(137).max().iloc[-1]
    low_r = df['Low'].rolling(137).min().iloc[-1]
    range_h = high_r - low_r
    mid_p = (high_r + low_r) / 2.0
    
    # 2. Determinazione Fase (Acc/Dist)
    is_acc = df['Close'].iloc[-1] < mid_p
    
    # 3. P_Livello (Logica Quantistica)
    p_livello = low_r - (range_h * ALPHA * 3.0) if is_acc else high_r + (range_h * ALPHA * 3.0)
    
    # 4. SL e TP
    sl = p_livello - (p_livello * ALPHA) if is_acc else p_livello + (p_livello * ALPHA)
    tp = p_livello + (range_h * 1.37) if is_acc else p_livello - (range_h * 1.37)
    
    return p_livello, sl, tp

# --- CICLO PRINCIPALE ---
for ticker in symbols:
    df = yf.download(ticker, period="3mo", interval="4h", progress=False, auto_adjust=True)
    if df.empty or len(df) < 137: continue
    
    # Pulizia
    df.columns = [c.capitalize() for c in df.columns]
    
    # Calcolo con la TUA formula
    p_livello, sl, tp = calcola_quantum_wyckoff(df)
    
    # Logica Sentinella (Notifica solo se vicino al P_Livello)
    prezzo = df['Close'].iloc[-1]
    distanza = abs(prezzo - p_livello) / p_livello
    
    if distanza < 0.015: # Soglia di notifica
        # Disegno grafico con i tuoi livelli precisi
        alines = dict(alines=[
            [(df.index[-50], p_livello), (df.index[-1], p_livello)], 
            [(df.index[-50], tp), (df.index[-1], tp)],             
            [(df.index[-50], sl), (df.index[-1], sl)]              
        ], colors=['blue', 'green', 'red'], linestyle='-.')
        
        mpf.plot(df.iloc[-50:], type='candle', style='charles', savefig='plot.png', alines=alines)
        
        msg = f"🚀 {ticker}\nLivello: {p_livello:.4f}\nTP: {tp:.4f} | SL: {sl:.4f}"
        send_telegram(msg, 'plot.png')
