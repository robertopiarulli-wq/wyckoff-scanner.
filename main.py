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
SOGLIA_NOTIFICA = 0.05          

# --- MAPPA ASSET COMPLETA ---
MAPPA_ASSET = {
    "^GSPC": {"cat": "📈 INDICE USA", "tv": "SPX"},
    "^NDX":  {"cat": "📈 INDICE TECH", "tv": "IXIC"},
    "^GDAXI": {"cat": "📈 INDICE DAX", "tv": "GER40"},
    "FTSEMIB.MI": {"cat": "📈 INDICE MIB", "tv": "FTSEMIB"},
    "CSSPX.MI": {"cat": "🇮🇹 ETF S&P500", "tv": "MIL:CSSPX"},
    "ANX.MI": {"cat": "🇮🇹 ETF NASDAQ", "tv": "MIL:ANX"},
    "SWDA.MI": {"cat": "🌍 ETF WORLD", "tv": "MIL:SWDA"},
    "AAPL": {"cat": "🍎 TECH (APPLE)", "tv": "AAPL"},
    "NVDA": {"cat": "🤖 TECH (NVIDIA)", "tv": "NVDA"},
    "TSLA": {"cat": "⚡ TECH (TESLA)", "tv": "TSLA"},
    "AMZN": {"cat": "📦 TECH (AMAZON)", "tv": "AMZN"},
    "META": {"cat": "📱 TECH (META)", "tv": "META"},
    "MSFT": {"cat": "💻 TECH (MICROSOFT)", "tv": "MSFT"},
    "GOOGL": {"cat": "🔍 TECH (GOOGLE)", "tv": "GOOGL"},
    "AVGO": {"cat": "🔌 TECH (BROADCOM)", "tv": "AVGO"},
    "ASML": {"cat": "🔬 TECH (ASML)", "tv": "ASML"},
    "XLF": {"cat": "🏦 SECTOR (FINANCE)", "tv": "XLF"},
    "XLE": {"cat": "🛢️ SECTOR (ENERGY)", "tv": "XLE"},
    "XLV": {"cat": "💊 SECTOR (HEALTH)", "tv": "XLV"},
    "SMH": {"cat": "💾 SECTOR (CHIPS)", "tv": "SMH"},
    "IWM": {"cat": "🚜 SMALL CAPS", "tv": "IWM"},
    "QQQ": {"cat": "📊 NASDAQ 100 ETF", "tv": "QQQ"},
    "GC=F": {"cat": "⛏️ METALS (GOLD)", "tv": "GOLD"},
    "SI=F": {"cat": "⛏️ METALS (SILVER)", "tv": "SILVER"},
    "CL=F": {"cat": "🛢️ ENERGY (OIL)", "tv": "USOIL"},
    "NG=F": {"cat": "🔥 ENERGY (GAS)", "tv": "NATGAS"},
    "KC=F": {"cat": "☕ SOFT (COFFEE)", "tv": "KC1!"},
    "SB=F": {"cat": "🍭 SOFT (SUGAR)", "tv": "SB1!"},
    "HG=F": {"cat": "🏗️ METALS (COPPER)", "tv": "COPPER"},
    "BTC-USD": {"cat": "🌐 CRYPTO (BTC)", "tv": "BTCUSD"},
    "ETH-USD": {"cat": "🌐 CRYPTO (ETH)", "tv": "ETHUSD"},
    "SOL-USD": {"cat": "🌐 CRYPTO (SOL)", "tv": "SOLUSD"},
    "ADA-USD": {"cat": "🌐 CRYPTO (ADA)", "tv": "ADAUSD"},
    "DOT-USD": {"cat": "🌐 CRYPTO (DOT)", "tv": "DOTUSD"},
    "AVAX-USD": {"cat": "🌐 CRYPTO (AVAX)", "tv": "AVAXUSD"},
    "LINK-USD": {"cat": "🌐 CRYPTO (LINK)", "tv": "LINKUSD"},
    "XRP-USD": {"cat": "🌐 CRYPTO (XRP)", "tv": "XRPUSD"},
    "KO": {"cat": "🥤 VALUE (COCA COLA)", "tv": "KO"},
    "PEP": {"cat": "🍿 VALUE (PEPSICO)", "tv": "PEP"},
    "PG": {"cat": "🧼 VALUE (P&G)", "tv": "PG"},
    "JNJ": {"cat": "🩺 VALUE (J&J)", "tv": "JNJ"},
    "EURUSD=X": {"cat": "💱 FOREX (EUR/USD)", "tv": "EURUSD"},
    "GBPUSD=X": {"cat": "💱 FOREX (GBP/USD)", "tv": "GBPUSD"}
}

