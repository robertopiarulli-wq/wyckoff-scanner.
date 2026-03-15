for ticker in symbols:
    print(f"Analizzo: {ticker}")
    try:
        # scarica i dati
        df = yf.download(ticker, period="3mo", interval="1h", progress=False, auto_adjust=True)
        if df.empty or len(df) < 137: continue
            
        # ESTRAZIONE "PIATTA" (senza MultiIndex)
        # Usiamo .iloc[:, 0] per forzare la prima colonna se ci sono conflitti
        high_s = df['High'].values if isinstance(df['High'], pd.Series) else df.iloc[:, df.columns.get_loc('High')].values
        low_s = df['Low'].values if isinstance(df['Low'], pd.Series) else df.iloc[:, df.columns.get_loc('Low')].values
        close_s = df['Close'].values if isinstance(df['Close'], pd.Series) else df.iloc[:, df.columns.get_loc('Close')].values
        
        # Calcolo rolling puro con numpy
        high_r = np.max(high_s[-137:])
        low_r = np.min(low_s[-137:])
        range_h = high_r - low_r
        
        p_livello = low_r - (range_h * 0.007 * 3.0) 
        prezzo = close_s[-1]
        
        distanza = abs(prezzo - p_livello) / p_livello
        
        # LOGICA TEST: Forziamo l'invio per TUTTI i ticker
        if distanza < 0.002: 
            semaforo, stato = "🔴", "INGRESSO IMMEDIATO"
        elif distanza < 0.01: 
            semaforo, stato = "🟡", "IN AVVICINAMENTO"
        else: 
            semaforo, stato = "⚪", "LONTANO"
        
        # Ora il codice prosegue SEMPRE verso il grafico e l'invio
        msg = f"{semaforo} {ticker}\nStato: {stato}\nTarget: {p_livello:.2f}"
        mpf.plot(df.iloc[-50:], type='candle', style='charles', savefig='plot.png')
        
        # Invio (ora questo viene eseguito per ogni ticker, senza filtri)
        send_telegram(msg, 'plot.png')
        print(f"Messaggio inviato per {ticker}")
        
        msg = f"{semaforo} {ticker}\nStato: {stato}\nTarget: {p_livello:.2f}"
        
        # Salvataggio grafico
        mpf.plot(df.iloc[-50:], type='candle', style='charles', savefig='plot.png')
        
        # Invio
        send_telegram(msg, 'plot.png')
        print(f"Finito {ticker}")
        time.sleep(2)
        
    except Exception as e:
        print(f"Errore su {ticker}: {e}")
        continue
