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

    sort_values = {
        "by": "timestamp",
        "ascending": True
    }
    drop = {
        "labels": ['symbol', 'trades' ,'vwap', 'lastSize', 'turnover', 'homeNotional', 'foreignNotional'],
        "axis": 1
    }
    rename = {
        "columns": {
            'open': 'Open',
            'close': 'Close',
            'high': 'High',
            'low': 'Low',
            'volume': 'Volume'
        },
        "inplace": True
    }

    df1min_orig = pd.DataFrame(timeframe1m[:], columns=timeframe1m[0]).sort_values(**sort_values).drop(**drop).rename(**rename)
    df1min_orig.index = pd.DatetimeIndex(df1min_orig['timestamp']) 

    df5min_orig = pd.DataFrame(timeframe5m[:], columns=timeframe5m[0]).sort_values(**sort_values).drop(**drop).rename(**rename)
    df5min_orig.index = pd.DatetimeIndex(df5min_orig['timestamp']) 

    df60min_orig = pd.DataFrame(timeframe1h[:], columns=timeframe1h[0]).sort_values(**sort_values).drop(**drop).rename(**rename)
    df60min_orig.index = pd.DatetimeIndex(df60min_orig['timestamp'])     
    #df = df.resample('15min', offset="-5T").apply(ohlc)#EXPERIMENTAL Gives signal way faster

    df2m = df1min_orig.resample('2min', closed='right').apply(ohlc)##Lags few minutes
    df3m = df1min_orig.resample('3min', closed='right').apply(ohlc)##Lags few minutes
    df10m = df5min_orig.resample('10min', closed='right').apply(ohlc)##Lags few minutes
    df15m = df5min_orig.resample('15min', closed='right').apply(ohlc)##Lags few minutes
    df30m = df5min_orig.resample('30min', closed='right').apply(ohlc)##Lags few minutes
    df45m = df5min_orig.resample('45min', closed='right').apply(ohlc)##Lags few minutes
 

    timeframe1m = df1min_orig.join([
        tanalysis.Fetch(df1min_orig),
        indi.supertrend(df1min_orig, period=12, ATR_multiplier=3)
    ])

    timeframe2m = df2m.join([
        tanalysis.Fetch(df2m),
        indi.supertrend(df2m, period=12, ATR_multiplier=3)
    ])

    timeframe3m = df3m.join([
        tanalysis.Fetch(df3m),
        indi.supertrend(df3m, period=12, ATR_multiplier=3)
    ])

    timeframe5m = df5min_orig.join([
        tanalysis.Fetch(df5min_orig),
        indi.supertrend(df5min_orig, period=12, ATR_multiplier=3)
    ])

    timeframe10m = df10m.join([
        tanalysis.Fetch(df10m),
        indi.supertrend(df10m, period=12, ATR_multiplier=3)
    ])

    timeframe15m = df15m.join([
        tanalysis.Fetch(df15m),
        indi.supertrend(df15m, period=12, ATR_multiplier=3)
    ])

    timeframe30m = df30m.join([
        tanalysis.Fetch(df30m),
        indi.supertrend(df30m, period=12, ATR_multiplier=3)
    ])

    timeframe45m = df45m.join([
        tanalysis.Fetch(df45m),
        indi.supertrend(df45m, period=12, ATR_multiplier=3)
    ])

    timeframe1h = df60min_orig.join([
        tanalysis.Fetch(df60min_orig),
        indi.supertrend(df60min_orig, period=12, ATR_multiplier=3)
    ])  

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