def calcola_indicatori(df):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    df['MA20'] = df['Close'].rolling(20).mean()
    df['StdDev'] = df['Close'].rolling(20).std()
    df['UpperB'] = df['MA20'] + (df['StdDev'] * 2)
    df['LowerB'] = df['MA20'] - (df['StdDev'] * 2)
    
    hl = df['High'] - df['Low']
    hc = (df['High'] - df['Close'].shift()).abs()
    lc = (df['Low'] - df['Close'].shift()).abs()
    df['ATR'] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()
    return df

def crea_grafico(df, t, lvl):
    buf = io.BytesIO()
    # TAGLIO DI VISUALIZZAZIONE: Ultime 40 candele per chiarezza nel messaggio
    data_to_plot = df.tail(40).copy()
    
    ap = [
        mpf.make_addplot(data_to_plot['LowerB'], color='gray', alpha=0.3),
        mpf.make_addplot(data_to_plot['UpperB'], color='gray', alpha=0.3)
    ]
    
    mpf.plot(data_to_plot, type='candle', style='charles', addplot=ap,
             hlines=dict(hlines=[lvl], colors=['blue'], linestyle='--'),
             savefig=dict(fname=buf, format='png'))
    buf.seek(0)
    return buf

def main():
    is_weekend = datetime.now().weekday() > 4
    cambiamenti = False
    
    try:
        with open('tickers.txt', 'r') as f:
            symbols = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except Exception as e:
        print(f"❌ Errore tickers: {e}")
        return

    print(f"🚀 SCANSIONE COMPLETA: {len(symbols)} asset...")
    lista_nuovi, lista_cancella = [], []

    for t in symbols:
        if is_weekend and "-USD" not in t: continue
        
        print(f"🔍 Analisi: {t}...")
        
        try:
            df = yf.download(t, period="1y", interval="4h", progress=False, auto_adjust=True)
            # CONTROLLO SICUREZZA: Servono almeno 140 candele per calcolare Pauli (137)
            if df.empty or len(df) < 140: 
                print(f"⚠️ Dati insufficienti per {t}")
                continue
            
            df.columns = [str(c[0] if isinstance(c, tuple) else c).capitalize() for c in df.columns]
            df = calcola_indicatori(df)
            
            p = float(df['Close'].iloc[-1].item())
            # FREQUENZA DI PAULI (137 CANDELE) - NON TOCCATA!
            h_r = float(df['High'].rolling(137).max().iloc[-1])
            l_r = float(df['Low'].rolling(137).min().iloc[-1])
            range_h = h_r - l_r
            
            is_acc = p < (h_r + l_r) / 2
            fase_attuale = "ACCUMULAZIONE" if is_acc else "DISTRIBUZIONE"
            lvl = l_r - (range_h * ALPHA * MOLTIPLICATORE_QUANTUM) if is_acc else h_r + (range_h * ALPHA * MOLTIPLICATORE_QUANTUM)
            dist = abs(p - lvl) / lvl
            t_clean = t.replace('^', '').split('.')[0]
            rsi_val = df['RSI'].iloc[-1]

            print(f"📊 {t_clean} | Distanza: {dist:.2%} | RSI: {rsi_val:.1f} | Fase: {fase_attuale}")

            conf_rsi = (is_acc and rsi_val < 48) or (not is_acc and rsi_val > 52)
            
            check_db = supabase.table("segnali_trading").select("*").eq("ticker", t_clean).eq("stato", "Pendente").execute() if supabase else None
            gia_pendente = bool(check_db and check_db.data)

            if dist < SOGLIA_NOTIFICA and conf_rsi:
                if not gia_pendente:
                    tp = lvl + (range_h * 0.7) if is_acc else lvl - (range_h * 0.7)
                    sl = lvl - (df['ATR'].iloc[-1]*2) if is_acc else lvl + (df['ATR'].iloc[-1]*2)
                    chart = crea_grafico(df, t, lvl)
                    d = {"t": t, "lvl": lvl, "fase": fase_attuale, "rsi": rsi_val, "tp": tp, "sl": sl, "chart": chart, "azione": "BUY LIMIT" if is_acc else "SELL LIMIT"}
                    lista_nuovi.append(d)
                    if supabase:
                        supabase.table("segnali_trading").insert({
                            "ticker": t_clean, "fase": fase_attuale, "stato": "Pendente", 
                            "prezzo_ingresso": round(lvl, 5), "tp": round(tp, 5), "sl": round(sl, 5), "rsi": round(rsi_val, 2)
                        }).execute()
                    cambiamenti = True
            elif gia_pendente:
                if check_db.data[0]['fase'] != fase_attuale or dist > (SOGLIA_NOTIFICA * 2.0):
                    lista_cancella.append({"t": t, "motivo": "Inversione Trend/Lontano"})
                    if supabase: supabase.table("segnali_trading").update({"stato": "Chiuso"}).eq("ticker", t_clean).execute()
                    cambiamenti = True
        except Exception as e: 
            print(f"❌ Errore su {t}: {e}")
            continue

    def invia_telegram(d, header, show_filters=True):
        asset = MAPPA_ASSET.get(d['t'], {"cat": "📊 ASSET", "tv": d['t']})
        msg = f"{header}\n{asset['cat']} | 🎯 <b>{d.get('azione', 'LIMIT')}</b>\n"
        msg += f"----------------------------------\n<b>Asset:</b> <code>{d['t']}</code>\n"
        if show_filters:
            msg += f"🔵 <b>ENTRY: {d['lvl']:.4f}</b>\n🟢 <b>TP: {d['tp']:.4f}</b>\n🔴 <b>SL: {d['sl']:.4f}</b>\n\n"
        else: msg += f"❗ <b>MOTIVO:</b> {d.get('motivo')}\n\n"
        msg += f"🔗 <a href='https://it.tradingview.com/chart/?symbol={asset['tv']}'>TradingView</a>"
        
        if d.get('chart'):
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendPhoto", params={'chat_id': CHAT_ID, 'caption': msg, 'parse_mode': 'HTML'}, files={'photo': d['chart']})
        else:
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML', 'disable_web_page_preview': True})

    for d in lista_nuovi: invia_telegram(d, "🆕 <b>NUOVO ALERT</b>")
    for d in lista_cancella: invia_telegram(d, "⚠️ <b>ORDINE CHIUSO</b>", False)

    if cambiamenti and supabase:
        res = supabase.table("segnali_trading").select("*").eq("stato", "Pendente").execute()
        limit_txt, live_txt = [], []
        for p in res.data:
            try:
                t_orig = next((k for k in MAPPA_ASSET if k.replace('^','').split('.')[0] == p['ticker']), p['ticker'])
                last_df = yf.download(t_orig, period="1d", progress=False)
                last_p = float(last_df['Close'].iloc[-1].item())
                link = f"<a href='https://it.tradingview.com/chart/?symbol={MAPPA_ASSET.get(t_orig, {'tv': p['ticker']})['tv']}'>📈</a>"
                linea = f"{link} <b>{p['ticker']}</b>\n      └ 🔵 Ingr: <code>{p['prezzo_ingresso']}</code> | RSI: <code>{p.get('rsi', 'N/D')}</code>\n      └ 🟢 TP: <code>{p.get('tp', 'N/D')}</code> | 🔴 SL: <code>{p.get('sl', 'N/D')}</code>"
                
                if (p['fase'] == "ACCUMULAZIONE" and last_p <= p['prezzo_ingresso']) or (p['fase'] == "DISTRIBUZIONE" and last_p >= p['prezzo_ingresso']):
                    live_txt.append(linea)
                else: limit_txt.append(linea)
            except: continue
        
        rep = "📊 <b>REPORT POSIZIONI ATTIVE</b>\n\n⏳ <b>LIMIT:</b>\n" + ("\n\n".join(limit_txt) if limit_txt else "Nessuna")
        rep += "\n\n🚀 <b>LIVE:</b>\n" + ("\n\n".join(live_txt) if live_txt else "Nessuna")
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={'chat_id': CHAT_ID, 'text': rep, 'parse_mode': 'HTML', 'disable_web_page_preview': True})

if __name__ == "__main__":
    main()
