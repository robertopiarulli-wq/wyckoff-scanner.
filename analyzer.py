import os
import requests
import pandas as pd
import yfinance as yf
from supabase import create_client
import time

# --- CONFIGURAZIONE AMBIENTE ---
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# Inizializzazione Client Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def analyze_full_backtest():
    """
    Analizza il regresso dei segnali nel database Supabase.
    Allineato ai nomi colonne del main: prezzo_ingresso, tp, sl, ticker.
    """
    # 1. Recupero di TUTTI i segnali dal database
    res = supabase.table("segnali_trading").select("*").order("id", desc=False).execute()
    signals = res.data
    
    if not signals:
        return "📭 Database vuoto: nessun segnale da analizzare."

    stats = {
        "vinti": 0, 
        "persi": 0, 
        "aperti": 0, 
        "pnl_netto": 0.0,
        "totale_processati": 0
    }
    
    print(f"🚀 Avvio analisi di {len(signals)} segnali...")

    for s in signals:
        try:
            # Mappatura coerente con la tabella 'segnali_trading'
            sym = s.get('ticker')
            entry = s.get('prezzo_ingresso')
            tp = s.get('tp')
            sl = s.get('sl')
            
            if not sym or entry is None or tp is None or sl is None:
                continue

            entry, tp, sl = float(entry), float(tp), float(sl)
            stats["totale_processati"] += 1
            
            # Gestione Ticker: mantiene il formato originale (es. FTSEMIB.MI o ^GDAXI)
            # Yahoo Finance richiede i prefissi/suffissi corretti per gli indici
            df = yf.download(sym, period="1mo", interval="1h", progress=False)
            
            if df.empty:
                print(f"⚠️ Dati non trovati per {sym}")
                continue
            
            high_max = float(df['High'].max().item())
            low_min = float(df['Low'].min().item())
            is_buy = tp > entry # Determina se Long o Short dalla posizione del TP
            
            # Verifica Esito Operazione
            if is_buy:
                if high_max >= tp:
                    stats["vinti"] += 1
                    stats["pnl_netto"] += ((tp - entry) / entry) * 100
                elif low_min <= sl:
                    stats["persi"] += 1
                    stats["pnl_netto"] -= ((entry - sl) / entry) * 100
                else:
                    stats["aperti"] += 1
            else:
                if low_min <= tp:
                    stats["vinti"] += 1
                    stats["pnl_netto"] += ((entry - tp) / entry) * 100
                elif high_max >= sl:
                    stats["persi"] += 1
                    stats["pnl_netto"] -= ((sl - entry) / entry) * 100
                else:
                    stats["aperti"] += 1
            
            # Pausa per evitare blocchi da Yahoo Finance
            if stats["totale_processati"] % 10 == 0:
                time.sleep(1)

        except Exception as e:
            print(f"❌ Errore ID {s.get('id')}: {e}")
            continue

    conclusi = stats["vinti"] + stats["persi"]
    wr = (stats["vinti"] / conclusi * 100) if conclusi > 0 else 0
    pnl_medio = (stats["pnl_netto"] / conclusi) if conclusi > 0 else 0

    report = (
        f"📊 **ANALISI REGRESSO INTEGRALE**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📂 Totale in DB: {len(signals)}\n"
        f"⚙️ Analizzati: {stats['totale_processati']}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✅ Target: {stats['vinti']}\n"
        f"🛑 Stop: {stats['persi']}\n"
        f"⏳ In corso: {stats['aperti']}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📈 **Win Rate: {wr:.2f}%**\n"
        f"💰 **PnL Totale: {stats['pnl_netto']:+.2f}%**\n"
        f"🎯 **Profitto Medio: {pnl_medio:+.2f}%/trade**\n"
    )
    return report

def send_telegram_report(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, data=payload)
    except Exception:
        pass

if __name__ == "__main__":
    risultato = analyze_full_backtest()
    send_telegram_report(risultato)
