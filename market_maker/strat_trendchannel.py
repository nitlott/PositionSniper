############################
# MACD STRAT @ ZLX EDITION #
############################
from market_maker.settings import settings
from market_maker.utils import log, math
from time import sleep
import math as math_round
import requests

import pandas as pd
logger = log.setup_custom_logger('root')

def check_trigger(self,data,tf=None,bigger_picture=None):
    """Helpers"""

    def XBt_to_XBT(XBt):
        return float(XBt) / 100000000
    def rounddown(x):
        return int(math_round.floor(x / 100.0)) * 100

    """Variables"""
    if tf != None:
        timeframe=tf
    ticker = self.get_ticker()
    existing_orders = self.exchange.get_orders()
    existing_stops = self.exchange.get_stops()
    margin = self.exchange.get_margin()
    balance = XBt_to_XBT(margin["marginBalance"])
    highest_buy = self.exchange.get_instrument()['bidPrice']
    lowest_sell = self.exchange.get_instrument()['askPrice']
    lastprice = self.exchange.get_instrument()['lastPrice'] 
    tickLog = self.exchange.get_instrument()['tickLog']

    positiondata = self.exchange.get_position()
    position = positiondata['currentQty']
    avg_entry=positiondata['avgEntryPrice']
    if isinstance(bigger_picture, pd.DataFrame):
        logger.debug("Using bigger picture for entry criterias.")
        bigema200=bigger_picture.EMA200[-1]
        bigatr=bigger_picture.ATR[-1]
        ema200=data.EMA200[-1]
        atr=data.ATR[-1]
    else:
        logger.debug("Using current timeframe for entry criterias.")
        ema200=data.EMA200[-1]
        atr=data.ATR[-1]
        bigema200=data.EMA200[-1]
        bigatr=data.ATR[-1]

    ordernum=0
    stopnum=0
    for order in existing_orders:
        ordernum+=1
    for order in existing_stops:
        stopnum+=1
    if position !=0:
        self.in_trade=True
        #self.print_status()
        if self.avg_entry==0:
            self.avg_entry=positiondata['avgEntryPrice']

    elif position == 0:
        #self.print_status()
        self.in_trade=False
        self.avg_entry=0
    if position !=0 and self.initialpos == 0:
        self.initialpos=position

    if (stopnum !=0 or ordernum !=0) and not self.in_trade: #Wipe it all if old orders on board...
        logger.info("Removing unrelated orders.")
        self.exchange.cancel_all_orders()
        self.initialpos = 0
        self.avg_entry=0
    elif (stopnum > 1 or ordernum > 3) and self.in_trade:
        logger.info("Fixing num of orders.")
        self.exchange.cancel_all_orders(stops=False)
    """Variables END"""


    """Trigger part for triggering events"""
    self.trigger=False
    trigger_type="nothing"
    if data.IDD and data.SFXSTATE == 'sideways':
        trigger_type="short" # nuke
    else if data.IDD:
        trigger_type="long" # dollar
    else if data.IDU and data.SFXSTATE == 'trend' and data.SMMA2_TEETH > data.SMMA2_TEETH[-1] and data.Close > data.Open:
        trigger_type="long" # bomb
    else if data.IDU and data.SFXSTATE == 'trend' and data.SMMA2_TEETH < data.SMMA2_TEETH[-1] and data.Close < data.Open:
        trigger_type="short" # hammer

    if trigger_type != 'nothing' and self.previous_trigger != trigger_type
        self.trigger=True
        self.previous_trigger = trigger_type
    """Trigger part END"""



    """Amend stop and update self.avg_entry/initialpos if a target seams to been hit."""
    amend_stop=True
    if stopnum >= 1 and position != self.initialpos and amend_stop and self.in_trade:
        to_amend=[]
        for stop in existing_stops:
            if abs(self.initialpos) <= abs(stop['leavesQty']):
                if position > 0:
                    desierd_stopPx = math.toNearest(self.avg_entry,self.instrument['tickSize'])
                    desired_qty = -abs(position)
                elif position < 0:
                    desierd_stopPx = math.toNearest(self.avg_entry,self.instrument['tickSize'])
                    desired_qty = abs(position)
                current_stopPx = math.toNearest(stop['stopPx'],self.instrument['tickSize'])
                if desierd_stopPx != current_stopPx:
                    to_amend.append({'orderID': stop['orderID'],'stopPx': desierd_stopPx, 'orderQty': stop['cumQty'] + desired_qty, 'side': stop['side']})
        if len(to_amend) > 0:
            for amended_order in reversed(to_amend):
                reference_order = [o for o in existing_stops if o['orderID'] == amended_order['orderID']][0]
                logger.info(f"Amending {amended_order['side']}: {reference_order['leavesQty']} @ {reference_order['stopPx']} to {(amended_order['orderQty'] - reference_order['cumQty'])} @ {amended_order['stopPx']}({(amended_order['stopPx'] - reference_order['stopPx'])})")

            try:
                self.exchange.amend_orders(to_amend)
                if position > 0:
                    self.avg_entry=self.avg_entry*settings.ENTRY_AFTER_AMEND
                elif position <0:
                    self.avg_entry=self.avg_entry/settings.ENTRY_AFTER_AMEND
                print("avg_entry modified:", self.avg_entry )
                self.initialpos=position
            except requests.exceptions.HTTPError as e:
                errorObj = e.response.json()
                if errorObj['error']['message'] == 'Invalid ordStatus':
                    logger.warn("Amending failed. Waiting for order data to converge and retrying.")
                    sleep(0.5)
                    return self.place_orders()
                else:
                    logger.error("Unknown error on amend: %s. Exiting" % errorObj)
                    sys.exit(1)
    """Amend stop and update self.avg_entry/initialpos if a target seams to been hit.END"""

    """Dynamic targets"""                        
    if settings.TAKEPROFIT:
        if position > 100:
            half_pos=abs(rounddown(position/4))
        elif position < -100:
            half_pos=abs(rounddown(abs(position)/4))
        else:
            half_pos=100
        if half_pos > 100:
            half_half_pos=abs(rounddown(half_pos/2))
        elif half_pos < -100:
            half_half_pos=abs(rounddown(abs(half_pos)/2))
        else:
            half_half_pos=100            
        if half_pos < 100:
            half_pos=100
        buy_x=0
        sell_x=0
        stoploss_x=0
        if position > 0:
            positiondata = self.exchange.get_position()
            avg_entry=positiondata['avgEntryPrice']
            existing_orders = self.exchange.get_orders()
            for order in existing_orders:
                if order['side'] == 'Sell':
                    sell_x+=1
        elif position < 0:
            existing_orders = self.exchange.get_orders()
            for order in existing_orders:
                if order['side'] == 'Buy':
                    buy_x+=1
        if buy_x == 0 and position < 0:
            existing_stops = self.exchange.get_stops()
            for order in existing_stops:
                if order['ordType'] == 'Stop' and order['side'] == 'Buy':
                    stoploss_x=order['stopPx']
                    target=math.toNearest((self.avg_entry - (stoploss_x - self.avg_entry)*settings.TP_MULTIPLIER),self.instrument['tickSize'])
                    self.exchange.bitmex.place_order(abs(half_pos), target)
                    sleep(2)
        elif sell_x==0 and position > 0:
            positiondata = self.exchange.get_position()
            avg_entry=positiondata['avgEntryPrice']            
            existing_stops = self.exchange.get_stops()
            for order in existing_stops:
                if order['ordType'] == 'Stop' and order['side'] == 'Sell':
                    stoploss_x=order['stopPx']
                    target=math.toNearest(((self.avg_entry - stoploss_x)*settings.TP_MULTIPLIER)+self.avg_entry,self.instrument['tickSize'])
                    self.exchange.bitmex.place_order(-abs(half_pos), target)
                    sleep(2)
        elif buy_x == 1 and position <= -200:
            existing_stops = self.exchange.get_stops()
            for order in existing_stops:
                if order['ordType'] == 'Stop' and order['side'] == 'Buy':
                    stoploss_x=order['stopPx']
                    target=math.toNearest(((stoploss_x - self.avg_entry)*settings.TP_MULTIPLIER2)-self.avg_entry,self.instrument['tickSize'])
                    self.exchange.bitmex.place_order(abs(half_half_pos), abs(target))
                    sleep(2)
        elif sell_x==1 and position >= 200:
            positiondata = self.exchange.get_position()
            avg_entry=positiondata['avgEntryPrice']            
            existing_stops = self.exchange.get_stops()
            for order in existing_stops:
                if order['ordType'] == 'Stop' and order['side'] == 'Sell':
                    stoploss_x=order['stopPx']
                    target=math.toNearest(((self.avg_entry - stoploss_x)*settings.TP_MULTIPLIER2)+self.avg_entry,self.instrument['tickSize'])
                    self.exchange.bitmex.place_order(-abs(half_half_pos), target)       
                    sleep(2)
        elif buy_x == 2 and position <= -500:
            existing_stops = self.exchange.get_stops()
            for order in existing_stops:
                if order['ordType'] == 'Stop' and order['side'] == 'Buy':
                    stoploss_x=order['stopPx']
                    target=math.toNearest(((stoploss_x - self.avg_entry)*settings.TP_MULTIPLIER3)-self.avg_entry,self.instrument['tickSize'])
                    self.exchange.bitmex.place_order(abs(half_half_pos), abs(target))
                    sleep(2)
        elif sell_x==2 and position >= 500:
            positiondata = self.exchange.get_position()
            avg_entry=positiondata['avgEntryPrice']            
            existing_stops = self.exchange.get_stops()
            for order in existing_stops:
                if order['ordType'] == 'Stop' and order['side'] == 'Sell':
                    stoploss_x=order['stopPx']
                    target=math.toNearest(((self.avg_entry - stoploss_x)*settings.TP_MULTIPLIER3)+self.avg_entry,self.instrument['tickSize'])
                    self.exchange.bitmex.place_order(-abs(half_half_pos), target)       
                    sleep(2)                    
    """Dynamic targets END"""                        


    disable_below=True
    """Reverse signal take profit/amend stop"""
    if self.in_trade and not self.trigged and not disable_below:#and self.trigger 
        if data.trend[-1] == -1 and position > 0 and trigger_type=="short":#
            self.trigged=True
            to_amend=[]
            existing_stops = self.exchange.get_stops()            
            """Take profit from a long"""
            if lastprice / avg_entry >= 1.005:
                if not settings.REVERSAL_AMEND:
                    self.exchange.bitmex.close_position()
                    self.initialpos = 0
                    sleep(10)
                    self.trigger=False
                    self.trigged=False
                    self.in_trade=False
                    self.avg_entry=0
                elif  stopnum > 0 and settings.REVERSAL_AMEND:
                    for stop in existing_stops:
                        if abs(self.initialpos) == abs(stop['leavesQty']):
                            desierd_stopPx = math.toNearest(avg_entry*1.0025,self.instrument['tickSize'])
                            current_stopPx = math.toNearest(stop['stopPx'],self.instrument['tickSize'])
                            desired_qty = position
                            current_qty = self.initialpos     
                            if desierd_stopPx != current_stopPx:
                                to_amend.append({'orderID': stop['orderID'], 'orderQty': stop['cumQty'] + desired_qty, 'side': stop['side']})                                  
        elif data.trend[-1] == 1 and position < 0 and trigger_type=="long":#
            self.trigged=True
            to_amend=[]
            existing_stops = self.exchange.get_stops()              
            """Take profit from a short"""
            if avg_entry / lastprice >= 1.005:
                if not settings.REVERSAL_AMEND:
                    self.exchange.bitmex.close_position()
                    self.initialpos = 0
                    sleep(10)
                    self.trigger=False
                    self.trigged=False
                    self.in_trade=False
                    self.avg_entry=0    
                elif  stopnum > 0 and settings.REVERSAL_AMEND:
                    for stop in existing_stops:
                        if abs(self.initialpos) == abs(stop['leavesQty']):
                            desierd_stopPx = math.toNearest(avg_entry/1.0025,self.instrument['tickSize'])
                            current_stopPx = math.toNearest(stop['stopPx'],self.instrument['tickSize'])
                            desired_qty = position
                            current_qty = self.initialpos     
                            if desierd_stopPx != current_stopPx:
                                #to_amend.append({'orderID': stop['orderID'], 'orderQty': stop['cumQty'] + desired_qty, 'side': stop['side']})    
                                to_amend.append({'orderID': stop['orderID'],'stopPx': desierd_stopPx, 'orderQty': stop['cumQty'] + desired_qty, 'side': stop['side']})


    if position != self.initialpos and amend_stop and position != 0:

