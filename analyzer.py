import os
import requests
import pandas as pd
import yfinance as yf
from supabase import create_client
import time

# --- CONFIGURAZIONE AMBIENTE ---
# Assicurati che questi segreti siano impostati su GitHub Actions
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# Inizializzazione Client Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def analyze_full_backtest():
    """
    Analizza l'intero regresso dei segnali nel database Supabase.
    Utilizza i nomi reali delle colonne: prezzo_ingresso, tp, sl, ticker.
    """
    # 1. Recupero di TUTTI i segnali dal database
    res = supabase.table("segnali_trading").select("*").order("id", desc=False).execute()
    signals = res.data
    
    if not signals:
        return "📭 Database vuoto: nessun segnale da analizzare."

    # Contatori statistici
    stats = {
        "vinti": 0, 
        "persi": 0, 
        "aperti": 0, 
        "pnl_netto": 0.0,
        "totale_processati": 0
    }
    
    print(f"🚀 Avvio analisi di {len(signals)} segnali in corso...")

    for s in signals:
        try:
            # MAPPATURA BASATA SULLA TUA TABELLA REALE
            sym = s.get('ticker')
            entry = s.get('prezzo_ingresso')
            tp = s.get('tp')
            sl = s.get('sl')
            
            if not sym or entry is None or tp is None or sl is None:
                continue

            entry, tp, sl = float(entry), float(tp), float(sl)
            stats["totale_processati"] += 1
            
            # Fix automatico per il ticker del DAX per evitare errori 404
            ticker_yf = sym if "GDAXI" not in sym else "^GDAXI"
            
            # Download dati storici (periodo di 1 mese per verificare l'esito dei segnali passati)
            df = yf.download(ticker_yf, period="1mo", interval="1h", progress=False)
            
            if df.empty:
                print(f"⚠️ Dati non trovati per {sym}")
                continue
            
            # Analisi dei prezzi (usiamo .item() per evitare FutureWarning di Pandas)
            high_max = float(df['High'].max().item())
            low_min = float(df['Low'].min().item())
            is_buy = tp > entry # Definiamo se è un segnale Long o Short
            
            # VERIFICA ESITO OPERAZIONE
            if is_buy:
                # Caso BUY: controlliamo prima il Target, poi lo Stop
                if high_max >= tp:
                    stats["vinti"] += 1
                    stats["pnl_netto"] += ((tp - entry) / entry) * 100
                elif low_min <= sl:
                    stats["persi"] += 1
                    stats["pnl_netto"] -= ((entry - sl) / entry) * 100
                else:
                    stats["aperti"] += 1
            else:
                # Caso SELL: controlliamo prima il Target (prezzo scende), poi lo Stop
                if low_min <= tp:
                    stats["vinti"] += 1
                    stats["pnl_netto"] += ((entry - tp) / entry) * 100
                elif high_max >= sl:
                    stats["persi"] += 1
                    stats["pnl_netto"] -= ((sl - entry) / entry) * 100
                else:
                    stats["aperti"] += 1
            
            # Pausa tecnica per rispettare i limiti di Yahoo Finance
            if stats["totale_processati"] % 10 == 0:
                print(f"⏳ Elaborati {stats['totale_processati']} segnali...")
                time.sleep(1)

        except Exception as e:
            print(f"❌ Errore durante l'analisi del segnale ID {s.get('id')}: {e}")
            continue

    # Calcolo metriche di performance
    conclusi = stats["vinti"] + stats["persi"]
    wr = (stats["vinti"] / conclusi * 100) if conclusi > 0 else 0
    pnl_medio = (stats["pnl_netto"] / conclusi) if conclusi > 0 else 0

    # Formattazione del report per Telegram
    report = (
        f"📊 **ANALISI REGRESSO INTEGRALE**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📂 Totale in DB: {len(signals)}\n"
        f"⚙️ Processati: {stats['totale_processati']}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✅ Target Raggiunti: {stats['vinti']}\n"
        f"🛑 Stop Loss Presi: {stats['persi']}\n"
        f"⏳ Posizioni Aperte/Incerte: {stats['aperti']}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📈 **Win Rate: {wr:.2f}%**\n"
        f"💰 **PnL Totale: {stats['pnl_netto']:+.2f}%**\n"
        f"🎯 **Profitto Medio: {pnl_medio:+.2f}%/trade**\n"
    )
    return report

def send_telegram_report(text):
    """Invia il report finale su Telegram"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Errore nell'invio del report a Telegram: {e}")

if __name__ == "__main__":
    print("🛰️ Avvio scansione completa del database...")
    report_finale = analyze_full_backtest()
    print(report_finale)
    send_telegram_report(report_finale)
