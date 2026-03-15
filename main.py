import yfinance as yf
import requests
import os
import mplfinance as mpf
import time
import numpy as np
import pandas as pd
from supabase import create_client

# Configurazione API e DB
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

# Controllo sicurezza
if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERRORE: Variabili Supabase non trovate! Controlla i Secrets su GitHub.")
    exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
ALPHA = 0.00729735

def salva_segnale_db(ticker, ingresso, tp, sl, fase):
    try:
        data = {"ticker": ticker, "prezzo_ingresso": float(ingresso), "tp": float(tp), "sl": float(sl), "fase": fase, "stato": "Pendente"}
        supabase.table("segnali_trading").insert(data).execute()
    except Exception as e:
        print(f"Errore salvataggio DB: {e}")

# ... (resto del codice uguale a quello di prima)
# Assicurati di mantenere la logica di calcolo e il ciclo for come nel file precedente!
