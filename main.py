import yfinance as yf
import requests
import os
import mplfinance as mpf
import pandas as pd
import numpy as np
import json
from datetime import datetime
from supabase import create_client

# --- CONFIGURAZIONE ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID') or os.environ.get('TELEGRAM_CHAT_ID')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

# --- PARAMETRI STRATEGIA ---
ALPHA = 0.00729735
MOLTIPLICATORE_QUANTUM = 1.618  
SOGLIA_NOTIFICA = 0.05          
SOGLIA_PANICO_INDICE = -1.50    

sent_alerts = {}

# --- MAPPA ASSET COMPLETA ---
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

def calcola_indicatori(df):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    df['MA20'] = df['Close'].rolling(20).mean()
    df['StdDev'] = df['Close'].rolling(20).std()
    df['UpperB'] = df['MA20'] + (df['StdDev'] * 2)
    df['LowerB'] = df['MA20'] - (df['StdDev'] * 2)
    df['Vol_MA_Short'] = df['Volume'].rolling(3).mean()
    df['Vol_MA_Long'] = df['Volume'].rolling(20).mean()
    hl, hc, lc = df['High']-df['Low'], (df['High']-df['Close'].shift()).abs(), (df['Low']-df['Close'].shift()).abs()
    df['ATR'] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()
    return df

