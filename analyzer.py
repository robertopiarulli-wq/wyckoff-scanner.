import os
import pandas as pd
import yfinance as yf
from supabase import create_client
from datetime import datetime, timedelta

# --- CONFIG ---
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_signals_from_db():
    # Recuperiamo i segnali "OPEN" o quelli dell'ultima settimana
    response = supabase.table("segnali_trading").select("*").execute()
    return response.data

def analyze_performance():
    signals = get_signals_from_db()
    if not signals:
        return "Nessun segnale trovato nel database."

    report_msg = "📊 **REPORT ANALISI SEGNALI**\n\n"
    
    for sig in signals:
        symbol = sig['symbol']
        entry = sig['entry']
        tp = sig['tp']
        sl = sig['sl']
        timestamp = pd.to_datetime(sig['created_at']) # o la tua colonna data
        
        # Scarichiamo i dati storici dal momento del segnale a oggi
        df = yf.download(symbol, start=timestamp, progress=False)
        
        if df.empty:
            continue

        # Verifichiamo l'esito
        high_max = df['High'].max()
        low_min = df['Low'].min()
        current_price = df['Close'].iloc[-1]
        
        stato = "⏳ In corso"
        esito = ""

        # Logica di verifica (assumendo BUY se tp > entry)
        is_buy = tp > entry
        
        if is_buy:
            if high_max >= tp:
                stato = "✅ TARGET"
                esito = f"Max raggiunto: {high_max:.4f}"
            elif low_min <= sl:
                stato = "🛑 STOP LOSS"
                esito = f"Min raggiunto: {low_min:.4f}"
        else: # SELL
            if low_min <= tp:
                stato = "✅ TARGET"
                esito = f"Min raggiunto: {low_min:.4f}"
            elif high_max >= sl:
                stato = "🛑 STOP LOSS"
                esito = f"Max raggiunto: {high_max:.4f}"

        report_msg += (f"🔹 **{symbol}** ({sig['azione']})\n"
                       f"Entrata: {entry:.4f} | Stato: {stato}\n"
                       f"Performance Attuale: {((current_price/entry - 1)*100 if is_buy else (1 - current_price/entry)*100):.2f}%\n"
                       f"{esito}\n\n")

    return report_msg

def send_telegram_report(text):
    import requests
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'Markdown'})

if __name__ == "__main__":
    report = analyze_performance()
    send_telegram_report(report)
