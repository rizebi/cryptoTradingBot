#! /usr/bin/python3
import os
import sys
import time # for sleep
import sqlite3 # for database connection
import logging # for logging
import datetime # for logging
import requests # for HTTP requests
import traceback # for error handling
import configparser # for configuration parser

from functools import wraps # for measuring time of function
from binance.client import Client
from binance.exceptions import BinanceAPIException

from binanceManager import getCurrencyBalance
from binanceManager import buyCrypto
from binanceManager import sellCrypto

from databaseManager import createTables
from databaseManager import getPriceHistory
from databaseManager import getLastTransactionStatus
from databaseManager import insertTradeHistory
from databaseManager import emptyTradeHistoryDatabase
from databaseManager import arePricesGoingUp
from databaseManager import getOldestPriceAfterCurrentDatapoint
from databaseManager import getMaximumPriceAfterTimestamp
from databaseManager import getFirstRealPriceAfterTimestamp
# Used for backtesting
from databaseManager import loadDatabaseInMemory
from databaseManager import writeDatabaseOnDisk
from databaseManager import readPriceHistoryInMemory
from databaseManager import countTradesFromDB
##### Constants #####
currentDir = os.getcwd()
configFile = "./configuration.cfg"
configSection = "configuration"
config = ""
binanceClient = ""

# Logging function
def getLogger():
  # Create logs folder if not exists
  if not os.path.isdir(os.path.join(currentDir, "logs")):
    try:
      os.mkdir(os.path.join(currentDir, "logs"))
    except OSError:
      print("Creation of the logs directory failed")
    else:
      print("Successfully created the logs directory")

  now = datetime.datetime.now()
  log_name = "" + str(now.year) + "." + '{:02d}'.format(now.month) + "." + '{:02d}'.format(now.day) + "-bot.log"
  log_name = os.path.join(currentDir, "logs", log_name)
  logging.basicConfig(format='%(asctime)s  %(message)s', level=logging.NOTSET,
                      handlers=[
                      logging.FileHandler(log_name),
                      logging.StreamHandler()
                      ])
  log = logging.getLogger()
  return log

# Wrapper used to measure function times
def fn_timer(function):
    @wraps(function)
    def function_timer(*args, **kwargs):
        t0 = time.time()
        result = function(*args, **kwargs)
        t1 = time.time()
        print ("######## Total time running %s : %s seconds" %
               (function.__name__, str(t1-t0))
               )
        return result
    return function_timer

# Function that sends a message to Telegram
def sendMessage(config, message):
  log = config["log"]
  try:
    payload = {
        'chat_id': config["bot_chat_id"],
        'text': "[bot]" + message,
        'parse_mode': 'HTML'
    }
    if config["telegram_notifications"] == "true":
      requests.post("https://api.telegram.org/bot{token}/sendMessage".format(token=config["bot_token"]), data=payload).content
  except Exception as e:
    log.info("Error when sending Telegram message: {}".format(e))
    tracebackError = traceback.format_exc()
    log.info(tracebackError)

def constructHistory(config, coin, aggregatedBy, lookBackIntervals, timeBetweenRuns):
  log = config["log"]
  # Get the price history from database
  realHistory = getPriceHistory(config, coin, aggregatedBy * lookBackIntervals)

  if len(realHistory) < aggregatedBy * lookBackIntervals:
    return [], []

  # len(realHistory) == (lookBackIntervals * aggregatedBy)
  i = 0
  aggregatedHistory = []
  while i < len(realHistory):
    suma = 0
    j = 0
    while j < aggregatedBy:
      suma += realHistory[i]
      i += 1
      j += 1
    aggregatedHistory.append(suma/aggregatedBy)

  return realHistory, aggregatedHistory

