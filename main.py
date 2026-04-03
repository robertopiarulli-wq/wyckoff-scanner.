import yfinance as yf
import requests
import os
import mplfinance as mpf
import pandas as pd
import numpy as np
from datetime import datetime
from supabase import create_client

# --- CONFIGURAZIONE ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID') or os.environ.get('TELEGRAM_CHAT_ID')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

# --- PARAMETRI STRATEGIA (Da main 27) ---
ALPHA = 0.00729735
MOLTIPLICATORE_QUANTUM = 1.200  
SOGLIA_NOTIFICA = 0.05          
SOGLIA_PANICO_INDICE = -1.50    

# --- MAPPA ASSET INTEGRALE (RIPRISTINATA DA MAIN 27) ---
MAPPA_ASSET = {
    "^GSPC": {"cat": "📈 INDICE USA", "tv": "SPX", "dir": "CSSPX"},
    "^NDX":  {"cat": "📈 INDICE TECH", "tv": "IXIC", "dir": "ANX"},
    "^GDAXI": {"cat": "📈 INDICE DAX", "tv": "GER40", "dir": "DAX"},
    "FTSEMIB.MI": {"cat": "📈 INDICE MIB", "tv": "FTSEMIB", "dir": "FIB"},
    "CSSPX.MI": {"cat": "🇮🇹 ETF S&P500", "tv": "MIL:CSSPX", "dir": "CSSPX"},
    "ANX.MI": {"cat": "🇮🇹 ETF NASDAQ", "tv": "MIL:ANX", "dir": "ANX"},
    "SWDA.MI": {"cat": "🌍 ETF WORLD", "tv": "MIL:SWDA", "dir": "SWDA"},
    "AAPL": {"cat": "🍎 TECH (APPLE)", "tv": "AAPL", "dir": "AAPL"},
    "NVDA": {"cat": "🤖 TECH (NVIDIA)", "tv": "NVDA", "dir": "NVDA"},
    "TSLA": {"cat": "⚡ TECH (TESLA)", "tv": "TSLA", "dir": "TSLA"},
    "AMZN": {"cat": "📦 TECH (AMAZON)", "tv": "AMZN", "dir": "AMZN"},
    "META": {"cat": "📱 TECH (META)", "tv": "META", "dir": "META"},
    "MSFT": {"cat": "💻 TECH (MICROSOFT)", "tv": "MSFT", "dir": "MSFT"},
    "GOOGL": {"cat": "🔍 TECH (GOOGLE)", "tv": "GOOGL", "dir": "GOOGL"},
    "AVGO": {"cat": "🔌 TECH (BROADCOM)", "tv": "AVGO", "dir": "AVGO"},
    "ASML": {"cat": "🔬 TECH (ASML)", "tv": "ASML", "dir": "ASML"},
    "XLF": {"cat": "🏦 SECTOR (FINANCE)", "tv": "XLF", "dir": "XLF"},
    "XLE": {"cat": "🛢️ SECTOR (ENERGY)", "tv": "XLE", "dir": "XLE"},
    "XLV": {"cat": "💊 SECTOR (HEALTH)", "tv": "XLV", "dir": "XLV"},
    "SMH": {"cat": "💾 SECTOR (CHIPS)", "tv": "SMH", "dir": "SMH"},
    "IWM": {"cat": "🚜 SMALL CAPS", "tv": "IWM", "dir": "IWM"},
    "QQQ": {"cat": "📊 NASDAQ 100 ETF", "tv": "QQQ", "dir": "QQQ"},
    "GC=F": {"cat": "⛏️ METALS (GOLD)", "tv": "GOLD", "dir": "SGLD"},
    "SI=F": {"cat": "⛏️ METALS (SILVER)", "tv": "SILVER", "dir": "PHAG"},
    "CL=F": {"cat": "🛢️ ENERGY (OIL)", "tv": "USOIL", "dir": "CRUD"},
    "NG=F": {"cat": "🔥 ENERGY (GAS)", "tv": "NATGAS", "dir": "NG"},
    "KC=F": {"cat": "☕ SOFT (COFFEE)", "tv": "KC1!", "dir": "KC"},
    "SB=F": {"cat": "🍭 SOFT (SUGAR)", "tv": "SB1!", "dir": "SB"},
    "HG=F": {"cat": "🏗️ METALS (COPPER)", "tv": "COPPER", "dir": "HG"},
    "BTC-USD": {"cat": "🌐 CRYPTO (BTC)", "tv": "BTCUSD", "dir": "BTC"},
    "ETH-USD": {"cat": "🌐 CRYPTO (ETH)", "tv": "ETHUSD", "dir": "ETH"},
    "SOL-USD": {"cat": "🌐 CRYPTO (SOL)", "tv": "SOLUSD", "dir": "SOL"},
    "ADA-USD": {"cat": "🌐 CRYPTO (ADA)", "tv": "ADAUSD", "dir": "ADA"},
    "DOT-USD": {"cat": "🌐 CRYPTO (DOT)", "tv": "DOTUSD", "dir": "DOT"},
    "AVAX-USD": {"cat": "🌐 CRYPTO (AVAX)", "tv": "AVAXUSD", "dir": "AVAX"},
    "LINK-USD": {"cat": "🌐 CRYPTO (LINK)", "tv": "LINKUSD", "dir": "LINK"},
    "XRP-USD": {"cat": "🌐 CRYPTO (XRP)", "tv": "XRPUSD", "dir": "XRP"},
    "KO": {"cat": "🥤 VALUE (COCA COLA)", "tv": "KO", "dir": "KO"},
    "PEP": {"cat": "🍿 VALUE (PEPSICO)", "tv": "PEP", "dir": "PEP"},
    "PG": {"cat": "🧼 VALUE (P&G)", "tv": "PG", "dir": "PG"},
    "JNJ": {"cat": "🩺 VALUE (J&J)", "tv": "JNJ", "dir": "JNJ"},
    "EURUSD=X": {"cat": "💱 FOREX (EUR/USD)", "tv": "EURUSD", "dir": "EURUSD"},
    "GBPUSD=X": {"cat": "💱 FOREX (GBP/USD)", "tv": "GBPUSD", "dir": "GBPUSD"}
}