#if using for orders#  if desired_order['orderQty'] != stop['leavesQty'] or ( desired_order['price'] != order['price'] and abs((desired_order['price'] / order['price']) - 1) > settings.RELIST_INTERVAL):
                    #to_amend.append({'orderID': stop['orderID'], 'orderQty': stop['cumQty'] + desired_order['orderQty'], 'price': desired_order['price'], 'side': stop['side']})

            if len(to_amend) > 0:
                for amended_order in reversed(to_amend):
                    reference_order = [o for o in existing_stops if o['orderID'] == amended_order['orderID']][0]
                    logger.info(f"Amending {amended_order['side']}: {reference_order['leavesQty']} @ {reference_order['stopPx']} to {(amended_order['orderQty'] - reference_order['cumQty'])} @ {amended_order['stopPx']}({(amended_order['stopPx'] - reference_order['stopPx'])})")

                try:
                    self.exchange.amend_orders(to_amend)
                    if position > 0:
                        self.avg_entry=self.avg_entry*settings.ENTRY_AFTER_AMEND
                    elif position <0:
                        self.avg_entry=self.avg_entry/settings.ENTRY_AFTER_AMEND                    
                except requests.exceptions.HTTPError as e:
                    errorObj = e.response.json()
                    if errorObj['error']['message'] == 'Invalid ordStatus':
                        logger.warn("Amending failed. Waiting for order data to converge and retrying.")
                        sleep(0.5)
                        return self.place_orders()
                    else:
                        logger.error("Unknown error on amend: %s. Exiting" % errorObj)
                        sys.exit(1)






    #print("EMA200:", ema200, " Close:", data.Close[-1])
    """FINALLY OPEN POSITION IF NOTHING ELSE HAPPEND AND GOT A TRIGGER"""
    if  (data.Close[-1] > bigema200) and (data.Close[-1] > ema200) and trigger_type == "long" and not self.in_trade: #data['kijun'][-1] > data['EMA50'][-1] and

        self.trigged=True  #To make sure we dont double trigger stuff
        self.in_trade=True  #To make sure we dont double trigger stuff
        """UP TREND MACD"""
        #logger.info("Betting on uptrend (MACD)")
        logger.info(f"Betting on uptrend  {timeframe}")
        ##Set stop distance before riskformula
        if data.trend[-1] == 1:
            temp=abs(lastprice - data.uptrend[-1])
        else:
            temp=bigatr*settings.ATR_STOP_MULTIPLIER
        if temp / lastprice > 0.01:
            temp=lastprice * 0.01
        stoploss_price=math.toNearest(lastprice-(temp),self.instrument['tickSize'])   

        ##Risk formula
        stop_percent=(lastprice - stoploss_price)/lastprice     
        maxloss=balance*settings.RISK*lastprice
        maxposition=maxloss/stop_percent
        maxposition=rounddown(maxposition)
        if maxposition==0:
            maxposition=100
            logger.info("Warning overrisking this trade!")
        logger.info(f"Stopdistance {round(stop_percent*100,2)}%")
        logger.info(f"Maximum loss $ {round(maxloss,2)}")                
        logger.info(f"Set Entry to: {lastprice}")
        logger.info(f"Set Stoploss to: {maxposition} @ {stoploss_price}")
        ##End riskformula
        self.stoploss=False
        if stopnum !=0 or ordernum !=0: #Wipe it all if old orders on board...
            self.exchange.cancel_all_orders()

        try:
            self.exchange.bitmex.place_stop(quantity=-abs(maxposition),stopPx=stoploss_price)
            self.stoploss=True
        except:
            pass
        logger.info(f"Dont exceed {maxposition} contracts..")


        if self.stoploss:
            price=lowest_sell
            quantity=abs(maxposition)
            try:
                self.exchange.bitmex.place_order(quantity, price)
                logger.info(f"Placing {quantity} contracts long @ ${price}")
                self.initialpos = quantity
                sleep(2)
            except:
                pass


    elif (data.Close[-1] < ema200) and (data.Close[-1] < ema200) and trigger_type == "short" and not self.in_trade: #data['kijun'][-1] < data['EMA50'][-1] and 
        self.trigged=True  #To make sure we dont double trigger stuff
        self.in_trade=True  #To make sure we dont double trigger stuff
        """DOWN TREND MACD"""                
        #logger.info("Betting on downtrend (MACD)")
        logger.info(f"Betting on downtrend {timeframe}")
        if data.trend[-1]==-1:
            temp=abs(data.downtrend[-1] - lastprice)
        else:
            temp=bigatr*settings.ATR_STOP_MULTIPLIER
        if temp / lastprice > 0.01:
            temp=lastprice * 0.01
        stoploss_price=math.toNearest((temp+lastprice),self.instrument['tickSize'])

        if data.trend[-1] == 1:
            temp=lastprice - data.trend[-1]

        stop_percent=abs((lastprice - stoploss_price)/lastprice)     
        maxloss=balance*settings.RISK*lastprice
        maxposition=maxloss/stop_percent
        maxposition=rounddown(maxposition)
        maxposition=-maxposition

        if maxposition==0:
            maxposition=100
            logger.info("Warning overrisking this trade #YOLO!")
        logger.info(f"Set Entry to: {lastprice}")
        logger.info(f"Stopdistance {round(stop_percent*100,2)}%")
        logger.info(f"Maximum loss $ {maxloss}")
        logger.info(f"Set Stoploss to: {maxposition} @ {stoploss_price}")
        self.stoploss=False
        if stopnum !=0 or ordernum !=0: #Wipe it all if old orders on board...
            self.exchange.cancel_all_orders()
        try:
            self.exchange.bitmex.place_stop(quantity=abs(maxposition),stopPx=stoploss_price)
            self.stoploss=True
        except:
            pass
        if self.stoploss:
            price=highest_buy
            quantity=-abs(maxposition)
            try:
                self.exchange.bitmex.place_order(quantity, price)
                logger.info(f"Placing {quantity} contracts short @ ${price}")
                sleep(2)
                self.initialpos = quantity
            except:
                pass
    """FINALLY OPEN POSITION IF NOTHING ELSE HAPPEND AND GOT A TRIGGER END"""