def main():
    is_weekend = datetime.now().weekday() > 4
    cambiamenti = false
    try:
        symbols = [line.strip() for line in open('tickers.txt', 'r') if line.strip() and not line.startswith('#')]
        print(f"🚀 SCANSIONE COMPLETA: {len(symbols)} asset...")
    except: return
    
    lista_nuovi = []
    lista_update = []
    lista_cancella = []

    for t in symbols:
        is_crypto = "-USD" in t
        if is_weekend and not is_crypto: continue

        try:
            df = yf.download(t, period="3mo", interval="4h", progress=False, auto_adjust=True)
            if df.empty or len(df) < 50: continue
            df.columns = [str(c[0] if isinstance(c, tuple) else c).capitalize() for c in df.columns]
            df = calcola_indicatori(df)
            
            p = float(df['Close'].iloc[-1].item())
            h_r = float(df['High'].rolling(100).max().iloc[-1])
            l_r = float(df['Low'].rolling(100).min().iloc[-1])
            range_h = h_r - l_r
            is_acc = p < (h_r + l_r) / 2
            lvl = l_r - (range_h * ALPHA * MOLTIPLICATORE_QUANTUM) if is_acc else h_r + (range_h * ALPHA * MOLTIPLICATORE_QUANTUM)
            dist = abs(p - lvl)/lvl
            
            rsi_val = float(df['RSI'].iloc[-1])
            conf_rsi = (10 <= rsi_val <= 42) if is_acc else (58 <= rsi_val <= 90)
            vol_status = df['Vol_MA_Short'].iloc[-1] < (df['Vol_MA_Long'].iloc[-1] * 1.6)

            d = {
                "t": t, "p": p, "rsi": rsi_val, "dist": dist, "lvl": lvl,
                "tp": lvl + (range_h * 0.85) if is_acc else lvl - (range_h * 0.85),
                "sl": lvl - (df['ATR'].iloc[-1] * 2.5) if is_acc else lvl + (df['ATR'].iloc[-1] * 2.5),
                "fase": "ACCUMULAZIONE" if is_acc else "DISTRIBUZIONE", 
                "azione": "BUY LIMIT" if is_acc else "SELL LIMIT", "df": df,
                "rsi_target": "10-42" if is_acc else "58-90"
            }

            t_clean = t.replace('^', '').split('.')[0]
            check_db = supabase.table("segnali_trading").select("id").eq("ticker", t_clean).eq("stato", "Pendente").execute() if supabase else None
            gia_pendente = bool(check_db and check_db.data)

            # --- NUOVA LOGICA DI SMISTAMENTO (Sostituisce il vecchio blocco) ---
            if dist < SOGLIA_NOTIFICA and conf_rsi and vol_status:
                if not gia_pendente:
                    lista_nuovi.append(d)
                    if supabase: 
                        supabase.table("segnali_trading").insert({
                            "ticker": t_clean, "fase": d['fase'], "stato": "Pendente", 
                            "prezzo_ingresso": round(lvl, 5), "tp": round(d['tp'], 5), "sl": round(d['sl'], 5)
                        }).execute()
                    cambiamenti = True
                # NOTA: Qui il Re-update è stato eliminato (non facciamo nulla se è già pendente e i filtri sono OK)
            
            elif gia_pendente:
                # Recuperiamo i dati dal DB per il controllo inversione
                info_db = check_db.data[0]
                # CHIUDI SE: La fase è cambiata (Inversione) O il prezzo è troppo lontano
                if info_db.get('fase') != fase_attuale or dist > (SOGLIA_NOTIFICA * 1.5):
                    d['motivo'] = "Inversione Fase" if info_db.get('fase') != fase_attuale else "Prezzo Lontano"
                    lista_cancella.append(d)
                    if supabase: 
                        supabase.table("segnali_trading").update({"stato": "Annullato"}).eq("ticker", t_clean).execute()
                    cambiamenti = True
        except: continue

    # FUNZIONE INVIO TELEGRAM MIGLIORATA
    def invia_telegram(d, header, show_filters=True):
        asset_info = MAPPA_ASSET.get(d['t'], {"cat": "📊 ASSET", "tv": d['t']})
        tv_link = f"https://it.tradingview.com/chart/?symbol={asset_info['tv']}"
        directa_link = "https://www.directatrading.com/app/" # Aggiunto Link Directa
        
        msg = (f"{header}\n"
               f"{asset_info['cat']} | 🎯 <b>{d['azione']}</b>\n"
               f"----------------------------------\n"
               f"<b>Asset:</b> <code>{d['t']}</code>\n"
               f"<b>Fase:</b> {d['fase']}\n\n"
               f"🔵 <b>ENTRY: {d['lvl']:.4f}</b>\n"
               f"🟢 <b>TP: {d['tp']:.4f}</b>\n"
               f"🔴 <b>SL: {d['sl']:.4f}</b>\n\n")
        
        if show_filters:
            msg += (f"🛡️ <b>STATUS:</b>\n"
                    f"✅ RSI: {d['rsi']:.1f}\n"
                    f"✅ Volumi: OK\n\n")
        elif 'motivo' in d: # Aggiunta gestione motivo chiusura
            msg += f"❗ <b>MOTIVO:</b> {d['motivo']}\n\n"
        
        msg += f"🔗 <a href='{tv_link}'>TradingView</a> | <a href='{directa_link}'>Directa</a>"
        # ... resto del codice del grafico (invariato)

        plot_data = d['df'].iloc[-50:]
        ap = [mpf.make_addplot(plot_data['UpperB'], color='gray', alpha=0.3), mpf.make_addplot(plot_data['LowerB'], color='gray', alpha=0.3)]
        mpf.plot(plot_data, type='candle', style='charles', addplot=ap, savefig='p.png', 
                 hlines=dict(hlines=[d['lvl'], d['tp'], d['sl']], colors=['blue', 'green', 'red'], linestyle='-.'))
        
        with open('p.png', 'rb') as f:
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendPhoto", 
                          files={'photo': f}, data={'chat_id': CHAT_ID, 'caption': msg, 'parse_mode': 'HTML'})

   # Invio alert singoli
    for d in lista_nuovi: invia_telegram(d, "🆕 <b>NUOVO ALERT</b>")
    for d in lista_cancella: invia_telegram(d, "⚠️ <b>ORDINE CHIUSO</b>", show_filters=False)

    # REPORT POSIZIONI (Solo se ci sono stati cambiamenti)
    if cambiamenti and supabase:
        res = supabase.table("segnali_trading").select("*").eq("stato", "Pendente").execute()
        limit_txt, live_txt = [], []
        
        for p in res.data:
            t_orig = next((k for k in MAPPA_ASSET if k.replace('^','').split('.')[0] == p['ticker']), p['ticker'])
            last_df = yf.download(t_orig, period="1d", progress=False)
            last_p = last_df['Close'].iloc[-1].item()
            link = f"<a href='https://it.tradingview.com/chart/?symbol={MAPPA_ASSET.get(t_orig, {'tv': p['ticker']})['tv']}'>📈</a>"
            linea = f"{link} <code>{p['ticker']}</code> @ {p['prezzo_ingresso']}"
            
            # Controllo se l'ordine è LIVE (prezzo ha toccato o superato l'entry)
            if (p['fase'] == "ACCUMULAZIONE" and last_p <= p['prezzo_ingresso']) or \
               (p['fase'] == "DISTRIBUZIONE" and last_p >= p['prezzo_ingresso']):
                live_txt.append(linea)
            else:
                limit_txt.append(linea)

        report = "📊 <b>REPORT POSIZIONI ATTIVE</b>\n\n⏳ <b>LIMIT:</b>\n" + ("\n".join(limit_txt) if limit_txt else "Nessuna")
        report += "\n\n🚀 <b>LIVE:</b>\n" + ("\n".join(live_txt) if live_txt else "Nessuna")
        
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                      data={'chat_id': CHAT_ID, 'text': report, 'parse_mode': 'HTML', 'disable_web_page_preview': True})
if __name__ == "__main__":
    main()
