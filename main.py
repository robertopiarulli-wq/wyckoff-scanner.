import yfinance as yf
import requests
import os
import mplfinance as mpf
import pandas as pd
import numpy as np
from datetime import datetime
from supabase import create_client
import io

# --- CONFIGURAZIONE ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID') or os.environ.get('TELEGRAM_CHAT_ID')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

ALPHA = 0.00729735
MOLTIPLICATORE_QUANTUM = 1.618  
SOGLIA_NOTIFICA = 0.05          # 5% per attivare alert
SOGLIA_CHIUSURA = 0.08          # 8% per invalidare ordine se il prezzo scappa

# --- MAPPA ASSET COMPLETA ---
MAPPA_ASSET = {
    "^GSPC": {"cat": "📈 INDICE USA (S&P500)", "tv": "CME_MINI:ES1!"},
    "^NDX":  {"cat": "📈 INDICE TECH (NAS100)", "tv": "CME_MINI:NQ1!"},
    "^GDAXI": {"cat": "📈 INDICE DAX", "tv": "EUREX:FDAX1!"},
    "FTSEMIB.MI": {"cat": "📈 INDICE MIB", "tv": "INDEX:FTSEMIB"},
    "DIA": {"cat": "📈 INDICE DOW JONES", "tv": "CBOT:YM1!"},
    "CSSPX.MI": {"cat": "🇮🇹 ETF S&P500", "tv": "MIL:CSSPX"},
    "ANX.MI": {"cat": "🇮🇹 ETF NASDAQ", "tv": "MIL:ANX"},
    "SWDA.MI": {"cat": "🌍 ETF WORLD", "tv": "MIL:SWDA"},
    "QQQ": {"cat": "📊 NASDAQ 100 ETF", "tv": "NASDAQ:QQQ"},
    "IWM": {"cat": "🚜 SMALL CAPS ETF", "tv": "AMEX:IWM"},
    "AAPL": {"cat": "🍎 APPLE", "tv": "NASDAQ:AAPL"},
    "NVDA": {"cat": "🤖 NVIDIA", "tv": "NASDAQ:NVDA"},
    "TSLA": {"cat": "⚡ TESLA", "tv": "NASDAQ:TSLA"},
    "AMZN": {"cat": "📦 AMAZON", "tv": "NASDAQ:AMZN"},
    "META": {"cat": "📱 META", "tv": "NASDAQ:META"},
    "MSFT": {"cat": "💻 MICROSOFT", "tv": "NASDAQ:MSFT"},
    "GOOGL": {"cat": "🔍 GOOGLE", "tv": "NASDAQ:GOOGL"},
    "AVGO": {"cat": "🔌 BROADCOM", "tv": "NASDAQ:AVGO"},
    "ASML": {"cat": "🔬 ASML", "tv": "NASDAQ:ASML"},
    "SMH": {"cat": "💾 CHIPS SECTOR", "tv": "AMEX:SMH"},
    "XLF": {"cat": "🏦 FINANCE SECTOR", "tv": "AMEX:XLF"},
    "XLE": {"cat": "🛢️ ENERGY SECTOR", "tv": "AMEX:XLE"},
    "XLV": {"cat": "💊 HEALTH SECTOR", "tv": "AMEX:XLV"},
    "KO": {"cat": "🥤 COCA COLA", "tv": "NYSE:KO"},
    "PEP": {"cat": "🍿 PEPSICO", "tv": "NASDAQ:PEP"},
    "PG": {"cat": "🧼 PROCTER & GAMBLE", "tv": "NYSE:PG"},
    "JNJ": {"cat": "🩺 JOHNSON & JOHNSON", "tv": "NYSE:JNJ"},
    "GC=F": {"cat": "⛏️ GOLD", "tv": "COMEX:GC1!"},
    "SI=F": {"cat": "⛏️ SILVER", "tv": "COMEX:SI1!"},
    "HG=F": {"cat": "🏗️ COPPER", "tv": "COMEX:HG1!"},
    "PL=F": {"cat": "💍 PLATINUM", "tv": "NYMEX:PL1!"},
    "CL=F": {"cat": "🛢️ CRUDE OIL", "tv": "NYMEX:CL1!"},
    "NG=F": {"cat": "🔥 NATGAS", "tv": "NYMEX:NG1!"},
    "KC=F": {"cat": "☕ COFFEE", "tv": "ICEUS:KC1!"},
    "SB=F": {"cat": "🍭 SUGAR", "tv": "ICEUS:SB1!"},
    "ZW=F": {"cat": "🌾 WHEAT (GRANO)", "tv": "CBOT:ZW1!"},
    "ZS=F": {"cat": "🌱 SOYBEANS (SOIA)", "tv": "CBOT:ZS1!"},
    "BTC-USD": {"cat": "🌐 BITCOIN", "tv": "BINANCE:BTCUSDT"},
    "ETH-USD": {"cat": "🌐 ETHEREUM", "tv": "BINANCE:ETHUSDT"},
    "SOL-USD": {"cat": "🌐 SOLANA", "tv": "BINANCE:SOLUSDT"},
    "ADA-USD": {"cat": "🌐 CARDANO", "tv": "BINANCE:ADAUSDT"},
    "DOT-USD": {"cat": "🌐 POLKADOT", "tv": "BINANCE:DOTUSDT"},
    "AVAX-USD": {"cat": "🌐 AVAX", "tv": "BINANCE:AVAXUSDT"},
    "LINK-USD": {"cat": "🌐 CHAINLINK", "tv": "BINANCE:LINKUSDT"},
    "XRP-USD": {"cat": "🌐 RIPPLE", "tv": "BINANCE:XRPUSDT"},
    "EURUSD=X": {"cat": "💱 EUR/USD", "tv": "FX:EURUSD"},
    "GBPUSD=X": {"cat": "💱 GBP/USD", "tv": "FX:GBPUSD"}
}