# Function that makes the trades
def trade(config):
  log = config["log"]

  # Function that is called when a buy trade should be made
  def buyHandler(config, currentDollars, cryptoQuantity, buyReason):
    log = config["log"]
    sendMessage = config["sendMessage"]
    tradeAggregatedPrice = currentAggregatedPrice
    message = "[BUY] " + buyReason + "\n"
    message += "aggregatedHistory:\n"
    for price in aggregatedHistory:
      message += str(price) + "\n"
    message += "##########\n"
    message += "currentRealPrice = " + str(currentRealPrice) + "\n"
    message += "tradeAggregatedPrice = " + str(tradeAggregatedPrice) + "\n"
    message += "averagelookBackIntervalsDatapointsIndex = " + str('{:.10f}'.format(averagelookBackIntervalsDatapointsIndex)) + "\n"
    message += "lastlookBackIntervalsIndexTreshold = " + str('{:.10f}'.format(lastlookBackIntervalsIndexTreshold)) + "\n"
    log.info(message)
    sendMessage(config, message)
    tradeRealPrice = buyCrypto(config)

    # Insert in trade_history
    if config["backtesting"] == "false":
      # Update variables
      cryptoQuantity = getCurrencyBalance(config, 'BTC')
      currentDollars = getCurrencyBalance(config, 'USDT')
    else:
      tradeRealPrice = currentRealPrice
      tradeAggregatedPrice = currentAggregatedPrice
      cryptoQuantity = currentDollars / tradeRealPrice
      cryptoQuantity -= float(config["backtesting_commision"]) * cryptoQuantity
      currentDollars = 0
    insertTradeHistory(config, currentTime, coin, "BUY", tradeRealPrice, tradeAggregatedPrice, currentDollars, cryptoQuantity)

  def sellHandler(config, currentDollars, cryptoQuantity, sellReason):
    log = config["log"]
    sendMessage = config["sendMessage"]
    tradeAggregatedPrice = currentAggregatedPrice
    message = "[SELL] " + sellReason + "\n"
    message += "aggregatedHistory:\n"
    for price in aggregatedHistory:
      message += str(price) + "\n"
    message += "##########\n"
    message += "currentRealPrice = " + str(currentRealPrice) + "\n"
    message += "tradeAggregatedPrice = " + str(tradeAggregatedPrice) + "\n"
    message += "maximumPrice = " + str(maximumPrice) + "\n"
    message += "maximumAggregatedPrice = " + str(maximumAggregatedPrice) + "\n"
    message += "aquisitionDiffPrice = " + str(aquisitionDiffPrice) + "\n"
    message += "peakDiffPrice = " + str(peakDiffPrice) + "\n"
    message += "peakIndex = " + str(peakIndex) + "\n"
    message += "peakIndexTreshold = " + str(peakIndexTreshold) + "\n"
    log.info(message)
    sendMessage(config, message)
    # Actual sell
    tradeRealPrice = sellCrypto(config)

    # Insert in trade_history
    if config["backtesting"] == "false":
      # Update variables
      cryptoQuantity = getCurrencyBalance(config, 'BTC')
      currentDollars = getCurrencyBalance(config, 'USDT')
    else:
      tradeRealPrice = currentRealPrice
      tradeAggregatedPrice = currentAggregatedPrice
      currentDollars = cryptoQuantity * tradeRealPrice
      # Substract here for the BUY commision
      currentDollars -= 0.001 * currentDollars
      cryptoQuantity = 0
    insertTradeHistory(config, currentTime, coin, "SELL", tradeRealPrice, tradeAggregatedPrice, currentDollars, cryptoQuantity)

  def backtestingPrintStatistics(config):
    log = config["log"]
    log.info("####################")
    log.info("Backtesting ended. Statistics:")
    log.info("Full simulation took: " + str(time.time() - allScriptStartTime) + " seconds.")
    log.info("Start time of simulation: " + str(config["backtesting_start_timestamp"]) + " = " + datetime.datetime.fromtimestamp(int(config["backtesting_start_timestamp"])).strftime("%Y-%m-%d_%H-%M-%S"))
    log.info("End time of simulation: " + str(config["backtesting_end_timestamp"]) + " = " + datetime.datetime.fromtimestamp(int(config["backtesting_end_timestamp"])).strftime("%Y-%m-%d_%H-%M-%S"))
    minimumAnalized = max(int(config["backtesting_start_timestamp"]), int(config["priceDictionary"]['BTCUSDT'][0][0]))
    maximumAnalized = min(int(config["backtesting_end_timestamp"]), int(config["priceDictionary"]['BTCUSDT'][-1][0]))
    log.info("Actual start time of simulation: " + str(minimumAnalized) + " = " + datetime.datetime.fromtimestamp(int(minimumAnalized)).strftime("%Y-%m-%d_%H-%M-%S"))
    log.info("Actual end time of simulation: " + str(maximumAnalized) + " = " + datetime.datetime.fromtimestamp(int(maximumAnalized)).strftime("%Y-%m-%d_%H-%M-%S"))
    minutesAnalized = (maximumAnalized - minimumAnalized) / 60
    hoursAnalized = minutesAnalized / 60
    daysAnalized = hoursAnalized / 24
    log.info("Minutes analized: " + str(minutesAnalized))
    log.info("Hours analized: " + str(hoursAnalized))
    log.info("Days analized: " + str(daysAnalized))

    try:
      log.info("currentRealPrice = " + str(currentRealPrice))
      log.info("currentAggregatedPrice = " + str(currentAggregatedPrice))
      log.info("doWeHaveCrypto = " + str(doWeHaveCrypto))
      log.info("tradeRealPrice = " + str(tradeRealPrice))
      log.info("tradeAggregatedPrice = " + str(tradeAggregatedPrice))
      if doWeHaveCrypto == True:
        log.info("currentDollars = " + str(cryptoQuantity * tradeRealPrice))
        log.info("cryptoQuantity = " + str(0))
      else:
        log.info("currentDollars = " + str(currentDollars))
        log.info("cryptoQuantity = " + str(cryptoQuantity))
      log.info("Individual trades made: " + str(countTradesFromDB(config)))
    except:
      pass
    # Write the database back on disk
    writeDatabaseOnDisk(config)


  # First we need to get the current state of liquidity
  # Extrapolate to many coins if the case
  coin = config["coins_to_scrape"].split("|")[0]

  # Get parameters from config
  # Sell if difference between maximum price for current trade - current price > peakIndexTreshold
  peakIndexTreshold = float(config["peak_index_treshold"])
  peakIndexTresholdIgnoreCooldown = float(config["peak_index_treshold_ignore_cooldown"])
  # Buy if difference between current price and lookBackIntervals datapoints ago is bigger than lastlookBackIntervalsIndexTreshold
  lastlookBackIntervalsIndexTreshold = float(config["buy_lookback_intervals_index_treshold"])
  lastlookBackIntervalsIndexTresholdIgnoreCooldown = float(config["buy_lookback_intervals_index_treshold_ignore_cooldown"])
  cooldownMinutesBuy = int(config["cooldown_minutes_buy"])
  cooldownMinutesSellPeak = int(config["cooldown_minutes_sell_peak"])
  cooldownMinutesSellBuyPrice = int(config["cooldown_minutes_sell_buy_price"])
  # Mow many datapoints to aggregate (average)
  aggregatedBy = int(config["aggregated_by"])
  # The bot will buy if  the current price is above average for lookBackIntervals
  # These are big intervals. Aggregated ones
  lookBackIntervals = int(config["buy_lookback_intervals"])
  # Time between runs
  timeBetweenRuns = int(config["seconds_between_scrapes"])

  # Backtesting configurations
  if config["backtesting"] == "true":
    emptyTradeHistoryDatabase(config)
    loadDatabaseInMemory(config) # For quicker reads for backtesting
    readPriceHistoryInMemory(config) # For even quicker reads for backtesting
    config["currentDatapoint"] = config["backtesting_start_timestamp"] # for backtesting

    # runOnce is needed for backtesting in order to stop when end is reached
    runOnce = False # for backtesting

    # For backtesting do not create all the time the binanceClient
    binanceClient = Client(config["api_key"], config["api_secret_key"])
    config["binanceClient"] = binanceClient

    # Use for backtesting to calculate the full time of script run
    allScriptStartTime = time.time()

  #######################
  #### Eternal While ####
  #######################
  loopOldTime = time.time()
  while True:
    # Update logger handler
    log = getLogger()
    config["log"] = log

    # If need to measure performance issues
    #loopCurrentTime = time.time()
    #log.info("######## This loop took: " + str(loopCurrentTime - loopOldTime) + " seconds.")
    #loopOldTime = loopCurrentTime

    # Get Binance Client everytime, because after some time it may behave wrong
    if config["backtesting"] == "false":
      binanceClient = Client(config["api_key"], config["api_secret_key"])
      config["binanceClient"] = binanceClient
      currentTime = int(time.time())
      log.info("[Datapoint: " + str(currentTime) + " = " + datetime.datetime.fromtimestamp(int(currentTime)).strftime("%Y-%m-%d_%H-%M-%S") + "] ######################################################")
    else:
      config["currentDatapoint"] = getOldestPriceAfterCurrentDatapoint(config, coin)

      if config["currentDatapoint"] < int(config["backtesting_start_timestamp"]):
        log.info("Prices between [backtesting_start_timestamp; backtesting_end_timestamp] not present in database")
        # Backtesting ended. Print statistics and exit.
        backtestingPrintStatistics(config)
        return
      currentTime = config["currentDatapoint"]
      log.info("[Datapoint: " + str(config["currentDatapoint"]) + " = " + datetime.datetime.fromtimestamp(int(config["currentDatapoint"])).strftime("%Y-%m-%d_%H-%M-%S") + "] ######################################################")

    # Get price history
    realHistory, aggregatedHistory = constructHistory(config, coin, aggregatedBy, lookBackIntervals, timeBetweenRuns)
    if len(realHistory) == 0:
      if config["backtesting"] == "true":
        if runOnce == True:
          # Backtesting ended. Print statistics and exit.
          backtestingPrintStatistics(config)
          return
          #sys.exit(0)
      log.info("Too few data to aggregate")
      time.sleep(timeBetweenRuns)
      continue

    # Get last transaction status
    status = getLastTransactionStatus(config, coin)
    lastTradeTimestamp = int(status["timestamp"])
    doWeHaveCrypto = status["doWeHaveCrypto"]
    tradeRealPrice = status["tradeRealPrice"]
    tradeAggregatedPrice = status["tradeAggregatedPrice"]
    currentDollars = status["currentDollars"]
    cryptoQuantity = status["cryptoQuantity"]
    gainOrLoss = status["gainOrLoss"]
    maximumPrice = status["maximumPrice"]
    maximumAggregatedPrice = status["maximumAggregatedPrice"]

    # Log the minutes since last trades
    minutesSinceLastTrade = int((currentTime - lastTradeTimestamp) / 60)
    log.info("minutesSinceLastTrade = " + str(minutesSinceLastTrade))

    if config["backtesting"] == "true":
      runOnce = True

    # Now the logic comes. To buy, to wait, to sell
    currentRealPrice = realHistory[-1]
    currentAggregatedPrice = aggregatedHistory[-1]
    # Print stats
    log.info("currentRealPrice = " + str(currentRealPrice))
    log.info("currentAggregatedPrice = " + str(currentAggregatedPrice))
    log.info("doWeHaveCrypto = " + str(doWeHaveCrypto))
    if doWeHaveCrypto == True:
      log.info("tradeRealPrice = " + str(tradeRealPrice))
      log.info("tradeAggregatedPrice = " + str(tradeAggregatedPrice))
      log.info("maximumPrice = " + str(maximumPrice))
      log.info("maximumAggregatedPrice = " + str(maximumAggregatedPrice))
    log.info("aggregatedHistory = " + str(aggregatedHistory))

    # Calculate change in the last lookBackIntervals datapoints
    averagelookBackIntervalsDataPoints = sum(aggregatedHistory[(-1) * lookBackIntervals:])/lookBackIntervals
    averagelookBackIntervalsDataPointsDiff = currentAggregatedPrice - averagelookBackIntervalsDataPoints
    averagelookBackIntervalsDatapointsIndex = averagelookBackIntervalsDataPointsDiff / averagelookBackIntervalsDataPoints
    log.info("averagelookBackIntervalsDataPointsDiff = " + str(averagelookBackIntervalsDataPointsDiff))
    log.info("averagelookBackIntervalsDatapointsIndex = " + str('{:.10f}'.format(averagelookBackIntervalsDatapointsIndex)))
    log.info("lastlookBackIntervalsIndexTreshold = " + str('{:.10f}'.format(lastlookBackIntervalsIndexTreshold)))
    log.info("lastlookBackIntervalsIndexTresholdIgnoreCooldown = " + str('{:.10f}'.format(lastlookBackIntervalsIndexTresholdIgnoreCooldown)))


    if doWeHaveCrypto == True:
      # If this is true, the logic is the same as in the beggining
      # If this is false, we will sell if average(aggregated_by) < agerage(aggregated_by * buy_lookback_intervals)
      useSellStrategyPeakIndex = config["use_sell_strategy_peak_index"]
      ### THIS SHOULD BE TRUE! False is for testing new strategy mode

      # Calculate peakIndex
      aquisitionDiffPrice = currentRealPrice - tradeRealPrice
      peakDiffPrice = currentAggregatedPrice - maximumAggregatedPrice
      peakIndex = peakDiffPrice / maximumAggregatedPrice
      log.info("aquisitionDiffPrice = " + str(aquisitionDiffPrice))
      log.info("peakDiffPrice = " + str(peakDiffPrice))
      log.info("peakIndex = " + str('{:.10f}'.format(peakIndex)))
      #log.info("peakIndexTreshold = " + str('{:.10f}'.format(peakIndexTreshold)))
      #log.info("peakIndexTresholdIgnoreCooldown = " + str('{:.10f}'.format(peakIndexTresholdIgnoreCooldown)))

      if useSellStrategyPeakIndex == "true":
        if peakIndex >= 0:
          gain = aquisitionDiffPrice * cryptoQuantity
          log.info("GOOD JOB. WE ARE MAKING MONEY. Gainings for this trade: " + str(gain) + "$.")
          # TODO Do we really should exit here?
          time.sleep(timeBetweenRuns)
          continue
        else:
          # If the real prices (not aggregated) are in a positive trend, do not sell
          if arePricesGoingUp(config, coin, "SELL") == True:
            log.info("KEEP. peakIndex is negative, but current trend is positive. Continue.")
            time.sleep(timeBetweenRuns)
            continue
          else:
            log.info("Realtime trend is down. If we decide to sell, we can sell.")

          # This protects us from bot restarts. If maximum was long time ago, but the market is growing, that's it. We missed it.
          # At least do not sell only to want to buy back.
          # TODO, backtest!!!
          #if averagelookBackIntervalsDatapointsIndex > 0:
          #  log.info("KEEP. Maybe we should have sold, but the buying strategy tells to buy if we did not have crypto")
          #  time.sleep(timeBetweenRuns)
          #  continue

          # SELL strategy 1 (sell if exceeded index from peak)

          # peakIndex < 0
          if peakIndex < (-1) * peakIndexTreshold:
            if currentTime - lastTradeTimestamp < 60 * int(cooldownMinutesSellPeak):
              if peakIndex < (-1) * peakIndexTresholdIgnoreCooldown:
                # We exceeded the BIG treshold, get out. Ignore cooldown
                # SELL
                sellHandler(config, currentDollars, cryptoQuantity, "We exceeded the BIG treshold, get out, ignoring cooldown")
                time.sleep(timeBetweenRuns)
                continue
              log.info("WAIT FOR COOLDOWN. No selling due to peakIndex < (-1) * peakIndexTreshold")
              waitMinutes = int(((60 * int(cooldownMinutesBuy)) - (currentTime - lastTradeTimestamp)) / 60)
              log.info("Wait at least " + str(waitMinutes) + " more minutes.")
              #time.sleep(timeBetweenRuns)
              #continue
            else:
              # We exceeded treshold, get out
              # SELL
              sellHandler(config, currentDollars, cryptoQuantity, "We exceeded treshold, get out")
              time.sleep(timeBetweenRuns)
              continue
          else:
            # We did not exceeded treshold, maybe we will come back
            log.info("Treshold not exceeded. KEEP")
            #time.sleep(timeBetweenRuns)
            #continue

        # From many test, this should be off (as it was for full March because of a bug)
        # SELL strategy 2 (sell if currentAggregatedPrice < tradeAggregatedPrice)
