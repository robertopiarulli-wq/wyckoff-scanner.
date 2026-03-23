import yfinance as yf
import requests
import os
import mplfinance as mpf
import pandas as pd
import numpy as np
from datetime import datetime
from supabase import create_client

# --- CONFIG ---
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID') or os.environ.get('TELEGRAM_CHAT_ID')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

ALPHA = 0.00729735
MOLTIPLICATORE_QUANTUM = 2.618 
SOGLIA_NOTIFICA = 0.02
SOGLIA_PANICO_INDICE = -1.25  # Filtro sicurezza: annulla segnali se l'indice crolla

MAPPA_ASSET = {
    "^GSPC": {"cat": "📈 INDICE USA", "tv": "SPX"},
    "^NDX":  {"cat": "📈 INDICE TECH", "tv": "NDX"},
    "^GDAXI": {"cat": "📈 INDICE DAX", "tv": "DAX"},
    "FTSEMIB.MI": {"cat": "📈 INDICE MIB", "tv": "FTSEMIB"},
    "GC=F": {"cat": "⛏️ METALS", "tv": "GC1!"},
    "CSSPX.MI": {"cat": "🇮🇹 ETF USA", "tv": "MIL:CSSPX"},
    "ANX.MI": {"cat": "🇮🇹 ETF TECH", "tv": "MIL:ANX"},
    "SGLD.MI": {"cat": "⛏️ ETC ORO", "tv": "MIL:SGLD"},
    "BTCE.DE": {"cat": "🌐 CRYPTO", "tv": "XETR:BTCE"},
    "SWDA.MI": {"cat": "🌍 ETF WORLD", "tv": "MIL:SWDA"}
}

CORRELAZIONI = {
    "CSSPX.MI": "^GSPC", 
    "ANX.MI": "^NDX", 
    "SGLD.MI": "GC=F",
    "SWDA.MI": "^GSPC",
    "BTCE.DE": "BTC-USD"
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
    if datetime.now().weekday() > 4:
        print("Weekend: Cecchino a riposo.")
        return

    try:
        symbols = [line.strip() for line in open('tickers.txt', 'r') if line.strip() and not line.startswith('#')]
    except: return
    
    cache = {}
    for t in symbols:
        try:
            df = yf.download(t, period="3mo", interval="4h", progress=False, auto_adjust=True)
            if df.empty or len(df) < 137: continue
            df.columns = [str(c[0] if isinstance(c, tuple) else c).capitalize() for c in df.columns]
            df = calcola_indicatori(df)
            p = df['Close'].iloc[-1]
            h_r, l_r = df['High'].rolling(137).max().iloc[-1], df['Low'].rolling(137).min().iloc[-1]
            range_h = h_r - l_r
            is_acc = p < (h_r + l_r) / 2
            
            lvl = l_r - (range_h * ALPHA * MOLTIPLICATORE_QUANTUM) if is_acc else h_r + (range_h * ALPHA * MOLTIPLICATORE_QUANTUM)
            
            rsi_val = df['RSI'].iloc[-1]
            if is_acc:
                conf_rsi = (15 <= rsi_val <= 32)
                rsi_target, azione = "15-32", "BUY LIMIT"
            else:
                conf_rsi = (68 <= rsi_val <= 85)
                rsi_target, azione = "68-85", "SELL LIMIT"
            
            vol_status = df['Vol_MA_Short'].iloc[-1] < (df['Vol_MA_Long'].iloc[-1] * 1.1)

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
            
            # --- FILTRO AUTOMATICO INDICE ---
            indice_ticker = CORRELAZIONI.get(t)
            idx_perf = 0
            info_indice = ""
            if indice_ticker:
                try:
                    idx_df = yf.download(indice_ticker, period="1d", progress=False)
                    if not idx_df.empty:
                        idx_now = idx_df['Close'].iloc[-1]
                        idx_prev = idx_df['Open'].iloc[-1]
                        idx_perf = ((idx_now / idx_prev) - 1) * 100
                        info_indice = f"📊 <b>INDICE REF ({indice_ticker}):</b> {idx_now:.2f} ({idx_perf:+.2f}%)\n"
                except:
                    info_indice = "⚠️ Errore recupero indice rif.\n"

            # Se l'indice crolla oltre la soglia, scartiamo il segnale
            if idx_perf < SOGLIA_PANICO_INDICE:
                print(f"DEBUG: Segnale su {t} scartato per crollo Indice ({idx_perf:.2f}%)")
                continue

            # --- SALVATAGGIO SU SUPABASE ---
            if supabase:
                try:
                    data_db = {"ticker": t, "azione": d['azione'], "entry": float(d['lvl']), "tp": float(d['tp']), "sl": float(d['sl']), "prezzo_attuale": float(d['p'])}
                    supabase.table("segnali_trading").insert(data_db).execute()
                except Exception as e: print(f"Errore DB: {e}")

            # --- INVIO TELEGRAM ---
            asset = MAPPA_ASSET.get(t, {"cat": "📊 ASSET", "tv": t})
            msg = (f"{asset['cat']} | 🎯 <b>SEGNALE GOLD</b>\n"
                   f"{info_indice}\n"
                   f"<b>Asset:</b> {t}\n"
                   f"<b>Azione:</b> <code>{d['azione']}</code>\n"
                   f"<b>Prezzo:</b> {d['p']:.4f}\n\n"
                   f"🔵 <b>ENTRY: {d['lvl']:.4f}</b>\n"
                   f"🟢 <b>TP: {d['tp']:.4f}</b>\n"
                   f"🔴 <b>SL: {d['sl']:.4f}</b>\n\n"
                   f"🛡️ <b>FILTRI ATTIVI:</b>\n"
                   f"✅ RSI ({d['rsi_target']}): {d['rsi']:.1f}\n"
                   f"✅ Trend: Esaurimento Volumi")

            plot_data = d['df'].iloc[-50:]
            ap = [mpf.make_addplot(plot_data['UpperB'], color='gray', alpha=0.3),
                  mpf.make_addplot(plot_data['LowerB'], color='gray', alpha=0.3)]
            mpf.plot(plot_data, type='candle', style='charles', addplot=ap, savefig='plot.png', 
                     hlines=dict(hlines=[d['lvl'], d['tp'], d['sl']], colors=['blue', 'green', 'red'], linestyle='-.'))
            
            with open('plot.png', 'rb') as f:
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendPhoto", files={'photo': f}, data={'chat_id': CHAT_ID, 'caption': msg, 'parse_mode': 'HTML'})

if __name__ == "__main__":
    main()