def calcola_indicatori(df):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    df['MA20_Vol'] = df['Volume'].rolling(20).mean()
    hl, hc, lc = df['High'] - df['Low'], (df['High'] - df['Close'].shift()).abs(), (df['Low'] - df['Close'].shift()).abs()
    df['ATR'] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()
    return df

def crea_grafico(df, t, lvl):
    buf = io.BytesIO()
    data_to_plot = df.tail(40).copy()
    mpf.plot(data_to_plot, type='candle', style='charles',
             hlines=dict(hlines=[lvl], colors=['blue'], linestyle='--'),
             savefig=dict(fname=buf, format='png'))
    buf.seek(0)
    return buf

def main():
    is_weekend = datetime.now().weekday() > 4
    try:
        with open('tickers.txt', 'r') as f:
            symbols = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except: return

    report_pendenti = []
    nuovi_alert_count = 0

    for t in symbols:
        if is_weekend and "-USD" not in t: continue
        try:
            df = yf.download(t, period="1y", interval="4h", progress=False, auto_adjust=True)
            if df.empty or len(df) < 140: continue
            df.columns = [str(c[0] if isinstance(c, tuple) else c).capitalize() for c in df.columns]
            df = calcola_indicatori(df)
            
            p_attuale = float(df['Close'].iloc[-1].item())
            h_r, l_r = float(df['High'].rolling(137).max().iloc[-1]), float(df['Low'].rolling(137).min().iloc[-1])
            range_h = h_r - l_r
            rsi_val = df['RSI'].iloc[-1]
            vol_attuale = df['Volume'].iloc[-1]
            vol_ma = df['MA20_Vol'].iloc[-1]
            
            is_acc = p_attuale < (h_r + l_r) / 2
            lvl_entry = l_r - (range_h * ALPHA * MOLTIPLICATORE_QUANTUM) if is_acc else h_r + (range_h * ALPHA * MOLTIPLICATORE_QUANTUM)
            distanza = abs(p_attuale - lvl_entry) / lvl_entry
            t_db = t.replace('^', '').split('.')[0].strip()

            # --- 1. GESTIONE POSIZIONI ESISTENTI (CHIUSURA) ---
            check = supabase.table("segnali_trading").select("*").eq("ticker", t_db).eq("stato", "Pendente").execute()
            
            if check.data:
                p = check.data[0]
                chiudi, motivo = False, ""
                
                if is_acc: # Logica Long
                    if p_attuale >= p['tp']: chiudi, motivo = True, "🎯 TARGET RAGGIUNTO"
                    elif p_attuale <= p['sl']: chiudi, motivo = True, "🛑 STOP LOSS PRESO"
                    elif distanza > SOGLIA_CHIUSURA: chiudi, motivo = True, "📐 INVALIDATO (LONTANO)"
                else: # Logica Short
                    if p_attuale <= p['tp']: chiudi, motivo = True, "🎯 TARGET RAGGIUNTO"
                    elif p_attuale >= p['sl']: chiudi, motivo = True, "🛑 STOP LOSS PRESO"
                    elif distanza > SOGLIA_CHIUSURA: chiudi, motivo = True, "📐 INVALIDATO (LONTANO)"
                
                if chiudi:
                    supabase.table("segnali_trading").update({"stato": "Chiuso"}).eq("ticker", t_db).execute()
                    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                                 params={'chat_id': CHAT_ID, 'text': f"🚩 <b>POSIZIONE CHIUSA</b>\n<b>{t_db}</b>: {motivo}", 'parse_mode': 'HTML'})
                else:
                    report_pendenti.append(f"⏳ {t_db}: In attesa @ {p['prezzo_ingresso']}")

            # --- 2. RICERCA NUOVI ALERT (Solo se non pendente) ---
            else:
                vol_confermato = vol_attuale > (vol_ma * 1.5)
                fase_attiva = False
                wyckoff_db = ""
                
                if is_acc and distanza < SOGLIA_NOTIFICA and vol_confermato and (35 <= rsi_val <= 55):
                    fase_attiva, wyckoff_db = True, "ACCUMULAZIONE (SOS)"
                elif not is_acc and distanza < SOGLIA_NOTIFICA and vol_confermato and (45 <= rsi_val <= 65):
                    fase_attiva, wyckoff_db = True, "DISTRIBUZIONE (SOW)"

                if fase_attiva:
                    tp = lvl_entry + (range_h * 0.7) if is_acc else lvl_entry - (range_h * 0.7)
                    sl = lvl_entry - (df['ATR'].iloc[-1]*2) if is_acc else lvl_entry + (df['ATR'].iloc[-1]*2)
                    
                    supabase.table("segnali_trading").insert({
                        "ticker": t_db, "fase": wyckoff_db, "fase": wyckoff_db, "stato": "Pendente", 
                        "prezzo_ingresso": round(lvl_entry, 5), "tp": round(tp, 5), "sl": round(sl, 5), "rsi": round(rsi_val, 2)
                    }).execute()
                    
                    asset = MAPPA_ASSET.get(t, {"cat": "📊 ASSET", "tv": t})
                    chart = crea_grafico(df, t, lvl_entry)
                    msg = (f"🚀 <b>NUOVO ALERT</b>\n"
                           f"━━━━━━━━━━━━━━━\n"
                           f"📦 <b>Stato:</b> {wyckoff_db}\n"
                           f"📈 <b>Asset:</b> {asset['cat']} ({t})\n"
                           f"🔵 <b>Ordine:</b> {'BUY LIMIT' if is_acc else 'SELL LIMIT'}\n"
                           f"💸 <b>Entry:</b> {lvl_entry:.4f}\n"
                           f"🟢 <b>Target:</b> {tp:.4f} | 🔴 <b>Stop:</b> {sl:.4f}\n"
                           f"━━━━━━━━━━━━━━━\n"
                           f"🔗 <a href='https://it.tradingview.com/chart/?symbol={asset['tv']}'>TradingView</a>")
                    
                    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendPhoto", 
                                 params={'chat_id': CHAT_ID, 'caption': msg, 'parse_mode': 'HTML'}, 
                                 files={'photo': chart})
                    nuovi_alert_count += 1

        except Exception as e: print(f"❌ Errore {t}: {e}")

    # --- 3. RIEPILOGO CICLO FINALE ---
    testo_report = "📊 <b>RIEPILOGO SCANSIONE</b>\n━━━━━━━━━━━━━━━\n"
    testo_report += f"🆕 Nuovi Alert: {nuovi_alert_count}\n"
    
    if report_pendenti:
        testo_report += "\n<b>ORDINI ATTIVI:</b>\n" + "\n".join(report_pendenti)
    else:
        testo_report += "\n📭 Nessun ordine pendente."
        
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                 params={'chat_id': CHAT_ID, 'text': testo_report, 'parse_mode': 'HTML', 'disable_web_page_preview': True})

if __name__ == "__main__":
    main()
