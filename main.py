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

    for t in symbols:
        if is_weekend and "-USD" not in t: continue
        try:
            df = yf.download(t, period="1y", interval="4h", progress=False, auto_adjust=True)
            if df.empty or len(df) < 140: continue
            df.columns = [str(c[0] if isinstance(c, tuple) else c).capitalize() for c in df.columns]
            df = calcola_indicatori(df)
            
            p = float(df['Close'].iloc[-1].item())
            h_r, l_r = float(df['High'].rolling(137).max().iloc[-1]), float(df['Low'].rolling(137).min().iloc[-1])
            range_h = h_r - l_r
            rsi_val = df['RSI'].iloc[-1]
            vol_attuale = df['Volume'].iloc[-1]
            vol_ma = df['MA20_Vol'].iloc[-1]
            
            is_acc = p < (h_r + l_r) / 2
            lvl = l_r - (range_h * ALPHA * MOLTIPLICATORE_QUANTUM) if is_acc else h_r + (range_h * ALPHA * MOLTIPLICATORE_QUANTUM)
            dist = abs(p - lvl) / lvl
            
            fase_attiva = False
            wyckoff_db = "" 
            wyckoff_msg = "" 

            vol_confermato = vol_attuale > (vol_ma * 1.5)
            
            if is_acc and dist < SOGLIA_NOTIFICA:
                if vol_confermato and (35 <= rsi_val <= 55):
                    fase_attiva = True
                    wyckoff_db = "ACCUMULAZIONE (SOS)" 
                    wyckoff_msg = "ACCUMULAZIONE (Fase D/E - SOS Attiva) ✅"
            
            elif not is_acc and dist < SOGLIA_NOTIFICA:
                if vol_confermato and (45 <= rsi_val <= 65):
                    fase_attiva = True
                    wyckoff_db = "DISTRIBUZIONE (SOW)" 
                    wyckoff_msg = "DISTRIBUZIONE (Fase C/D - SOW Attiva) ✅"

            if fase_attiva:
                # CORREZIONE: Pulizia ticker per il controllo unicità nel database
                t_db = t.replace('^', '').split('.')[0]
                check = supabase.table("segnali_trading").select("*").eq("ticker", t_db).eq("stato", "Pendente").execute()
                
                # Inserisce solo se non esiste già un segnale "Pendente" per questo ticker
                if not check.data:
                    tp = lvl + (range_h * 0.7) if is_acc else lvl - (range_h * 0.7)
                    sl = lvl - (df['ATR'].iloc[-1]*2) if is_acc else lvl + (df['ATR'].iloc[-1]*2)
                    
                    if supabase:
                        supabase.table("segnali_trading").insert({
                            "ticker": t_db, "fase": wyckoff_db, "stato": "Pendente", 
                            "prezzo_ingresso": round(lvl, 5), "tp": round(tp, 5), "sl": round(sl, 5), "rsi": round(rsi_val, 2)
                        }).execute()
                    
                    asset = MAPPA_ASSET.get(t, {"cat": "📊 ASSET", "tv": t})
                    chart = crea_grafico(df, t, lvl)
                    msg = (f"🎯 <b>FASE WYCKOFF RILEVATA</b>\n"
                           f"━━━━━━━━━━━━━━━\n"
                           f"📦 <b>Stato:</b> {wyckoff_msg}\n"
                           f"📈 <b>Asset:</b> {asset['cat']} ({t})\n"
                           f"🔵 <b>Ordine:</b> {'BUY LIMIT' if is_acc else 'SELL LIMIT'}\n"
                           f"💸 <b>Entry:</b> {lvl:.4f}\n"
                           f"🟢 <b>Target:</b> {tp:.4f} | 🔴 <b>Stop:</b> {sl:.4f}\n"
                           f"━━━━━━━━━━━━━━━\n"
                           f"📊 <b>RSI:</b> {rsi_val:.1f} | 🔊 <b>Vol:</b> {vol_attuale/vol_ma:.1f}x\n"
                           f"🔗 <a href='https://it.tradingview.com/chart/?symbol={asset['tv']}'>TradingView</a>")
                    
                    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendPhoto", 
                                 params={'chat_id': CHAT_ID, 'caption': msg, 'parse_mode': 'HTML'}, 
                                 files={'photo': chart})
                else:
                    print(f"ℹ️ Segnale per {t_db} già presente nel database. Salto inserimento.")

        except Exception as e: print(f"❌ Errore {t}: {e}")

if __name__ == "__main__":
    main()
