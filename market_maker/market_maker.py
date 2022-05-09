from __future__ import absolute_import
from time import sleep
import sys
from datetime import datetime
from os.path import getmtime
import random
import requests
import atexit
import signal
from market_maker import bitmex
from market_maker.settings import settings
from market_maker.utils import log, constants, errors, math
from market_maker import tanalysis
from market_maker import indicators as indi 
from market_maker import prepare_ta as prep
from market_maker import macd_strat as macd_strat
import pandas as pd
import math as math_round



# Used for reloading the bot - saves modified times of key files
import os
watched_files_mtimes = [(f, getmtime(f)) for f in settings.WATCHED_FILES]


#
# Helpers
#
logger = log.setup_custom_logger('root')


class ExchangeInterface:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        if len(sys.argv) > 1:
            self.symbol = sys.argv[1]
        else:
            self.symbol = settings.SYMBOL
        self.bitmex = bitmex.BitMEX(base_url=settings.BASE_URL, symbol=self.symbol,
                                    apiKey=settings.API_KEY, apiSecret=settings.API_SECRET,
                                    orderIDPrefix=settings.ORDERID_PREFIX, postOnly=settings.POST_ONLY,
                                    timeout=settings.TIMEOUT)

    def cancel_order(self, order):
        tickLog = self.get_instrument()['tickLog']
        logger.info("Canceling: %s %d @ %.*f" %
                    (order['side'], order['orderQty'], tickLog, order['price']))
        while True:
            try:
                self.bitmex.cancel(order['orderID'])
                sleep(settings.API_REST_INTERVAL)
            except ValueError as e:
                logger.info(e)
                sleep(settings.API_ERROR_INTERVAL)
            else:
                break

    def cancel_all_orders(self,stops=True):
        if self.dry_run:
            return
        if stops:
            logger.info("Canceling all existing orders, including stops.")
        elif not stops:
            logger.info("Canceling all existing orders, excluding stops.")
        tickLog = self.get_instrument()['tickLog']

        # In certain cases, a WS update might not make it through before we call this.
        # For that reason, we grab via HTTP to ensure we grab them all.
        orders = self.bitmex.http_open_orders()

        for order in orders:
            if order['ordType'] == "Stop" and stops:
                logger.info(f"Canceling stop {order['leavesQty']} @ ${order['stopPx']}")
                self.bitmex.cancel(order['orderID'])
            else:
                if not order['ordType'] == "Stop":
                    logger.info(f"Canceling: {order['side']} {order['orderQty']} @ ${order['price']}")
                    self.bitmex.cancel(order['orderID'])
                    

        #if len(orders):
        #    self.bitmex.cancel([order['orderID'] for order in orders])



        sleep(settings.API_REST_INTERVAL)

    def get_portfolio(self):
        contracts = settings.CONTRACTS
        portfolio = {}
        for symbol in contracts:
            position = self.bitmex.position(symbol=symbol)
            instrument = self.bitmex.instrument(symbol=symbol)

            if instrument['isQuanto']:
                future_type = "Quanto"
            elif instrument['isInverse']:
                future_type = "Inverse"
            elif not instrument['isQuanto'] and not instrument['isInverse']:
                future_type = "Linear"
            else:
                raise NotImplementedError(
                    "Unknown future type; not quanto or inverse: %s" % instrument['symbol'])

            if instrument['underlyingToSettleMultiplier'] is None:
                multiplier = float(
                    instrument['multiplier']) / float(instrument['quoteToSettleMultiplier'])
            else:
                multiplier = float(
                    instrument['multiplier']) / float(instrument['underlyingToSettleMultiplier'])

            portfolio[symbol] = {
                "currentQty": float(position['currentQty']),
                "futureType": future_type,
                "multiplier": multiplier,
                "markPrice": float(instrument['markPrice']),
                "spot": float(instrument['indicativeSettlePrice'])
            }

        return portfolio

    def calc_delta(self):
        """Calculate currency delta for portfolio"""
        portfolio = self.get_portfolio()
        spot_delta = 0
        mark_delta = 0
        for symbol in portfolio:
            item = portfolio[symbol]
            if item['futureType'] == "Quanto":
                spot_delta += item['currentQty'] * \
                    item['multiplier'] * item['spot']
                mark_delta += item['currentQty'] * \
                    item['multiplier'] * item['markPrice']
            elif item['futureType'] == "Inverse":
                spot_delta += (item['multiplier'] /
                               item['spot']) * item['currentQty']
                mark_delta += (item['multiplier'] /
                               item['markPrice']) * item['currentQty']
            elif item['futureType'] == "Linear":
                spot_delta += item['multiplier'] * item['currentQty']
                mark_delta += item['multiplier'] * item['currentQty']
        basis_delta = mark_delta - spot_delta
        delta = {
            "spot": spot_delta,
            "mark_price": mark_delta,
            "basis": basis_delta
        }
        return delta

    def get_delta(self, symbol=None):
        if symbol is None:
            symbol = self.symbol
        return self.get_position(symbol)['currentQty']

    def get_instrument(self, symbol=None):
        if symbol is None:
            symbol = self.symbol
        return self.bitmex.instrument(symbol)

    def get_margin(self):
        if self.dry_run:
            return {'marginBalance': float(settings.DRY_BTC), 'availableFunds': float(settings.DRY_BTC)}
        return self.bitmex.funds()

    def get_orders(self):
        if self.dry_run:
            return []
        return self.bitmex.open_orders()

    def get_highest_buy(self):
        buys = [o for o in self.get_orders() if o['side'] == 'Buy']
        if not len(buys):
            return {'price': -2**32}
        highest_buy = max(buys or [], key=lambda o: o['price'])
        return highest_buy if highest_buy else {'price': -2**32}

    def get_lowest_sell(self):
        sells = [o for o in self.get_orders() if o['side'] == 'Sell']
        if not len(sells):
            return {'price': 2**32}
        lowest_sell = min(sells or [], key=lambda o: o['price'])
        # ought to be enough for anyone
        return lowest_sell if lowest_sell else {'price': 2**32}
        
    def amend_orders(self, orders):
        if self.dry_run:
            return orders
        return self.bitmex.amend_orders(orders)

    def get_position(self, symbol=None):
        if symbol is None:
            symbol = self.symbol
        return self.bitmex.position(symbol)

    def get_ticker(self, symbol=None):
        if symbol is None:
            symbol = self.symbol
        return self.bitmex.ticker_data(symbol)

    def is_open(self):
        """Check that websockets are still open."""
        return not self.bitmex.ws.exited

    def check_market_open(self):
        instrument = self.get_instrument()
        if instrument["state"] != "Open" and instrument["state"] != "Closed":
            raise errors.MarketClosedError("The instrument %s is not open. State: %s" %
                                           (self.symbol, instrument["state"]))

    def get_avgentry(self, symbol=None):
        if symbol is None:
            symbol = self.symbol
        return self.get_position(symbol)['avgEntryPrice'] 

    def get_stops(self):
        if self.dry_run:
            return []
        return self.bitmex.open_stops()   

    def check_if_orderbook_empty(self):
        """This function checks whether the order book is empty"""
        instrument = self.get_instrument()
        if instrument['midPrice'] is None:
            raise errors.MarketEmptyError("Orderbook is empty, cannot quote")

