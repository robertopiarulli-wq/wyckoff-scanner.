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

# Parametri Strategia (Quantum Alpha)
ALPHA = 0.00729735
MOLTIPLICATORE_QUANTUM = 2.618 
SOGLIA_NOTIFICA = 0.02
SOGLIA_PANICO_INDICE = -1.25 

# --- MAPPA ASSET PROFESSIONALE (Yahoo -> TradingView -> Directa/MT5) ---
MAPPA_ASSET = {
    "^GSPC": {"cat": "📈 INDICE USA (S&P500)", "tv": "SPX", "dir": "CSSPX"},
    "^NDX":  {"cat": "📈 INDICE TECH (NASDAQ)", "tv": "IXIC", "dir": "ANX"},
    "^GDAXI": {"cat": "📈 INDICE DAX", "tv": "GER40", "dir": "DAX"},
    "FTSEMIB.MI": {"cat": "📈 INDICE MIB", "tv": "FTSEMIB", "dir": "FIB"},
    "GC=F": {"cat": "⛏️ METALS (ORO)", "tv": "GOLD", "dir": "SGLD"},
    "SI=F": {"cat": "⛏️ METALS (ARGENTO)", "tv": "SILVER", "dir": "PHAG"},
    "CL=F": {"cat": "🛢️ ENERGY (CRUDE OIL)", "tv": "USOIL", "dir": "CRUD"},
    "NG=F": {"cat": "🔥 ENERGY (NATURAL GAS)", "tv": "NATGAS", "dir": "NG"},
    "KC=F": {"cat": "☕ SOFT (CAFFÈ)", "tv": "KC1!", "dir": "KC"},
    "SB=F": {"cat": "🍭 SOFT (ZUCCHERO)", "tv": "SB1!", "dir": "SB"},
    "CSSPX.MI": {"cat": "🇮🇹 ETF S&P500", "tv": "MIL:CSSPX", "dir": "CSSPX"},
    "ANX.MI": {"cat": "🇮🇹 ETF NASDAQ", "tv": "MIL:ANX", "dir": "ANX"},
    "SGLD.MI": {"cat": "⛏️ ETC ORO", "tv": "MIL:SGLD", "dir": "SGLD"},
    "PHAG.MI": {"cat": "⛏️ ETC ARGENTO", "tv": "MIL:PHAG", "dir": "PHAG"},
    "CRUD.MI": {"cat": "🛢️ ETC PETROLIO", "tv": "MIL:CRUD", "dir": "CRUD"},
    "SWDA.MI": {"cat": "🌍 ETF WORLD", "tv": "MIL:SWDA", "dir": "SWDA"},
    "BTCE.DE": {"cat": "🌐 CRYPTO (BITCOIN ETN)", "tv": "XETR:BTCE", "dir": "BTCE"},
    "ETH-USD": {"cat": "🌐 CRYPTO (ETHEREUM)", "tv": "ETHUSD", "dir": "ETH"},
    "EURUSD=X": {"cat": "💱 FOREX (EUR/USD)", "tv": "EURUSD", "dir": "EURUSD"},
    "GBPUSD=X": {"cat": "💱 FOREX (GBP/USD)", "tv": "GBPUSD", "dir": "GBPUSD"}
}

# --- FILTRI DI CORRELAZIONE (Sentiment Check) ---
CORRELAZIONI = {
    "CSSPX.MI": "^GSPC", "ANX.MI": "^NDX", "SWDA.MI": "^GSPC", 
    "ETFMIB.MI": "FTSEMIB.MI", "EXX5.DE": "^GDAXI",
    "SGLD.MI": "GC=F", "PHAG.MI": "GC=F", "SI=F": "GC=F",
    "CRUD.MI": "CL=F", "BTCE.DE": "BTC-USD", "ETH-USD": "BTC-USD"
}

def calcola_indicatori(df):
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    # Bollinger
    df['MA20'] = df['Close'].rolling(20).mean()
    df['StdDev'] = df['Close'].rolling(20).std()
    df['UpperB'] = df['MA20'] + (df['StdDev'] * 2)
    df['LowerB'] = df['MA20'] - (df['StdDev'] * 2)
    # Volumi
    df['Vol_MA_Short'] = df['Volume'].rolling(3).mean()
    df['Vol_MA_Long'] = df['Volume'].rolling(20).mean()
    # ATR per Stop Loss elastico
    hl = df['High'] - df['Low']
    hc = (df['High'] - df['Close'].shift()).abs()
    lc = (df['Low'] - df['Close'].shift()).abs()
    df['ATR'] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()
    return df

