import yfinance as yf
import requests
import os
import mplfinance as mpf
import time
import numpy as np
import pandas as pd

TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def send_telegram(msg, img_path):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    with open(img_path, 'rb') as photo:
        requests.post(url, files={'photo': photo}, data={'chat_id': CHAT_ID, 'caption': msg})

# --- CARICAMENTO TICKER ---
with open('tickers.txt', 'r') as f:
    symbols = [line.strip() for line in f if line.strip() and not line.startswith('#')]

# --- CICLO PRINCIPALE ---
for ticker in symbols:
    print(f"Analizzo: {ticker}")
    try:
        df = yf.download(ticker, period="3mo", interval="1h", progress=False, auto_adjust=True)
        if df.empty or len(df) < 137: continue
        
        # --- PULIZIA DATI PER MPLFINANCE ---
        # Assicuriamoci che tutte le colonne siano float
        df = df.apply(pd.to_numeric, errors='coerce')
        # Rimuoviamo eventuali righe vuote
        df = df.dropna()
        # Assicuriamoci che i nomi siano quelli corretti
        df.columns = [c.capitalize() for c in df.columns] 
        
        # Estrarre valori per i calcoli
        high_s = df['High'].values
        low_s = df['Low'].values
        close_s = df['Close'].values
        
        # ... (il resto del tuo calcolo p_livello e distanza rimane uguale) ...
        
        # Creazione grafico con pulizia extra
        # Se manca il Volume, mplfinance crasha, lo creiamo fittizio
        if 'Volume' not in df.columns:
            df['Volume'] = 0
            
        mpf.plot(df.iloc[-50:], type='candle', style='charles', savefig='plot.png', volume=False)
        
        # Invio
        send_telegram(msg, 'plot.png')
        print(f"Messaggio inviato per {ticker}")
            
        # Estrarre i valori come numpy array per evitare l'errore di ambiguità
        high_s = df['High'].values
        low_s = df['Low'].values
        close_s = df['Close'].values
        
        # Calcolo livelli Wyckoff
        high_r = np.max(high_s[-137:])
        low_r = np.min(low_s[-137:])
        range_h = high_r - low_r
        p_livello = low_r - (range_h * 0.007 * 3.0) 
        prezzo = close_s[-1]
        
        distanza = abs(prezzo - p_livello) / p_livello
        
        # LOGICA TEST: Inviamo TUTTO per verificare la connessione
        if distanza < 0.002: 
            semaforo, stato = "🔴", "INGRESSO IMMEDIATO"
        elif distanza < 0.01: 
            semaforo, stato = "🟡", "IN AVVICINAMENTO"
        else: 
            semaforo, stato = "⚪", "LONTANO"
        
        msg = f"{semaforo} {ticker}\nStato: {stato}\nTarget: {p_livello:.2f}"
        
        # Creazione grafico
        mpf.plot(df.iloc[-50:], type='candle', style='charles', savefig='plot.png')
        
        # Invio
        send_telegram(msg, 'plot.png')
        print(f"Messaggio inviato per {ticker}")
        time.sleep(2)
        
    except Exception as e:
        print(f"Errore su {ticker}: {e}")
        continue