class OrderManager:
    def __init__(self):
        self.exchange = ExchangeInterface(settings.DRY_RUN)
        # Once exchange is created, register exit handler that will always cancel orders
        # on any error.
        atexit.register(self.exit)
        signal.signal(signal.SIGTERM, self.exit)

        logger.info("Using symbol %s." % self.exchange.symbol)

        self.start_time = datetime.now()
        self.instrument = self.exchange.get_instrument()
        self.starting_qty = self.exchange.get_delta()
        self.running_qty = self.starting_qty
        self.trigger=False
        self.trigged=False
        self.in_trade=False
        self.stoploss=False
        self.times=100
        self.initialpos=0
        self.notification=False
        self.avg_entry=0
        with open("balance.log") as f:
            self.firstbalance = f.readlines()[0].rstrip()        
        # self.reset()

    def reset(self):
        self.exchange.cancel_all_orders(stops=False)
        self.sanity_check()
        self.print_status()

        # Create orders and converge.
        self.place_orders()

    def print_status(self):
        """Print the current MM status."""
        self.times+=1
        if self.times < 10:
            return
        self.times=0


        sys.stdout.write("-----\n")
        margin = self.exchange.get_margin()
        position = self.exchange.get_position()
        self.running_qty = self.exchange.get_delta()
        tickLog = self.exchange.get_instrument()['tickLog']
        self.start_XBt = margin["marginBalance"]
        f = open("balance.log", "a")
        f.write(str(XBt_to_XBT(self.start_XBt))+ "\n")
        f.close()
        profit=XBt_to_XBT(self.start_XBt) - float(self.firstbalance)
        logger.info(f"Current XBT Balance: {XBt_to_XBT(self.start_XBt):.6f} (Start Balance: {float(self.firstbalance):.6f})") 
        logger.info(f"Profit launch of strategy: {profit:.4f}BTC ({(profit/float(self.firstbalance)):.0%} of initial investment)") 

        if position['currentQty'] != 0:
            #logger.info(f"Avg Cost Price: ${float(position['avgCostPrice'])})")
            logger.info(f"Current Contract Position: {self.running_qty} @ ${(float(position['avgEntryPrice']))} entry ")

    #        logger.info(f"Avg Entry Price: ${(float(position['avgEntryPrice']))}")
        #logger.info("Contracts Traded This Run: %d" %
        #            (self.running_qty - self.starting_qty))
            logger.info(f"Total Contract Delta: {round(self.exchange.calc_delta()['spot'],6)}")
        logger.info(f"Max loss per trade: {settings.RISK:.0%} ")
        if self.initialpos != 0 and self.avg_entry != 0:
            logger.info(f"Last pos variable: {self.initialpos}")
            logger.info(f"Dynamic avg_entry variable: {self.avg_entry}")

    def get_ticker(self):
        ticker = self.exchange.get_ticker()
        tickLog = self.exchange.get_instrument()['tickLog']

        # Set up our buy & sell positions as the smallest possible unit above and below the current spread
        # and we'll work out from there. That way we always have the best price but we don't kill wide
        # and potentially profitable spreads.
        self.start_position_buy = ticker["buy"] + self.instrument['tickSize']
        self.start_position_sell = ticker["sell"] - self.instrument['tickSize']

        # If we're maintaining spreads and we already have orders in place,
        # make sure they're not ours. If they are, we need to adjust, otherwise we'll
        # just work the orders inward until they collide.
        if settings.MAINTAIN_SPREADS:
            if ticker['buy'] == self.exchange.get_highest_buy()['price']:
                self.start_position_buy = ticker["buy"]
            if ticker['sell'] == self.exchange.get_lowest_sell()['price']:
                self.start_position_sell = ticker["sell"]

        # Back off if our spread is too small.
        if self.start_position_buy * (1.00 + settings.MIN_SPREAD) > self.start_position_sell:
            self.start_position_buy *= (1.00 - (settings.MIN_SPREAD / 2))
            self.start_position_sell *= (1.00 + (settings.MIN_SPREAD / 2))

        # Midpoint, used for simpler order placement.
        self.start_position_mid = ticker["mid"]
        #logger.info(
        #    "%s Ticker: Buy: %.*f, Sell: %.*f" %
        #    (self.instrument['symbol'], tickLog,
        #     ticker["buy"], tickLog, ticker["sell"])
        #)
        #logger.info('Start Positions: Buy: %.*f, Sell: %.*f, Mid: %.*f' %
        #            (tickLog, self.start_position_buy, tickLog, self.start_position_sell,
        #             tickLog, self.start_position_mid))
        return ticker

    def get_price_offset(self, index):
        """Given an index (1, -1, 2, -2, etc.) return the price for that side of the book.
           Negative is a buy, positive is a sell."""
        # Maintain existing spreads for max profit
        if settings.MAINTAIN_SPREADS:
            start_position = self.start_position_buy if index < 0 else self.start_position_sell
            # First positions (index 1, -1) should start right at start_position, others should branch from there
            index = index + 1 if index < 0 else index - 1
        else:
            # Offset mode: ticker comes from a reference exchange and we define an offset.
            start_position = self.start_position_buy if index < 0 else self.start_position_sell

            # If we're attempting to sell, but our sell price is actually lower than the buy,
            # move over to the sell side.
            if index > 0 and start_position < self.start_position_buy:
                start_position = self.start_position_sell
            # Same for buys.
            if index < 0 and start_position > self.start_position_sell:
                start_position = self.start_position_buy

        return math.toNearest(start_position * (1 + settings.INTERVAL) ** index, self.instrument['tickSize'])

    ###
    # Orders
    ###

    def place_orders(self):
        """Create order items for use in convergence."""

        buy_orders = []
        sell_orders = []
        # Create orders from the outside in. This is intentional - let's say the inner order gets taken;
        # then we match orders from the outside in, ensuring the fewest number of orders are amended and only
        # a new order is created in the inside. If we did it inside-out, all orders would be amended
        # down and a new order would be created at the outside.
        for i in reversed(range(1, settings.ORDER_PAIRS + 1)):
            if not self.long_position_limit_exceeded():
                buy_orders.append(self.prepare_order(-i))
            if not self.short_position_limit_exceeded():
                sell_orders.append(self.prepare_order(i))

        return self.converge_orders(buy_orders, sell_orders)



    ###
    # Position Limits
    ###

    def short_position_limit_exceeded(self):
        """Returns True if the short position limit is exceeded"""
        if not settings.CHECK_POSITION_LIMITS:
            return False
        position = self.exchange.get_delta()
        return position <= settings.MIN_POSITION

    def long_position_limit_exceeded(self):
        """Returns True if the long position limit is exceeded"""
        if not settings.CHECK_POSITION_LIMITS:
            return False
        position = self.exchange.get_delta()
        return position >= settings.MAX_POSITION

    ###
    # Sanity
    ##

    def sanity_check(self):
        """Perform checks before placing orders."""
        # Check if OB is empty - if so, can't quote.
        self.exchange.check_if_orderbook_empty()

        # Ensure market is still open.
        self.exchange.check_market_open()

        # Get ticker, which sets price offsets and prints some debugging info.
        ticker = self.get_ticker()

        # Sanity check:
        if self.get_price_offset(-1) >= ticker["sell"] or self.get_price_offset(1) <= ticker["buy"]:
            logger.error("Buy: %s, Sell: %s" %
                        (self.start_position_buy, self.start_position_sell))
            logger.error("First buy position: %s\nBitMEX Best Ask: %s\nFirst sell position: %s\nBitMEX Best Bid: %s" %
                        (self.get_price_offset(-1), ticker["sell"], self.get_price_offset(1), ticker["buy"]))
            logger.error("Sanity check failed, exchange data is inconsistent")
            sys.exit(1)
            self.exit()

        # Messaging if the position limits are reached
        if self.long_position_limit_exceeded():
            logger.info("Long delta limit exceeded")
            logger.info("Current Position: %.f, Maximum Position: %.f" %
                        (self.exchange.get_delta(), settings.MAX_POSITION))

        if self.short_position_limit_exceeded():
            logger.info("Short delta limit exceeded")
            logger.info("Current Position: %.f, Minimum Position: %.f" %
                        (self.exchange.get_delta(), settings.MIN_POSITION))

    ###
    # Running
    ###

    def check_file_change(self):
        """Restart if any files we're watching have changed."""
        for f, mtime in watched_files_mtimes:
            if getmtime(f) > mtime:
                logger.info("***************************************************************")
                logger.info("* A change in the code has been detected, reloading instance! *")
                logger.info("***************************************************************")

                sys.exit(1)
                self.restart()

    def check_connection(self):
        """Ensure the WS connections are still open."""
        return self.exchange.is_open()

    def exit(self):
        logger.info("Shutting down.")
        try:
            #self.exchange.cancel_all_orders()
            self.exchange.bitmex.exit()
        except errors.AuthenticationError as e:
            logger.info("Was not authenticated; could not cancel orders.")
        except Exception as e:
            logger.info("Unable to cancel orders: %s" % e)

        sys.exit()

    def run_loop(self):
        while True:

            sys.stdout.flush()

            self.check_file_change()
            sleep(settings.LOOP_INTERVAL)

            # This will restart on very short downtime, but if it's longer,
            # the MM will crash entirely as it is unable to connect to the WS on boot.
            if not self.check_connection():
                logger.error(
                    "Realtime data connection unexpectedly closed, restarting.")
                sys.exit(1)
                self.restart()

            self.sanity_check()  # Ensures health of mm - several cut-out points here
            self.print_status()  # Print skew, delta, etc
            self.place_orders()  # Creates desired orders and converges to existing orders

    def restart(self):
        logger.info("Restarting the market maker...")
        os.execv(sys.executable, [sys.executable] + sys.argv)

