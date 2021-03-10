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

from binance.client import Client
from binance.exceptions import BinanceAPIException

from binanceManager import getCurrencyBalance
from binanceManager import buyCrypto
from binanceManager import sellCrypto

from databaseManager import createTables
from databaseManager import getPriceHistoryFromDatabase
from databaseManager import getPriceHistoryFromFile
from databaseManager import getLastTransactionStatus
from databaseManager import insertTradeHistory
from databaseManager import emptyTradeHistoryDatabase
from databaseManager import arePricesGoingUp
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
  log_name = "" + str(now.year) + "." + '{:02d}'.format(now.month) + "-bot.log"
  log_name = os.path.join(currentDir, "logs", log_name)
  logging.basicConfig(format='%(asctime)s  %(message)s', level=logging.NOTSET,
                      handlers=[
                      logging.FileHandler(log_name),
                      logging.StreamHandler()
                      ])
  log = logging.getLogger()
  return log

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

# For back-testing
def readDataFromFile(config):
  log = config["log"]
  priceFile = open(config["backtest_file"], "r")
  data = priceFile.read().split("\n")[0:-1]
  # Sanitize data
  dataPoints = []
  for element in data:
    if "nan" in element.lower():
      continue
    if len(element.split(",")) > 1:
      dataPoints.append(float(element.split(",")[1]))
    else:
      dataPoints.append(float(element))
  config["dataPoints"] = dataPoints

