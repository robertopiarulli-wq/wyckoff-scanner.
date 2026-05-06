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
    Analizza l'intero regresso dei segnali nel database Supabase.
    Calcola Win Rate e PnL percentuale complessivo.
    """
    # 1. Recupero di TUTTI i segnali (senza .limit)
    # Usiamo l'ordinamento per ID per processare in ordine cronologico
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
            # Mappatura flessibile delle colonne per compatibilità col passato
            sym = s.get('ticker') or s.get('symbol') or s.get('asset')
            entry = s.get('entry') or s.get('prezzo_ingresso') or s.get('lvl')
            tp = s.get('tp') or s.get('take_profit') or s.get('target')
            sl = s.get('sl') or s.get('stop_loss') or s.get('stop')
            
            if not sym or entry is None or tp is None or sl is None:
                continue

            entry, tp, sl = float(entry), float(tp), float(sl)
            stats["totale_processati"] += 1
            
            # Download dati storici (30 giorni per coprire il tempo di vita del segnale)
            # Nota: ^GDAXI invece di GDAXI per evitare errori 404 su Yahoo[cite: 1]
            ticker_yf = sym if not sym.endswith("GDAXI") else "^GDAXI"
            df = yf.download(ticker_yf, period="1mo", interval="1h", progress=False)
            
            if df.empty:
                print(f"⚠️ Dati non trovati per {sym}")
                continue
            
            # Analisi massimi e minimi registrati nel periodo
            high_max = float(df['High'].max().item())
            low_min = float(df['Low'].min().item())
            is_buy = tp > entry
            
            # LOGICA DI VERIFICA ESITO
            if is_buy:
                # Caso Long: prima controlliamo se ha toccato il Target
                if high_max >= tp:
                    stats["vinti"] += 1
                    stats["pnl_netto"] += ((tp - entry) / entry) * 100
                # Poi controlliamo se ha preso lo Stop
                elif low_min <= sl:
                    stats["persi"] += 1
                    stats["pnl_netto"] -= ((entry - sl) / entry) * 100
                else:
                    stats["aperti"] += 1
            else:
                # Caso Short: TP è più basso dell'ingresso
                if low_min <= tp:
                    stats["vinti"] += 1
                    stats["pnl_netto"] += ((entry - tp) / entry) * 100
                elif high_max >= sl:
                    stats["persi"] += 1
                    stats["pnl_netto"] -= ((sl - entry) / entry) * 100
                else:
                    stats["aperti"] += 1
            
            # Piccola pausa per non sovraccaricare le API di Yahoo
            if stats["totale_processati"] % 10 == 0:
                print(f"⏳ Processati {stats['totale_processati']} asset...")
                time.sleep(1)

        except Exception as e:
            print(f"❌ Errore su ID {s.get('id')}: {e}")
            continue

    # Calcolo metriche finali
    conclusi = stats["vinti"] + stats["persi"]
    wr = (stats["vinti"] / conclusi * 100) if conclusi > 0 else 0
    pnl_medio = (stats["pnl_netto"] / conclusi) if conclusi > 0 else 0

    # Formattazione Report Finale
    report = (
        f"📊 **ANALISI REGRESSO COMPLETA**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📂 Segnali in DB: {len(signals)}\n"
        f"⚙️ Analizzati con successo: {stats['totale_processati']}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✅ Target Raggiunti: {stats['vinti']}\n"
        f"🛑 Stop Loss Presi: {stats['persi']}\n"
        f"⏳ Posizioni Incerte: {stats['aperti']}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📈 **Win Rate: {wr:.2f}%**\n"
        f"💰 **PnL Lordo Totale: {stats['pnl_netto']:+.2f}%**\n"
        f"🎯 **Profitto Medio: {pnl_medio:+.2f}%/trade**\n"
    )
    return report

def send_telegram_report(text):
    """Invia il verdetto finale su Telegram"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Errore invio Telegram: {e}")

if __name__ == "__main__":
    print("🛰️ Avvio Backtest Integrale sui dati esistenti...")
    risultato = analyze_full_backtest()
    print(risultato)
    send_telegram_report(risultato)