#
# Helpers
#


def XBt_to_XBT(XBt):
    return float(XBt) / constants.XBt_TO_XBT


def cost(instrument, quantity, price):
    mult = instrument["multiplier"]
    P = mult * price if mult >= 0 else mult / price
    return abs(quantity * P)


def margin(instrument, quantity, price):
    return cost(instrument, quantity, price) * instrument["initMargin"]


def run():
    logger.info('Position sniper ^_^ © %s\n' % constants.VERSION)

    #om = OrderManager()
    om = CustomOrderManager()
    # Try/except just keeps ctrl-c from printing an ugly stacktrace
    try:
        om.run_loop()
    except (KeyboardInterrupt, SystemExit):
        sys.exit()

from market_maker.market_maker import OrderManager

class CustomOrderManager(OrderManager):
    logger.info('Custom strat')

    def place_orders(self) -> None:

    ##########################
    # Technical preparations #
    ##########################
        timeframe1m=self.exchange.bitmex.get_candles(bucket='1m', symbol=settings.SYMBOL, reverse='true', count=1000)
        timeframe5m=self.exchange.bitmex.get_candles(bucket='5m', symbol=settings.SYMBOL, reverse='true', count=1000)
        timeframe1h=self.exchange.bitmex.get_candles(bucket='1h', symbol=settings.SYMBOL, reverse='true', count=1000)
        """NOTE some timeframes are derived from 1min and 5min candles inside prepare so no need to pass them from here"""
        timeframe1m,timeframe2m,timeframe3m,timeframe5m,timeframe10m,timeframe15m,timeframe30m,timeframe45m,timeframe1h = prep.prepare(timeframe1m, timeframe5m, timeframe1h)
    # END TECHNICAL PREPARATIONS #

    #####################################
    ## Variables used for calculations ##
    #####################################
        position=self.exchange.get_position()['currentQty']
        if position != 0:
            self.in_trade=True
        else:
            self.in_trade=False
    ### END VARIABLES ###

    ###########################
    ## Trade helper function ##
    ###########################
        def rounddown(x):
            return int(math_round.floor(x / 100.0)) * 100
    ### END TRADE HELPER FUNCTION ###

        macd_strat.check_trigger(self,timeframe1h,"1h")
        macd_strat.check_trigger(self,timeframe45m,"45min")
        macd_strat.check_trigger(self,timeframe30m,"30min")
        macd_strat.check_trigger(self,timeframe15m,"15min")
        macd_strat.check_trigger(self,timeframe10m,"10min")
        macd_strat.check_trigger(self,timeframe5m,"5min",timeframe15m)
        macd_strat.check_trigger(self,timeframe3m,"3min",timeframe15m)
        macd_strat.check_trigger(self,timeframe2m,"2min",timeframe15m)
        macd_strat.check_trigger(self,timeframe1m,"1min",timeframe5m)