CORRELAZIONI = {
    "CSSPX.MI": "^GSPC", "ANX.MI": "^NDX", "SWDA.MI": "^GSPC", 
    "AAPL": "^NDX", "NVDA": "^NDX", "TSLA": "^NDX", "AMZN": "^NDX",
    "META": "^NDX", "MSFT": "^NDX", "GOOGL": "^NDX", "SMH": "^NDX",
    "SGLD.MI": "GC=F", "PHAG.MI": "SI=F", "CRUD.MI": "CL=F",
    "ETH-USD": "BTC-USD", "SOL-USD": "BTC-USD", "ADA-USD": "BTC-USD"
}

def main():
    is_weekend = datetime.now().weekday() > 4
    try:
        symbols = [line.strip() for line in open('tickers.txt', 'r') if line.strip() and not line.startswith('#')]
    except: return
    
    lista_nuovi, lista_cancella = [], [] # Rimosso lista_update per eliminare msg ridondanti
    cambiamenti = False

    for t in symbols:
        if is_weekend and "-USD" not in t: continue
        try:
            df = yf.download(t, period="3mo", interval="4h", progress=False, auto_adjust=True)
            if df.empty or len(df) < 50: continue
            df.columns = [str(c[0] if isinstance(c, tuple) else c).capitalize() for c in df.columns]
            
            p = float(df['Close'].iloc[-1].item())
            h_r, l_r = float(df['High'].rolling(100).max().iloc[-1]), float(df['Low'].rolling(100).min().iloc[-1])
            range_h = h_r - l_r
            is_acc = p < (h_r + l_r) / 2
            fase_attuale = "ACCUMULAZIONE" if is_acc else "DISTRIBUZIONE"
            lvl = l_r - (range_h * ALPHA * MOLTIPLICATORE_QUANTUM) if is_acc else h_r + (range_h * ALPHA * MOLTIPLICATORE_QUANTUM)
            dist = abs(p - lvl)/lvl
            t_clean = t.replace('^', '').split('.')[0]

            # Sentiment Indice
            idx_perf = 0.0
            indice_ticker = CORRELAZIONI.get(t)
            if indice_ticker:
                idx_df = yf.download(indice_ticker, period="1d", progress=False)
                idx_perf = ((idx_df['Close'].iloc[-1] / idx_df['Open'].iloc[-1]) - 1) * 100

            check_db = supabase.table("segnali_trading").select("*").eq("ticker", t_clean).eq("stato", "Pendente").execute() if supabase else None
            gia_pendente = bool(check_db and check_db.data)

            # 1. NUOVI ALERT (Solo se non gia in DB)
            if dist < SOGLIA_NOTIFICA and not gia_pendente and idx_perf > SOGLIA_PANICO_INDICE:
                lista_nuovi.append({"t": t, "lvl": lvl, "fase": fase_attuale, "idx_perf": idx_perf, "df": df})
                if supabase: supabase.table("segnali_trading").insert({
                    "ticker": t_clean, "fase": fase_attuale, "stato": "Pendente", "prezzo_ingresso": round(lvl, 5)
                }).execute()
                cambiamenti = True

            # 2. CHIUSURA/CANCELLAZIONE (Inversione fase o troppo lontano)
            elif gia_pendente:
                info_db = check_db.data[0]
                if info_db['fase'] != fase_attuale or dist > (SOGLIA_NOTIFICA * 1.5) or idx_perf < SOGLIA_PANICO_INDICE:
                    motivo = "Inversione Fase" if info_db['fase'] != fase_attuale else "Fuori Target/Panico"
                    lista_cancella.append({"t": t, "motivo": motivo, "fase": fase_attuale, "df": df, "lvl": lvl})
                    if supabase: supabase.table("segnali_trading").update({"stato": "Chiuso"}).eq("ticker", t_clean).execute()
                    cambiamenti = True
        except: continue

    # INVIO TELEGRAM (Solo Nuovi o Cancellati - Niente Update)
    def invia(d, h, show_filters=True):
        asset = MAPPA_ASSET.get(d['t'], {"cat": "📊 ASSET", "tv": d['t']})
        msg = f"{h}\n{asset['cat']} | <b>{d['t']}</b>\nFase: {d['fase']}\nENTRY: {d['lvl']:.4f}\n"
        if show_filters: msg += f"Sentiment: {d['idx_perf']:+.2f}%\n"
        msg += f"🔗 <a href='https://it.tradingview.com/chart/?symbol={asset['tv']}'>TV</a> | <a href='https://www.directatrading.com/app/'>Directa</a>"
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML', 'disable_web_page_preview': True})

    for d in lista_nuovi: invia(d, "🆕 <b>NUOVO ALERT</b>")
    for d in lista_cancella: invia(d, f"⚠️ <b>CHIUDI/CANCELLA ({d['motivo']})</b>", False)

    # REPORT POSIZIONI ATTIVE (Con link e distinzione LIMIT/LIVE)
    if cambiamenti and supabase:
        res = supabase.table("segnali_trading").select("*").eq("stato", "Pendente").execute()
        limit_txt, live_txt = [], []
        
        for p in res.data:
            # Recupero ticker originale per il check prezzo live
            t_orig = next((k for k in MAPPA_ASSET if k.replace('^','').split('.')[0] == p['ticker']), p['ticker'])
            last_p = yf.download(t_orig, period="1d", progress=False)['Close'].iloc[-1]
            
            link = f"<a href='https://it.tradingview.com/chart/?symbol={MAPPA_ASSET.get(t_orig, {'tv': p['ticker']})['tv']}'>📈</a>"
            linea = f"{link} <code>{p['ticker']}</code> ({p['fase']}) @ {p['prezzo_ingresso']}"
            
            # Verifica se il prezzo ha raggiunto il livello (LIVE) o è ancora in attesa (LIMIT)
            is_live = (p['fase'] == "ACCUMULAZIONE" and last_p <= p['prezzo_ingresso']) or \
                      (p['fase'] == "DISTRIBUZIONE" and last_p >= p['prezzo_ingresso'])
            
            if is_live: live_txt.append(linea)
            else: limit_txt.append(linea)

        report = "📊 <b>REPORT POSIZIONI ATTIVE</b>\n\n"
        report += "⏳ <b>LIMIT (IN ATTESA):</b>\n" + ("\n".join(limit_txt) if limit_txt else "Nessuna")
        report += "\n\n🚀 <b>LIVE (ESEGUITE):</b>\n" + ("\n".join(live_txt) if live_txt else "Nessuna")
        
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={'chat_id': CHAT_ID, 'text': report, 'parse_mode': 'HTML', 'disable_web_page_preview': True})

if __name__ == "__main__":
    main()
