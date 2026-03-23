import os
import requests
import pandas as pd
import yfinance as yf
from supabase import create_client
from datetime import datetime

# --- CONFIG ---
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def analyze_performance():
    # Recupera i dati dalla tua tabella esistente
    res = supabase.table("segnali_trading").select("*").order("created_at", descending=True).limit(10).execute()
    signals = res.data
    
    if not signals:
        return "📭 Nessun dato trovato nella tabella segnali_trading."

    report = "🧐 **ANALISI PERFORMANCE CECCHINO**\n\n"
    
    for s in signals:
        sym = s['symbol']
        entry = float(s['entry'])
        tp = float(s['tp'])
        sl = float(s['sl'])
        # Scarichiamo i dati dal momento del segnale (approssimato a 7gg fa per velocità)
        df = yf.download(sym, period="7d", interval="1h", progress=False)
        
        if df.empty: continue
        
        current = df['Close'].iloc[-1]
        high_max = df['High'].max()
        low_min = df['Low'].min()
        
        # Verifica esito (Assumendo Buy se TP > Entry)
        is_buy = tp > entry
        status = "⏳ In corso"
        if is_buy:
            if high_max >= tp: status = "✅ TARGET RAGGIUNTO"
            elif low_min <= sl: status = "🛑 STOP LOSS"
        else:
            if low_min <= tp: status = "✅ TARGET RAGGIUNTO"
            elif high_max >= sl: status = "🛑 STOP LOSS"
            
        diff = ((current - entry) / entry) * 100 if is_buy else ((entry - current) / entry) * 100
        
        report += (f"STUMENTO: **{sym}**\n"
                   f"Ingresso: {entry:.4f} | Ora: {current:.4f}\n"
                   f"Esito: {status} ({diff:+.2f}%)\n"
                   f"----------------------------\n")
    
    return report

def send_report(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'Markdown'})

if __name__ == "__main__":
    report_text = analyze_performance()
    send_report(report_text)
