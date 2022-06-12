import sys
import pandas
from inspect import stack

from position_sniper import tanalysis
from position_sniper import indicators as indi
from market_maker.settings import settings
from market_maker.market_maker import OrderManager

class CustomOrderManager(OrderManager):
    """A sample order manager for implementing your own custom strategy"""

    def __init__(self):
        super().__init__()

        # prepare dataframe
        candles = self.exchange.bitmex.get_candles(bucket='1m', symbol=settings.SYMBOL, reverse='true', count=100)
        sort_values = { "by": "timestamp", "ascending": True }
        drop = { "labels": ['symbol', 'trades' ,'vwap', 'lastSize', 'turnover', 'homeNotional', 'foreignNotional'], "axis": 1 }
        rename = {
            "columns": {
                'open': 'Open',
                'close': 'Close',
                'high': 'High',
                'low': 'Low',
                'volume': 'Volume'
            }
        }
        df = pandas.DataFrame(candles[:], columns=candles[0]).sort_values(**sort_values).drop(**drop).rename(**rename)
        df = tanalysis.Fetch(df)
        df = df.join(indi.supertrend(df, period=12, ATR_multiplier=3))
        df.to_csv("datas/" + __file__.split('/')[-1].replace('.py','') +".csv")

    def sanity_check(self) -> None:
        super().sanity_check()

        # update dataframe (TODO)


    def place_orders(self) -> None:
        # implement your custom strategy here

        buy_orders = []
        sell_orders = []

        # populate buy and sell orders, e.g.
        # buy_orders.append({'price': 999.0, 'orderQty': 100, 'side': "Buy"})
        # sell_orders.append({'price': 1001.0, 'orderQty': 100, 'side': "Sell"})

        self.converge_orders(buy_orders, sell_orders)


def run() -> None:
    order_manager = CustomOrderManager()

    # Try/except just keeps ctrl-c from printing an ugly stacktrace
    try:
        order_manager.run_loop()
    except (KeyboardInterrupt, SystemExit):
        sys.exit()