#         if currentAggregatedPrice < tradeAggregatedPrice:
#           if currentTime - lastTradeTimestamp < 60 * int(cooldownMinutesSellBuyPrice):
#             log.info("WAIT FOR COOLDOWN. No selling due to currentAggregatedPrice < tradeAggregatedPrice")
#             waitMinutes = int(((60 * int(cooldownMinutesBuy)) - (currentTime - lastTradeTimestamp)) / 60)
#             log.info("Wait at least " + str(waitMinutes) + " more minutes.")
#             #time.sleep(timeBetweenRuns)
#             #continue
#           else:
#             # SELL
#             sellHandler(config, currentDollars, cryptoQuantity, "currentAggregatedPrice < tradeAggregatedPrice")
#             time.sleep(timeBetweenRuns)
#             continue

        # SELL strategy 3 (sell if realPrice(sell_price_abruptly_drops_minutes ago) dropped by sell_price_abruptly_drops_index_treshold
        timestampMinutesAgo = currentTime - (60 * int(config["sell_price_abruptly_drops_minutes"]))
        realPriceAgo = getFirstRealPriceAfterTimestamp(config, coin, timestampMinutesAgo)
        realPriceDiffPrice = currentRealPrice - realPriceAgo
        realPriceAgoIndex = realPriceDiffPrice / realPriceAgo
        log.info("DEBUG - realPriceAgo = " + str(realPriceAgo))
        log.info("DEBUG - realPriceDiffPrice = " + str(realPriceDiffPrice))
        log.info("DEBUG - realPriceAgoIndex = " + str(realPriceAgoIndex))
        if realPriceAgoIndex < (-1) * float(config["sell_price_abruptly_drops_index_treshold"]):
          # SELL
          sellHandler(config, currentDollars, cryptoQuantity, "Seems abrupt drop. Sell.")
          time.sleep(timeBetweenRuns)
          continue

      else:
        # SELL strategy 4. Sell with the same logic as buy but reverse.
        if averagelookBackIntervalsDatapointsIndex > 0 or arePricesGoingUp(config, coin, "SELL") == False:
          log.info("WAIT. Do not sell. Market going up")
          time.sleep(timeBetweenRuns)
          continue
        else:
          if currentTime - lastTradeTimestamp < 60 * int(cooldownMinutesBuy):
              log.info("WAIT FOR COOLDOWN. No selling.")
              waitMinutes = int(((60 * int(cooldownMinutesBuy)) - (currentTime - lastTradeTimestamp)) / 60)
              log.info("Wait at least " + str(waitMinutes) + " more minutes.")
              time.sleep(timeBetweenRuns)
              continue
          else:
            sellReason = "Sell the same logic as buy "
          # Buy
          sellHandler(config, currentDollars, cryptoQuantity, sellReason)
          time.sleep(timeBetweenRuns)
          continue
    else:
      # We do not have crypto
      # Should we buy?

      # BUY Strategy 1 (buy if averagelookBackIntervalsDatapointsIndex > lastlookBackIntervalsIndexTreshold)
      if averagelookBackIntervalsDatapointsIndex < 0 or arePricesGoingUp(config, coin, "BUY") == False:
        log.info("WAIT. Do not buy. Market going down")
        time.sleep(timeBetweenRuns)
        continue
      else:
        if averagelookBackIntervalsDatapointsIndex < lastlookBackIntervalsIndexTreshold:
          log.info("WAIT. Do not buy. Too little increase.")
          time.sleep(timeBetweenRuns)
          continue
        else:
          if currentTime - lastTradeTimestamp < 60 * int(cooldownMinutesBuy):
            if averagelookBackIntervalsDatapointsIndex < lastlookBackIntervalsIndexTresholdIgnoreCooldown:
              log.info("WAIT FOR COOLDOWN. No buying.")
              waitMinutes = int(((60 * int(cooldownMinutesBuy)) - (currentTime - lastTradeTimestamp)) / 60)
              log.info("Wait at least " + str(waitMinutes) + " more minutes.")
              time.sleep(timeBetweenRuns)
              continue
            else:
              buyReason = "BIG increase. Buy ignoring treshold"
          else:
            buyReason = "Seems increase. Buy"
          # Buy
          # So it seems that we want to buy. We will calculate if currentAggregatedPrice is less than the maximumAggregatedPrice, for the maximum price in the last 30 minutes. If current is higher, will buy.

