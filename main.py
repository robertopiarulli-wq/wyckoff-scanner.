import yfinance as yf
import requests
import os
import mplfinance as mpf
import time
import numpy as np
import pandas as pd
from supabase import create_client

# --- CONFIGURAZIONE ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

# Controllo sicurezza inizializzazione
if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERRORE: Variabili Supabase non trovate nei Secrets di GitHub!")
    exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
ALPHA = 0.00729735

def send_telegram(msg, img_path):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    try:
        with open(img_path, 'rb') as photo:
            requests.post(url, files={'photo': photo}, data={'chat_id': CHAT_ID, 'caption': msg})
    except Exception as e:
        print(f"Errore invio Telegram: {e}")

def salva_segnale_db(ticker, ingresso, tp, sl, fase):
    try:
        data = {
            "ticker": ticker, 
            "prezzo_ingresso": float(ingresso), 
            "tp": float(tp), 
            "sl": float(sl), 
            "fase": fase, 
            "stato": "Pendente"
        }
        supabase.table("segnali_trading").insert(data).execute()
        print(f"-> Segnale registrato su Supabase per {ticker}")
    except Exception as e:
        print(f"Errore scrittura DB: {e}")

def get_clean_tickers():
    if not os.path.exists('tickers.txt'):
        return []
    with open('tickers.txt', 'r') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

# --- AVVIO ANALISI ---
symbols = get_clean_tickers()
print(f"Avvio scansione su {len(symbols)} ticker...")

for ticker in symbols:
    try:
        # Download dati
        df = yf.download(ticker, period="3mo", interval="4h", progress=False, auto_adjust=True)
        
        if isinstance(df, tuple): df = df[0]
        if df.empty or len(df) < 137:
            print(f"Dati insufficienti per {ticker}, salto.")
            continue
        
        # Pulizia e Formattazione Colonne
        df.columns = [str(c[0] if isinstance(c, tuple) else c).capitalize() for c in df.columns]
        df = df.apply(pd.to_numeric, errors='coerce').dropna()
        
        # Logica Quantum/Wyckoff (Sincronizzata con MT5)
        high_r = df['High'].rolling(137).max().iloc[-1]
        low_r = df['Low'].rolling(137).min().iloc[-1]
        range_h = high_r - low_r
        mid_p = (high_r + low_r) / 2.0
        
        is_acc = df['Close'].iloc[-1] < mid_p
        
        p_livello = low_r - (range_h * ALPHA * 3.0) if is_acc else high_r + (range_h * ALPHA * 3.0)
        sl = p_livello - (p_livello * ALPHA) if is_acc else p_livello + (p_livello * ALPHA)
        tp = p_livello + (range_h * 1.37) if is_acc else p_livello - (range_h * 1.37)
        
        prezzo_attuale = df['Close'].iloc[-1]
        distanza = abs(prezzo_attuale - p_livello) / p_livello
        
        # Log di tracciamento nel terminale GitHub
        print(f"[{ticker}] Prezzo: {prezzo_attuale:.4f} | Livello: {p_livello:.4f} | Dist: {distanza:.2%}")

        # Filtro Notifica (1.5%)
        if distanza < 0.015:
            print(f"!!! SEGNALE TROVATO PER {ticker} !!!")
            stato = "🔴 INGRESSO" if distanza < 0.005 else "🟡 AVVICINAMENTO"
            
            # Creazione Grafico
            plot_data = df.iloc[-50:]
            alines = dict(alines=[
                [(plot_data.index[0], p_livello), (plot_data.index[-1], p_livello)], 
                [(plot_data.index[0], tp), (plot_data.index[-1], tp)],             
                [(plot_data.index[0], sl), (plot_data.index[-1], sl)]
            ], colors=['blue', 'green', 'red'], linestyle='-.')
            
            mpf.plot(plot_data, type='candle', style='charles', savefig='plot.png', alines=alines)
            
            # Notifica Telegram
            fase_str = "Accumulazione" if is_acc else "Distribuzione"
            msg = f"{stato} {ticker} ({fase_str})\nPrezzo: {prezzo_attuale:.4f}\nLivello: {p_livello:.4f}\nTP: {tp:.4f} | SL: {sl:.4f}"
            
            send_telegram(msg, 'plot.png')
            
            # Salvataggio Database
            salva_segnale_db(ticker, p_livello, tp, sl, "Acc" if is_acc else "Dist")
            
            time.sleep(2) # Pausa per evitare spam/limitazioni API

    except Exception as e:
        print(f"Errore critico durante l'analisi di {ticker}: {e}")
        continue

print("Scansione completata.")