def constructHistory(config, coin, aggregatedBy, lookBackIntervals, timeBetweenRuns):
  log = config["log"]
  # Get the price history from database
  if config["dry_run"] == "false":
    realHistory = getPriceHistoryFromDatabase(config, coin, aggregatedBy * lookBackIntervals)
  else:
    realHistory = getPriceHistoryFromFile(config, coin, aggregatedBy * lookBackIntervals)
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
  def buyHandler(config, currentDollars, cryptoQuantity):
    log = config["log"]
    sendMessage = config["sendMessage"]
    tradeAggregatedPrice = currentAggregatedPrice
    message = "[BUY]\n"
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
    if config["dry_run"] == "false":
      # Update variables
      cryptoQuantity = getCurrencyBalance(config, 'BTC')
      currentDollars = getCurrencyBalance(config, 'USDT')
    else:
      tradeRealPrice = currentRealPrice
      tradeAggregatedPrice = currentAggregatedPrice
      cryptoQuantity = currentDollars / tradeRealPrice
      cryptoQuantity -= 0.001 * cryptoQuantity
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
    if config["dry_run"] == "false":
      # Update variables
      cryptoQuantity = getCurrencyBalance(config, 'BTC')
      currentDollars = getCurrencyBalance(config, 'USDT')
    else:
      tradeRealPrice = currentRealPrice
      tradeAggregatedPrice = currentAggregatedPrice
      currentDollars = cryptoQuantity * tradeRealPrice
      currentDollars -= 0.001 * currentDollars
      cryptoQuantity = 0
    insertTradeHistory(config, currentTime, coin, "SELL", tradeRealPrice, tradeAggregatedPrice, currentDollars, cryptoQuantity)


  # First we need to get the current state of liquidity
  # Extrapolate to many coins if the case
  coin = config["coins_to_scrape"].split("|")[0]

  # Get parameters from config
  # Sell if difference between maximum price for current trade - current price > peakIndexTreshold
  peakIndexTreshold = float(config["peak_index_treshold"])
  peakIndexTresholdIgnoreCooldown = float(config["peak_index_treshold_ignore_cooldown"])
  # Buy if difference between current price and lookBackIntervals datapoints ago is bigger than lastlookBackIntervalsIndexTreshold
  lastlookBackIntervalsIndexTreshold = float(config["buy_lookback_intervals_index_treshold"])
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

  # Dry run configurations
  config["currentDatapoint"] = 0 # for backtesting when reading from file
  runOnce = False # for backtesting
  if config["dry_run"] == "true":
    emptyTradeHistoryDatabase(config)
    readDataFromFile(config)
    # For dry run do not create all the time the binanceClient
    binanceClient = Client(config["api_key"], config["api_secret_key"])
    config["binanceClient"] = binanceClient
  while True:
    # Update logger handler
    log = getLogger()
    config["log"] = log
    currentTime = int(time.time())

    # Get Binance Client everytime, because after some time it may behave wrong
    if config["dry_run"] == "false":
      binanceClient = Client(config["api_key"], config["api_secret_key"])
      config["binanceClient"] = binanceClient

    config["currentDatapoint"] += 1
    if config["dry_run"] == "false":
      log.info("[Datapoint " + str(currentTime) + "] ######################################################")
    else:
      log.info("[Datapoint " + str(config["currentDatapoint"]) + "] ######################################################")
    # Get price history
    realHistory, aggregatedHistory = constructHistory(config, coin, aggregatedBy, lookBackIntervals, timeBetweenRuns)
    if len(realHistory) == 0:
      if config["dry_run"] == "true" and runOnce == True:
        log.info("####################")
        log.info("Backtesting ended. Statistics:")
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
        sys.exit(0)
      log.info("Too few data to aggregate")
      time.sleep(timeBetweenRuns)
      continue
    runOnce = True
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


    if doWeHaveCrypto == True:
      # Calculate peakIndex
      aquisitionDiffPrice = currentRealPrice - tradeRealPrice
      peakDiffPrice = currentAggregatedPrice - maximumAggregatedPrice
      peakIndex = peakDiffPrice / maximumAggregatedPrice
      log.info("aquisitionDiffPrice = " + str(aquisitionDiffPrice))
      log.info("peakDiffPrice = " + str(peakDiffPrice))
      log.info("peakIndex = " + str('{:.10f}'.format(peakIndex)))
      log.info("peakIndexTreshold = " + str('{:.10f}'.format(peakIndexTreshold)))
      log.info("peakIndexTresholdIgnoreCooldown = " + str('{:.10f}'.format(peakIndexTresholdIgnoreCooldown)))

      if peakIndex >= 0:
        gain = aquisitionDiffPrice * cryptoQuantity
        log.info("GOOD JOB. WE ARE MAKING MONEY. Gainings for this trade: " + str(gain) + "$.")
        time.sleep(timeBetweenRuns)
        continue
      else:
        # SELL strategy 1
        # If the real prices (not aggregated) are in a positive trend, do not sell
        if arePricesGoingUp(config, coin) == True:
          log.info("KEEP. peakIndex is negative, but current trend is positive.")
          time.sleep(timeBetweenRuns)
          continue
        else:
          log.info("Realtime trend is down. If we exceeded treshold, we will sell")

        # This protects us from bot restarts. If maximum was long time ago, but the market is growing, that's it. We missed it.
        # At least do not sell only to want to buy back.
        if averagelookBackIntervalsDatapointsIndex > 0 and averagelookBackIntervalsDatapointsIndex < lastlookBackIntervalsIndexTreshold:
          log.info("KEEP. Maybe we should have sold, but the buying strategy tells to buy if we did not have crypto")
          time.sleep(timeBetweenRuns)
          continue

        # peakIndex < 0
        if peakIndex < (-1) * peakIndexTreshold:
          if config["dry_run"] == "false":
            cooldownExpression = currentTime - lastTradeTimestamp < 60 * int(cooldownMinutesSellPeak)
          else:
            if lastTradeTimestamp == 0:
              cooldownExpression = False
            else:
              cooldownExpression = config["currentDatapoint"] - lastTradeTimestamp < int(cooldownMinutesSellPeak)
          if cooldownExpression:
            if peakIndex < (-1) * peakIndexTresholdIgnoreCooldown:
              # We exceeded the BIG treshold, get out. Ignore cooldown
              # SELL
              sellHandler(config, currentDollars, cryptoQuantity, "We exceeded the BIG treshold, get out, ignoring cooldown")
              time.sleep(timeBetweenRuns)
              continue
            log.info("WAIT FOR COOLDOWN. No selling due to peakIndex < (-1) * peakIndexTreshold")
            if config["dry_run"] == "false":
              waitMinutes = int(((60 * int(cooldownMinutesBuy)) - (currentTime - lastTradeTimestamp)) / 60)
            else:
              waitMinutes = int(cooldownMinutesBuy) - (config["currentDatapoint"] - lastTradeTimestamp)
            log.info("Wait at least " + str(waitMinutes) + " more minutes.")
            time.sleep(timeBetweenRuns)
            continue
          # We exceeded treshold, get out
          # SELL
          sellHandler(config, currentDollars, cryptoQuantity, "We exceeded treshold, get out")
          time.sleep(timeBetweenRuns)
          continue
        else:
          # We did not exceeded treshold, maybe we will come back
          log.info("Treshold not exceeded. KEEP")
          time.sleep(timeBetweenRuns)
          continue
      # SELL strategy 2
      if currentAggregatedPrice < tradeAggregatedPrice:
        if config["dry_run"] == "false":
          cooldownExpression = currentTime - lastTradeTimestamp < 60 * int(cooldownMinutesSellBuyPrice)
        else:
          if lastTradeTimestamp == 0:
            cooldownExpression = False
          else:
            cooldownExpression = config["currentDatapoint"] - lastTradeTimestamp < int(cooldownMinutesSellBuyPrice)
        if cooldownExpression:
          log.info("WAIT FOR COOLDOWN. No selling due to currentAggregatedPrice < tradeAggregatedPrice")
          if config["dry_run"] == "false":
            waitMinutes = int(((60 * int(cooldownMinutesBuy)) - (currentTime - lastTradeTimestamp)) / 60)
          else:
            waitMinutes = int(cooldownMinutesBuy) - (config["currentDatapoint"] - lastTradeTimestamp)
          log.info("Wait at least " + str(waitMinutes) + " more minutes.")
          time.sleep(timeBetweenRuns)
          continue
        # SELL
        sellHandler(config, currentDollars, cryptoQuantity, "currentAggregatedPrice < tradeAggregatedPrice")
        time.sleep(timeBetweenRuns)
        continue
    else:
      # We do not have crypto
      # Should we buy?
      if averagelookBackIntervalsDatapointsIndex < 0:
        log.info("Market going down. Keep waiting.")
        time.sleep(timeBetweenRuns)
        continue
      else:
        if averagelookBackIntervalsDatapointsIndex < lastlookBackIntervalsIndexTreshold:
          log.info("Too little increase. Not buying. Keep waiting.")
          time.sleep(timeBetweenRuns)
          continue
        else:
          if config["dry_run"] == "false":
            cooldownExpression = currentTime - lastTradeTimestamp < 60 * int(cooldownMinutesBuy)
          else:
            if lastTradeTimestamp == 0:
              cooldownExpression = False
            else:
              cooldownExpression = config["currentDatapoint"] - lastTradeTimestamp < int(cooldownMinutesBuy)
          if cooldownExpression:
            log.info("WAIT FOR COOLDOWN. No buying.")
            if config["dry_run"] == "false":
              waitMinutes = int(((60 * int(cooldownMinutesBuy)) - (currentTime - lastTradeTimestamp)) / 60)
            else:
              waitMinutes = int(cooldownMinutesBuy) - (config["currentDatapoint"] - lastTradeTimestamp)
            log.info("Wait at least " + str(waitMinutes) + " more minutes.")
            time.sleep(timeBetweenRuns)
            continue

          # Buy
          buyHandler(config, currentDollars, cryptoQuantity)
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