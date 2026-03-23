import os
import requests
import pandas as pd
import yfinance as yf
from supabase import create_client

# --- CONFIG ---
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def analyze_performance():
    # Recupero dati ordinati per ID (ultimi 10)
    res = supabase.table("segnali_trading").select("*").order("id", desc=True).limit(10).execute()
    signals = res.data
    
    if not signals:
        return "📭 Nessun dato trovato nella tabella segnali_trading."

    report = "🧐 **ANALISI PERFORMANCE CECCHINO**\n\n"
    
    for s in signals:
        try:
            # MAPPATURA COLONNE (Ticker confermato, gli altri a tentativo)
            sym = s.get('ticker') or s.get('symbol') or s.get('asset')
            entry = s.get('entry') or s.get('prezzo_ingresso') or s.get('prezzo') or s.get('lvl')
            tp = s.get('tp') or s.get('take_profit') or s.get('target')
            sl = s.get('sl') or s.get('stop_loss') or s.get('stop')
            azione = s.get('azione') or "BUY" # Default se manca

            if not sym or entry is None:
                continue

            entry, tp, sl = float(entry), float(tp), float(sl)
            
            # Download dati (7 giorni per vedere l'evoluzione)
            df = yf.download(sym, period="7d", interval="1h", progress=False)
            if df.empty: continue
            
            current = float(df['Close'].iloc[-1])
            high_max = float(df['High'].max())
            low_min = float(df['Low'].min())
            
            # Logica Buy/Sell basata sul TP
            is_buy = tp > entry
            status = "⏳ In corso"
            
            if is_buy:
                if high_max >= tp: status = "✅ TARGET RAGGIUNTO"
                elif low_min <= sl: status = "🛑 STOP LOSS"
            else:
                if low_min <= tp: status = "✅ TARGET RAGGIUNTO"
                elif high_max >= sl: status = "🛑 STOP LOSS"
                
            diff = ((current - entry) / entry) * 100 if is_buy else ((entry - current) / entry) * 100
            
            report += (f"STRUMENTO: **{sym}**\n"
                       f"Ingresso: {entry:.4f} | Ora: {current:.4f}\n"
                       f"Esito: {status} ({diff:+.2f}%)\n"
                       f"----------------------------\n")
        except Exception as e:
            print(f"Errore analisi riga: {e}")
            continue
    
    return report

def send_report(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'Markdown'})

if __name__ == "__main__":
    report_text = analyze_performance()
    # Se il report contiene strumenti, lo invia, altrimenti stampa errore in log
    if "STRUMENTO" in report_text:
        send_report(report_text)
    else:
        print("DEBUG: Nessun dato valido elaborato. Controlla i nomi delle colonne su Supabase.")
        print(report_text)
