import numpy as np
from statistics import mean
import pandas as pd
import pandas_ta as ta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import mplfinance as mpf
from finta import TA

# shortcut for (high + low)/2
def HL2(df):
    return (df["High"]+df["Low"])/2

def Fetch(df):
    ##Kijun-sen##
    def KIJUN(data):
        # Tenkan-sen (Conversion Line): (9-period high + 9-period low)/2))
        # nine_period_high = df['High'].rolling(window= 9).max()
        # nine_period_low = df['Low'].rolling(window= 9).min()
        # df['tenkan_sen'] = (nine_period_high + nine_period_low) /2
        # Kijun-sen (Base Line): (26-period high + 26-period low)/2))
        period26_high = df['High'].rolling(window=26).max()
        period26_low = df['Low'].rolling(window=26).min()
        df['kijun'] = (period26_high + period26_low) / 2
        return df

    def ATR(data):
        high_low = data['High'] - data['Low']
        #high_cp = np.abs(data['High'] - data['Close'].shift())
        #low_cp = np.abs(data['Low'] - data['Close'].shift())
        df2 = pd.concat([high_low], axis=1)
        true_range = np.max(df2, axis=1)
        df['ATR']= true_range.rolling(12).mean()
        df['SATR'] = ta.sma(df["ATR"], length=12)
        return df    


    ##Moving average##
    def SMA(data):
        df['SMA11'] = ta.sma(df["Close"], length=11)
        df['SMA21'] = ta.sma(df["Close"], length=21)
        return df

    def MFI(data):
        df['MFI'] = ta.mfi(df["High"], df["Low"], df["Close"], df["Volume"], length=11)
        return df        

    def SMMA2(data):
        df=data
        LENGTH_JAW = 13
        LENGTH_TEETH = 8
        LENGTH_LIPS = 5
        df['SMMA2_JAW'] = ta.sma(HL2(df), length=LENGTH_JAW)
        df['SMMA2_JAW'] = (df['SMMA2_JAW'].shift() * (LENGTH_JAW - 1) + HL2(df))
        df['SMMA2_TEETH'] = ta.sma(HL2(df), length=LENGTH_TEETH)
        df['SMMA2_TEETH'] = (df['SMMA2_TEETH'].shift() * (LENGTH_TEETH - 1) + HL2(df))
        df['SMMA2_LIPS'] = ta.sma(HL2(df), length=LENGTH_LIPS)
        df['SMMA2_LIPS'] = (df['SMMA2_LIPS'].shift() * (LENGTH_LIPS - 1) + HL2(df))
        return df

    ##ExpMoving average##
    def EMA(data):
        """EMA AND DEMA"""
        ema50=df['Close'].ewm(span=50,min_periods=50,adjust=False,ignore_na=False).mean()
        df['EMA50'] = ema50
        ema1=df['Close'].ewm(span=200,min_periods=200,adjust=False,ignore_na=False).mean()
        df['EMA200'] = ema1
        ema2 = ema1.ewm(span=200, adjust=False).mean()
        df['DEMA200'] = 2*ema1 - ema2

        ema1=df['Close'].ewm(span=100,min_periods=100,adjust=False,ignore_na=False).mean()
        df['EMA100'] = ema1
        ema2 = ema1.ewm(span=100, adjust=False).mean()
        df['DEMA100'] = 2*ema1 - ema2

        return df

    ##Bollinger Bands##
    def BB(data):
        df = data
        df['30_MA_Close'] = df['Close'].rolling(window=30).mean()
        df['20_std_Close'] = df['Close'].rolling(window=20).std()
        df['Upper'] = df['30_MA_Close'] + 2*df['20_std_Close']
        df['Lower'] = df['30_MA_Close'] - 2*df['20_std_Close']
        return df

    ##ADX##
    def ADX(data):
        df = data.astype({"High": float, "Low": float, "Close": float})
        adx15 = ta.adx(df['High'],df['Low'],df['Close'], length=15)
        df['ADX15'] = adx15['ADX_15']
        df['DMP15'] = adx15['DMP_15']
        df['DMN15'] = adx15['DMN_15']

        return df
    ##MACD##
    def MACD(data):
        df = data
        k = df['Close'].ewm(span=12, adjust=False, min_periods=12).mean()
        d = df['Close'].ewm(span=26, adjust=False, min_periods=26).mean()
        macd = k - d
        signal = macd.ewm(span=9, adjust=False, min_periods=9).mean()
        histogram = macd - signal
        df["MACD"], df["MACD_SIGNAL"], df["MACD_HIST"] = macd, signal, histogram
        return df        

    ## Standard deviation ##
    def STDDEV(data):
        df = data
        df['STDDEV'] = ta.stdev(data['Close'], 12, False)
        return df

    ## SFX Trend Or Range Indicator ##
    def sfxtrend(data):
        df=data

        SFXSTATE = '' if not df['SFXSTATE'].shift() else df['SFXSTATE'].shift() # use sfxstate from previous row or ''
        STDDEV = df['STDDEV']
        SMA = ta.sma(df['Close'], length=11)
        CROSS = ta.cross(STDDEV, SMA)
        IDU = CROSS and STDDEV > SMA and STDDEV < ATR
        IDU2 = CROSS and STDDEV > SMA and STDDEV > ATR
        IDD = CROSS and STDDEV < SMA and STDDEV > ATR
        IDD2 = CROSS and STDDEV < SMA and STDDEV < ATR

        if IDU and (SFXSTATE == 'exhaust' or SFXSTATE == '' or SFXSTATE == 'sideways'):
            SFXSTATE = 'trend'

        if IDD and (SFXSTATE =='trend'):
            SFXSTATE = 'exhaust'

        if IDD2 and (SFXSTATE == 'exhaust' or SFXSTATE == ''):
            SFXSTATE = 'sideways'


        df['IDD'] = IDD
        df['IDD2'] = IDD2
        df['IDU'] = IDU
        df['SFXSTATE'] = SFXSTATE

        return df
  
    #df=SMA(df)
    #df=BB(df)
    df=EMA(df)
    #df=ADX(df)
    df=MACD(df)
    df=MFI(df)
    df=KIJUN(df)
    df=ATR(df)
    df=STDDEV(df)
    df=SMMA2(df)
    df=sfxtrend(df)
    pd.set_option('display.max_rows', None)


    def chart(data):
        pdata = df
        pdata.timestamp = pd.to_datetime(pdata.timestamp)
        pdata.set_index('timestamp', inplace=True)
        
        bb1 = mpf.make_addplot(pdata['Upper'],type='line')
        bb2 = mpf.make_addplot(pdata['Lower'],type='line')
        bb3 = mpf.make_addplot(pdata['30_MA_Close'],type='line')
        #ema11 = mpf.make_addplot(pdata['EMA-11'],type='line')
        #ema21 = mpf.make_addplot(pdata['EMA-21'],type='line')

        adx15 = mpf.make_addplot(pdata['ADX15'],panel='lower',color='black',secondary_y=False)
        dmp15 = mpf.make_addplot(pdata['DMP15'],panel='lower',color='green',secondary_y=False)
        dmn15 = mpf.make_addplot(pdata['DMN15'],panel='lower',color='red',secondary_y=False)

        #ema21 = mpf.make_addplot(pdata['EMA-21'],type='line')


        mpf.plot(pdata,type='candle',addplot=[adx15,dmp15,dmn15,bb1,bb2,bb3])
        #ani = animation.FuncAnimation(fig, animate, interval=1000)
        plt.show()    
    #chart(df)
    return df