#           firstTimestampToLookForMaximumBeforeBuy = currentTime - (60 * int(config["minutes_lookback_maximum_before_buy"]))
#           log.info("DEBUG - bot - try to getMaximumPriceAfterTimestamp")
#           maximumPrice, maximumAggregatedPrice = getMaximumPriceAfterTimestamp(config, firstTimestampToLookForMaximumBeforeBuy)
#           log.info("Found in the last " + str(config["minutes_lookback_maximum_before_buy"]) + " minutes:")
#           log.info("maximumPrice = " + str(maximumPrice))
#           log.info("maximumAggregatedPrice = " + str(maximumAggregatedPrice))
#           if maximumAggregatedPrice > currentAggregatedPrice:
#             log.info("%%%%%%%%%%%%%")
#             log.info("We should have bought, but maximumAggregatedPrice < currentAggregatedPrice. Continue.")
#             time.sleep(timeBetweenRuns)
#             continue

          buyHandler(config, currentDollars, cryptoQuantity, buyReason)
          time.sleep(timeBetweenRuns)
          continue
    # In case we have missed a time.sleep in the logic
    time.sleep(timeBetweenRuns)

# Main function
def mainFunction():
  # Initialize the logger
  log = getLogger()
  log.info("################################# New run")
  try:
    # Check if configuration file exists, and exit if it is not
    if os.path.isfile(configFile) is False:
      message = "[FATAL] Config file does not exist. Exiting"
      log.info(message)
      sendMessage(config, message)
      sys.exit(1)

    # Read config file
    configObj = configparser.ConfigParser()
    configObj.read(configFile)
    config = configObj._sections[configSection]
    config["sendMessage"] = sendMessage
    config["log"] = log
    sendMessage(config, "[INFO] Bot restarted")

    # Connect to database
    try:
      databaseClient = sqlite3.connect(config["database_file"])
    except Exception as e:
      message = "[FATAL] Couldn't connect to the database. Investigate manually"
      log.info(message)
      log.info(e)
      sendMessage(config, message)
      sys.exit(2)

    config["databaseClient"] = databaseClient
    # Create table if it not exists
    createTables(config)

    # The function should never end, that scrape, and write in the database
    trade(config)

    # Commit and close
    try:
      databaseClient.commit()
      databaseClient.close()
      message = "[FATAL] Unexpected end of script. Database successfully commited and closed"
      log.info(message)
      sendMessage(config, message)
    except Exception as e:
      message = "[FATAL] Unexpected end of script. Database successfully commited and closed"
      log.info(message)
      log.info("Fatal Error: {}".format(e))
      tracebackError = traceback.format_exc()
      log.info(tracebackError)
      sendMessage(config, message)


  ##### END #####
  except KeyboardInterrupt:
    try:
      databaseClient.commit()
      databaseClient.close()
    except:
      message = "[FATAL] Could not commit and close DB connection"
      log.info(message)
      sendMessage(config, message)
    log.info("DB commited and closed. Gracefully quiting")
    sys.exit(0)
  except Exception as e:
    log.info("Fatal Error: {}".format(e))
    tracebackError = traceback.format_exc()
    log.info(tracebackError)
    try:
      databaseClient.commit()
      databaseClient.close()
    except:
      message = "[FATAL] Could not commit and close DB connection."
      log.info(message)
      sendMessage(config, message)
    sendMessage(config, str(e) + "\n\n\n\n" + str(tracebackError))
    sys.exit(99)


##### BODY #####
if __name__ == "__main__":

  if len(sys.argv) != 1:
    log.info("Wrong number of parameters. Use: python bot.py")
    sys.exit(99)
  else:
    mainFunction()