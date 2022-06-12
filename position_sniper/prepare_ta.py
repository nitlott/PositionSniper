import pandas as pd 
from market_maker import tanalysis
from market_maker import indicators as indi

def prepare(timeframe1m,timeframe5m,timeframe1h):
    ohlc = {
    'Open': 'first',
    'High': 'max',
    'Low': 'min',
    'Close': 'last',
    'Volume': 'sum'
}   


    df1min_orig = pd.DataFrame(timeframe1m[:], columns=timeframe1m[0])
    df1min_orig=df1min_orig.sort_values(['timestamp'], ascending=[True])
    df1min_orig=df1min_orig.drop(['symbol', 'trades' ,'vwap', 'lastSize', 'turnover', 'homeNotional', 'foreignNotional'],axis=1)
    df1min_orig.rename(columns={'open': 'Open', 'close': 'Close'}, inplace=True)
    df1min_orig.rename(columns={'high': 'High', 'low': 'Low'}, inplace=True)
    df1min_orig.rename(columns={'volume': 'Volume'}, inplace=True)
    df1min_orig.index = pd.DatetimeIndex(df1min_orig['timestamp']) 

    df5min_orig = pd.DataFrame(timeframe5m[:], columns=timeframe5m[0])
    df5min_orig=df5min_orig.sort_values(['timestamp'], ascending=[True])
    df5min_orig=df5min_orig.drop(['symbol', 'trades' ,'vwap', 'lastSize', 'turnover', 'homeNotional', 'foreignNotional'],axis=1)
    df5min_orig.rename(columns={'open': 'Open', 'close': 'Close'}, inplace=True)
    df5min_orig.rename(columns={'high': 'High', 'low': 'Low'}, inplace=True)
    df5min_orig.rename(columns={'volume': 'Volume'}, inplace=True)
    df5min_orig.index = pd.DatetimeIndex(df5min_orig['timestamp']) 

    df60min_orig = pd.DataFrame(timeframe1h[:], columns=timeframe1h[0])
    df60min_orig=df60min_orig.sort_values(['timestamp'], ascending=[True])
    df60min_orig=df60min_orig.drop(['symbol', 'trades' ,'vwap', 'lastSize', 'turnover', 'homeNotional', 'foreignNotional'],axis=1)
    df60min_orig.rename(columns={'open': 'Open', 'close': 'Close'}, inplace=True)
    df60min_orig.rename(columns={'high': 'High', 'low': 'Low'}, inplace=True)
    df60min_orig.rename(columns={'volume': 'Volume'}, inplace=True)
    df60min_orig.index = pd.DatetimeIndex(df60min_orig['timestamp'])     
    #df = df.resample('15min', offset="-5T").apply(ohlc)#EXPERIMENTAL Gives signal way faster

    df2m = df1min_orig.resample('2min', closed='right').apply(ohlc)##Lags few minutes

    df3m = df1min_orig.resample('3min', closed='right').apply(ohlc)##Lags few minutes

    df10m = df5min_orig.resample('10min', closed='right').apply(ohlc)##Lags few minutes

    df15m = df5min_orig.resample('15min', closed='right').apply(ohlc)##Lags few minutes

    df30m = df5min_orig.resample('30min', closed='right').apply(ohlc)##Lags few minutes

    df45m = df5min_orig.resample('45min', closed='right').apply(ohlc)##Lags few minutes
 


    timeframe1m=tanalysis.Fetch(df1min_orig)
    timeframe2m=tanalysis.Fetch(df2m)
    timeframe3m=tanalysis.Fetch(df3m)
    timeframe5m=tanalysis.Fetch(df5min_orig)
    timeframe10m=tanalysis.Fetch(df10m)
    timeframe15m=tanalysis.Fetch(df15m)
    timeframe30m=tanalysis.Fetch(df30m)
    timeframe45m=tanalysis.Fetch(df45m)
    timeframe1h=tanalysis.Fetch(df60min_orig)

    supertrend = indi.supertrend(timeframe1m, period=12, ATR_multiplier=3)
    timeframe1m=timeframe1m.join(supertrend)

    supertrend = indi.supertrend(timeframe2m, period=12, ATR_multiplier=3)
    timeframe2m=timeframe2m.join(supertrend)

    supertrend = indi.supertrend(timeframe3m, period=12, ATR_multiplier=3)
    timeframe3m=timeframe3m.join(supertrend)

    supertrend = indi.supertrend(timeframe5m, period=12, ATR_multiplier=3)
    timeframe5m=timeframe5m.join(supertrend)

    supertrend = indi.supertrend(timeframe10m, period=12, ATR_multiplier=3)
    timeframe10m=timeframe10m.join(supertrend)

    supertrend = indi.supertrend(timeframe15m, period=12, ATR_multiplier=3)
    timeframe15m=timeframe15m.join(supertrend)

    supertrend = indi.supertrend(timeframe30m, period=12, ATR_multiplier=3)
    timeframe30m=timeframe30m.join(supertrend)

    supertrend = indi.supertrend(timeframe45m, period=12, ATR_multiplier=3)
    timeframe45m=timeframe45m.join(supertrend)

    supertrend = indi.supertrend(timeframe1h, period=12, ATR_multiplier=3)
    timeframe1h=timeframe1h.join(supertrend)            

    make_csv=True
    if make_csv:
        timeframe1m.to_csv("timeframe1m.csv")
        timeframe2m.to_csv("timeframe2m.csv")
        timeframe3m.to_csv("timeframe3m.csv")
        timeframe5m.to_csv("timeframe5m.csv")
        timeframe10m.to_csv("timeframe10m.csv")
        timeframe30m.to_csv("timeframe30m.csv")
        timeframe45m.to_csv("timeframe30m.csv")
        timeframe1h.to_csv("timeframe1h.csv")
        

    # print("1h:", timeframe1h.index.inferred_type)
    # print("45m:",  timeframe45m.index.inferred_type)
    return timeframe1m,timeframe2m,timeframe3m,timeframe5m,timeframe10m,timeframe15m,timeframe30m,timeframe45m,timeframe1h


    
    # classified_price_swings = indi.classify_swings(indi.find_swings(signals15m.filter(['Open', 'High', 'Low', 'Close'])))
    # classified_indicator_swings = indi.classify_swings(indi.find_swings(signals15m.filter(['MACD']),data_type='other'))
    # signals15m=signals15m.join(classified_indicator_swings)
    # signals15m.rename(columns={'Trend': 'div_trend'}, inplace=True)
    # divergence=indi.detect_divergence(classified_price_swings, classified_indicator_swings)
    # signals15m=signals15m.join(divergence)

    # classified_price_swings = indi.classify_swings(indi.find_swings(signals1h.filter(['Open', 'High', 'Low', 'Close'])))
    # classified_indicator_swings = indi.classify_swings(indi.find_swings(signals1h.filter(['MACD']),data_type='other'))
    # divergence=indi.detect_divergence(classified_price_swings, classified_indicator_swings)
    # signals1h=signals1h.join(divergence)