def main():
    if datetime.now().weekday() > 4:
        print("Weekend: Mercati chiusi.")
        return

    # Caricamento dinamico da ticker.txt
    try:
        symbols = [line.strip() for line in open('tickers.txt', 'r') if line.strip() and not line.startswith('#')]
        print(f"🚀 CECCHINO AVVIATO: Analisi di {len(symbols)} asset in corso...")
    except Exception as e:
        print(f"❌ Errore ticker.txt: {e}")
        return
    
    cache = {}
    for t in symbols:
        try:
            df = yf.download(t, period="3mo", interval="4h", progress=False, auto_adjust=True)
            if df.empty or len(df) < 137: continue
            df.columns = [str(c[0] if isinstance(c, tuple) else c).capitalize() for c in df.columns]
            df = calcola_indicatori(df)
            
            p = float(df['Close'].iloc[-1].item())
            h_r = float(df['High'].rolling(137).max().iloc[-1].item())
            l_r = float(df['Low'].rolling(137).min().iloc[-1].item())
            range_h = h_r - l_r
            
            is_acc = p < (h_r + l_r) / 2
            lvl = l_r - (range_h * ALPHA * MOLTIPLICATORE_QUANTUM) if is_acc else h_r + (range_h * ALPHA * MOLTIPLICATORE_QUANTUM)
            
            rsi_val = float(df['RSI'].iloc[-1].item())
            conf_rsi = (15 <= rsi_val <= 32) if is_acc else (68 <= rsi_val <= 85)
            vol_status = df['Vol_MA_Short'].iloc[-1] < (df['Vol_MA_Long'].iloc[-1] * 1.1)

            cache[t] = {
                "p": p, "rsi": rsi_val, "dist": abs(p - lvl)/lvl, "lvl": lvl,
                "tp": lvl + (range_h * 0.85) if is_acc else lvl - (range_h * 0.85),
                "sl": lvl - (df['ATR'].iloc[-1] * 2.5) if is_acc else lvl + (df['ATR'].iloc[-1] * 2.5),
                "fase": "ACCUMULAZIONE" if is_acc else "DISTRIBUZIONE", 
                "vol_status": vol_status, "conf_rsi": conf_rsi, "df": df
            }
        except: continue

    for t, d in cache.items():
        if d['dist'] < SOGLIA_NOTIFICA and d['conf_rsi'] and d['vol_status']:
            
            # Controllo Indice di Riferimento
            indice_ticker = CORRELAZIONI.get(t)
            idx_perf = 0.0
            if indice_ticker:
                try:
                    idx_df = yf.download(indice_ticker, period="1d", progress=False)
                    idx_perf = ((float(idx_df['Close'].iloc[-1].item()) / float(idx_df['Open'].iloc[-1].item())) - 1) * 100
                except: pass

            if idx_perf < SOGLIA_PANICO_INDICE: continue

            # --- SALVATAGGIO SU SUPABASE ---
            if supabase:
                try:
                    # Pulizia ticker per compatibilità MT5 (es: ^GDAXI -> GDAXI)
                    t_clean = t.replace('^', '').split('.')[0].replace('=X', '')
                    supabase.table("segnali_trading").insert({
                        "ticker": t_clean, "fase": d['fase'], "stato": "Pendente", 
                        "prezzo_ingresso": round(d['lvl'], 5), "tp": round(d['tp'], 5), 
                        "sl": round(d['sl'], 5), "distanza_minima_raggiunta": round(d['dist'], 5)
                    }).execute()
                    print(f"📡 Segnale inviato a DB: {t_clean}")
                except Exception as e: print(f"Errore DB: {e}")

            # --- INVIO TELEGRAM ---
            asset_info = MAPPA_ASSET.get(t, {"cat": "📊 ASSET", "tv": t, "dir": t})
            msg = (f"{asset_info['cat']} | 🎯 <b>SEGNALE</b>\n\n"
                   f"<b>Asset:</b> <code>{t}</code>\n"
                   f"<b>Azione:</b> {'BUY LIMIT' if 'ACC' in d['fase'] else 'SELL LIMIT'}\n"
                   f"🔵 <b>ENTRY: {d['lvl']:.4f}</b>\n"
                   f"🟢 <b>TP: {d['tp']:.4f}</b>\n"
                   f"🔴 <b>SL: {d['sl']:.4f}</b>\n\n"
                   f"🛡️ <b>RSI:</b> {d['rsi']:.1f} | <b>Volumi:</b> OK")

            # Grafico
            plot_data = d['df'].iloc[-50:]
            mpf.plot(plot_data, type='candle', style='charles', savefig='plot.png', 
                     hlines=dict(hlines=[d['lvl'], d['tp'], d['sl']], colors=['blue', 'green', 'red'], linestyle='-.'))
            
            with open('plot.png', 'rb') as f:
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendPhoto", 
                              files={'photo': f}, data={'chat_id': CHAT_ID, 'caption': msg, 'parse_mode': 'HTML'})

if __name__ == "__main__":
    main()