#########Check ner hit!

##
##Safety feature below
##

    if position == 0:
        self.in_trade=False
    else:
        self.in_trade=True
        stops_s=0
        stops_b=0
        positiondata = self.exchange.get_position()
        avg_entry=positiondata['avgEntryPrice']
        existing_stops = self.exchange.get_stops()
        for order in existing_stops:
            if order['ordType'] == 'Stop' and order['side'] == 'Sell':
                stops_s+=1
            elif order['ordType'] == 'Stop' and order['side'] == 'Buy':
                stops_b+=1
        if position > 0 and stops_s==0:
            if data.trend[-1] == 1:
                temp=avg_entry - data.uptrend[-1]
            else:
                temp=atr*settings.ATR_STOP_MULTIPLIER
            if temp / avg_entry > 0.01:
                temp=lastprice * 0.01
            stoploss_price=math.toNearest((avg_entry - temp),self.instrument['tickSize'])
            try:
                self.exchange.bitmex.place_stop(quantity=-abs(position),stopPx=stoploss_price)
                self.stoploss=True
                logger.info("stop placed")
            except:
                logger.info("Some error with stop placement")   
        elif position < 0 and stops_b==0:
            if data.trend[-1] == -1:
                temp=data.downtrend[-1] - avg_entry
            else:
                temp=atr*settings.ATR_STOP_MULTIPLIER
            if temp / avg_entry > 0.01:
                temp=lastprice * 0.01
            stoploss_price=math.toNearest((temp + avg_entry),self.instrument['tickSize'])       
            try:
                self.exchange.bitmex.place_stop(quantity=abs(position),stopPx=stoploss_price)     
                self.stoploss=True
                logger.info("stop placed")
            except:
                logger.info("Some error with stop placement")   

#####Take Profit section
    if self.in_trade and self.trigger:
        lastprice = self.exchange.get_instrument()['lastPrice'] 
        positiondata = self.exchange.get_position()
        avg_entry=positiondata['avgEntryPrice']
        if position > 0 and data.trend[-1] == -1:
            """Take profit from a long"""
            if lastprice / self.avg_entry >= 1.005:
                self.exchange.bitmex.close_position()

        elif position < 0 and data.trend[-1] == 1:
            """Take profit from a short"""
            if self.avg_entry / lastprice >= 1.005:
                self.exchange.bitmex.close_position()


