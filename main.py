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

# --- PARAMETRI STRATEGIA (MASSIMA AZIONE) ---
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

    try:
        symbols = [line.strip() for line in open('tickers.txt', 'r') if line.strip() and not line.startswith('#')]
        print(f"🚀 SCANSIONE COMPLETA: {len(symbols)} asset...")
    except: return
    
    cache = {}
    for t in symbols:
        is_crypto = "-USD" in t
        if is_weekend and not is_crypto:
            continue

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
            
            rsi_val = float(df['RSI'].iloc[-1])
            if is_acc:
                conf_rsi = (10 <= rsi_val <= 42)
                rsi_target, azione = "10-42", "BUY LIMIT"
            else:
                conf_rsi = (58 <= rsi_val <= 90)
                rsi_target, azione = "58-90", "SELL LIMIT"
            
            vol_status = df['Vol_MA_Short'].iloc[-1] < (df['Vol_MA_Long'].iloc[-1] * 1.6)

            cache[t] = {
                "p": p, "rsi": rsi_val, "dist": abs(p - lvl)/lvl, "lvl": lvl,
                "tp": lvl + (range_h * 0.85) if is_acc else lvl - (range_h * 0.85),
                "sl": lvl - (df['ATR'].iloc[-1] * 2.5) if is_acc else lvl + (df['ATR'].iloc[-1] * 2.5),
                "fase": "ACCUMULAZIONE" if is_acc else "DISTRIBUZIONE", 
                "vol_status": vol_status, "conf_rsi": conf_rsi, "rsi_target": rsi_target,
                "azione": azione, "df": df
            }
        except: continue

    for t, d in cache.items():
        if d['dist'] < SOGLIA_NOTIFICA and d['conf_rsi'] and d['vol_status']:
            alert_id = f"{t}_{d['azione']}_{datetime.now().strftime('%Y%m%d_%H')}"
            if alert_id in sent_alerts: continue

            indice_ticker = CORRELAZIONI.get(t)
            idx_perf = 0.0
            info_indice = ""
            if indice_ticker:
                try:
                    idx_df = yf.download(indice_ticker, period="1d", progress=False)
                    idx_now, idx_prev = float(idx_df['Close'].iloc[-1]), float(idx_df['Open'].iloc[-1])
                    idx_perf = ((idx_now / idx_prev) - 1) * 100
                    info_indice = f"📊 <b>INDICE REF ({indice_ticker}):</b> {idx_now:.2f} ({idx_perf:+.2f}%)\n"
                except: info_indice = "⚠️ Errore indice rif.\n"

            if idx_perf < SOGLIA_PANICO_INDICE: continue

            # --- NUOVA LOGICA: DISTINZIONE NUOVO ALERT / RE-UPDATE ---
            is_new_alert = True
            if supabase:
                try:
                    t_clean = t.replace('^', '').split('.')[0]
                    # Controlla se l'asset è già "Pendente" nel database
                    check = supabase.table("segnali_trading").select("id").eq("ticker", t_clean).eq("stato", "Pendente").execute()
                    
                    if check.data:
                        # Se esiste già, marchiamo come RE-UPDATE e NON inseriamo nel DB (anti-doppione)
                        is_new_alert = False
                    else:
                        # Se NON esiste, è un NUOVO ALERT e lo inseriamo
                        supabase.table("segnali_trading").insert({
                            "ticker": t_clean, "fase": d['fase'], "stato": "Pendente", 
                            "prezzo_ingresso": round(d['lvl'], 5), "tp": round(d['tp'], 5), 
                            "sl": round(d['sl'], 5), "distanza_minima_raggiunta": round(d['dist'], 5)
                        }).execute()
                except: pass

            header = "🆕 <b>NUOVO ALERT</b>" if is_new_alert else "🔄 <b>RE-UPDATE ALERT</b>"
            asset_info = MAPPA_ASSET.get(t, {"cat": "📊 ASSET", "tv": t, "dir": t})
            tv_link = f"https://it.tradingview.com/chart/?symbol={asset_info['tv']}"
            check_idx = "✅" if (not indice_ticker or idx_perf > SOGLIA_PANICO_INDICE) else "⚠️"

            msg = (f"{header}\n"
                   f"{asset_info['cat']} | 🎯 <b>SEGNALE GOLD</b>\n"
                   f"{info_indice}\n"
                   f"<b>Asset:</b> <code>{t}</code> (TV: <b>{asset_info['tv']}</b>)\n"
                   f"<b>Azione:</b> <code>{d['azione']}</code>\n"
                   f"<b>Fase:</b> {d['fase']}\n\n"
                   f"🔵 <b>ENTRY: {d['lvl']:.4f}</b>\n"
                   f"🟢 <b>TP: {d['tp']:.4f}</b>\n"
                   f"🔴 <b>SL: {d['sl']:.4f}</b>\n\n"
                   f"🛡️ <b>FILTRI ATTIVI:</b>\n"
                   f"✅ <b>RSI ({d['rsi_target']}):</b> {d['rsi']:.1f}\n"
                   f"✅ <b>Volumi:</b> Esaurimento OK\n"
                   f"{check_idx} <b>Sentiment Indice:</b> Stabile\n\n"
                   f"🔗 <a href='{tv_link}'>TradingView</a> | <a href='https://www.directatrading.com/app/'>Directa</a>")

            plot_data = d['df'].iloc[-50:]
            ap = [mpf.make_addplot(plot_data['UpperB'], color='gray', alpha=0.3), mpf.make_addplot(plot_data['LowerB'], color='gray', alpha=0.3)]
            mpf.plot(plot_data, type='candle', style='charles', addplot=ap, savefig='p.png', 
                     hlines=dict(hlines=[d['lvl'], d['tp'], d['sl']], colors=['blue', 'green', 'red'], linestyle='-.'))
            
            with open('p.png', 'rb') as f:
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendPhoto", 
                              files={'photo': f}, data={'chat_id': CHAT_ID, 'caption': msg, 'parse_mode': 'HTML'})
            
            sent_alerts[alert_id] = True

if __name__ == "__main__":
    main()
