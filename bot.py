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
from databaseManager import getPriceHistory
from databaseManager import getLastTransactionStatus
from databaseManager import getMaximumPriceAfter
from databaseManager import insertTradeHistory


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
def sendMessage(log, config, message):
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

def constructHistory(log, sendMessage, config, databaseClient, binanceClient, coin, aggregatedBy, lookBackIntervals, timeBetweenRuns):
  # Get the price history from database
  realHistory = getPriceHistory(log, sendMessage, config, databaseClient, binanceClient, coin, aggregatedBy * lookBackIntervals)
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
def trade(log, sendMessage, config, databaseClient, binanceClient):
  # First we need to get the current state of liquidity
  # Extrapolate to many coins if the case
  coin = config["coins_to_scrape"].split("|")[0]

  # Get parameters from config
  # Sell if difference between maximum price for current trade - current price > peakIndexTreshold
  peakIndexTreshold = float(config["peak_index_treshold"])
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

  while True:
    # Update logger handler
    log = getLogger()
    currentTime = int(time.time())
    log.info("[Datapoint " + str(currentTime) + "] ######################################################")

    # Get last transaction status
    status = getLastTransactionStatus(log, sendMessage, config, databaseClient, binanceClient, coin)
    lastTradeTimestamp = int(status["timestamp"])
    doWeHaveCrypto = status["doWeHaveCrypto"]
    buyingPrice = status["buyingPrice"]
    currentDollars = status["currentDollars"]
    cryptoQuantity = status["cryptoQuantity"]
    gainOrLoss = status["gainOrLoss"]

    # If de we have crypto, we have to gate from history the maximum value of crypto after buying
    if doWeHaveCrypto == True:
      maximumPrice = getMaximumPriceAfter(log, sendMessage, config, databaseClient, binanceClient, lastTradeTimestamp)
    else:
      maximumPrice = 0

    # Get price history
    realHistory, aggregatedHistory = constructHistory(log, sendMessage, config, databaseClient, binanceClient, coin, aggregatedBy, lookBackIntervals, timeBetweenRuns)
    if len(realHistory) == 0:
      log.info("Too few data to aggregate")
      time.sleep(timeBetweenRuns)
      continue

    # Now the logic comes. To buy, to wait, to sell
    currentRealPrice = realHistory[-1]
    currentAggregatedPrice = aggregatedHistory[-1]
    log.info("currentRealPrice = " + str(currentRealPrice))
    log.info("currentAggregatedPrice = " + str(currentAggregatedPrice))
    # Print stats
    log.info("doWeHaveCrypto = " + str(doWeHaveCrypto))
    if doWeHaveCrypto == True:
      log.info("buyingPrice = " + str(buyingPrice))
      log.info("maximumPrice = " + str(maximumPrice))
    log.info("aggregatedHistory = " + str(aggregatedHistory))

    if doWeHaveCrypto == True:
      # Calculate peakIndex
      peakDiffPrice = currentAggregatedPrice - maximumPrice
      peakIndex = peakDiffPrice / maximumPrice
      log.info("peakDiffPrice = " + str(peakDiffPrice))
      log.info("peakIndex = " + str(peakIndex))

      if peakIndex >= 0:
        aquisitionDiffPrice = currentRealPrice - buyingPrice
        gain = aquisitionDiffPrice * cryptoQuantity
        log.info("GOOD JOB. WE ARE MAKING MONEY. Gainings for this trade: " + str(gain) + "$.")
        time.sleep(timeBetweenRuns)
        continue
      else:
        # peakIndex < 0
        if peakIndex < (-1) * peakIndexTreshold:
          if currentTime - lastTradeTimestamp < 60 * int(cooldownMinutesSellPeak):
            log.info("WAIT FOR COOLDOWN. No selling due to peakIndex < (-1) * peakIndexTreshold")
            waitMinutes = int(((60 * int(cooldownMinutesSellPeak)) - (currentTime - lastTradeTimestamp)) / 60)
            log.info("Wait at least " + str(waitMinutes) + " more minutes."
            time.sleep(timeBetweenRuns)
            continue
          # We exceeded treshold, get out
          # SELL
          message = "[SELL] We exceeded treshold, get out"
          message += "aggregatedHistory:\n"
          for price in aggregatedHistory:
            message += str(price) + "\n"
          message += "##########\n"
          message += "currentRealPrice = " + str(currentRealPrice) + "\n"
          message += "currentAggregatedPrice = " + str(currentAggregatedPrice) + "\n"
          message += "maximumPrice = " + str(maximumPrice) + "\n"
          message += "peakDiffPrice = " + str(peakDiffPrice) + "\n"
          message += "peakIndex = " + str(peakIndex) + "\n"
          message += "peakIndexTreshold = " + str(peakIndexTreshold) + "\n"
          log.info(message)
          sendMessage(log, config, message)
          tradePrice = sellCrypto(log, sendMessage, config, binanceClient)

          # Update variables
          currentDollars = getCurrencyBalance(log, sendMessage, config, binanceClient, 'USDT')
          cryptoQuantity = getCurrencyBalance(log, sendMessage, config, binanceClient, 'BTC')
          doWeHaveCrypto = False
          buyingPrice = 0
          madeFirstTrade = True
          # Insert in trade_history
          insertTradeHistory(log, sendMessage, config, databaseClient, binanceClient, currentTime, coin, "SELL", tradePrice, currentDollars, cryptoQuantity)
          time.sleep(timeBetweenRuns)

          continue
        else:
          # We did not exceeded treshold, maybe we will come back
          log.info("Treshold not exceeded. KEEP")
          time.sleep(timeBetweenRuns)
          continue

      if currentAggregatedPrice < buyingPrice:
        if currentTime - lastTradeTimestamp < 60 * int(cooldownMinutesSellBuyPrice):
          log.info("WAIT FOR COOLDOWN. No selling due to currentAggregatedPrice < buyingPrice")
          waitMinutes = int(((60 * int(cooldownMinutesSellBuyPrice)) - (currentTime - lastTradeTimestamp)) / 60)
          log.info("Wait at least " + str(waitMinutes) + " more minutes."
          time.sleep(timeBetweenRuns)
          continue
        # SELL
        message = "[SELL] currentAggregatedPrice < buyingPrice"
        message += "aggregatedHistory:\n"
        for price in aggregatedHistory:
          message += str(price) + "\n"
        message += "##########\n"
        message += "currentRealPrice = " + str(currentRealPrice) + "\n"
        message += "currentAggregatedPrice = " + str(currentAggregatedPrice) + "\n"
        message += "buyingPrice = " + str(buyingPrice) + "\n"
        log.info(message)
        sendMessage(log, config, message)
        tradePrice = sellCrypto(log, sendMessage, config, binanceClient)

        # Update variables
        currentDollars = getCurrencyBalance(log, sendMessage, config, binanceClient, 'USDT')
        cryptoQuantity = getCurrencyBalance(log, sendMessage, config, binanceClient, 'BTC')
        doWeHaveCrypto = False
        buyingPrice = 0
        madeFirstTrade = True
        # Insert in trade_history
        insertTradeHistory(log, sendMessage, config, databaseClient, binanceClient, currentTime, coin, "SELL", tradePrice, currentDollars, cryptoQuantity)

        time.sleep(timeBetweenRuns)
        continue
    else:
      # We do not have crypto
      # Should we buy?

      # Calculate change in the last lookBackIntervals datapoints
      averagelookBackIntervalsDataPoints = sum(aggregatedHistory[(-1) * lookBackIntervals:])/lookBackIntervals
      averagelookBackIntervalsDataPointsDiff = currentAggregatedPrice - averagelookBackIntervalsDataPoints
      averagelookBackIntervalsDatapointsIndex = averagelookBackIntervalsDataPointsDiff / averagelookBackIntervalsDataPoints
      log.info("averagelookBackIntervalsDataPointsDiff = " + str(averagelookBackIntervalsDataPointsDiff))
      log.info("averagelookBackIntervalsDatapointsIndex = " + str(averagelookBackIntervalsDatapointsIndex))
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
          if currentTime - lastTradeTimestamp < 60 * int(cooldownMinutesBuy):
            log.info("WAIT FOR COOLDOWN. No buying.")
            waitMinutes = int(((60 * int(cooldownMinutesBuy)) - (currentTime - lastTradeTimestamp)) / 60)
            log.info("Wait at least " + str(waitMinutes) + " more minutes."
            time.sleep(timeBetweenRuns)
            continue
          # BUY
          message = "[BUY]\n"
          message += "aggregatedHistory:\n"
          for price in aggregatedHistory:
            message += str(price) + "\n"
          message += "##########\n"
          message += "currentRealPrice = " + str(currentRealPrice) + "\n"
          message += "currentAggregatedPrice = " + str(currentAggregatedPrice) + "\n"
          message += "averagelookBackIntervalsDatapointsIndex = " + str('{:.10f}'.format(averagelookBackIntervalsDatapointsIndex)) + "\n"
          message += "lastlookBackIntervalsIndexTreshold = " + str('{:.10f}'.format(lastlookBackIntervalsIndexTreshold)) + "\n"
          log.info(message)
          sendMessage(log, config, message)
          tradePrice = buyCrypto(log, sendMessage, config, binanceClient)

          # Update variables
          cryptoQuantity = getCurrencyBalance(log, sendMessage, config, binanceClient, 'BTC')
          currentDollars = getCurrencyBalance(log, sendMessage, config, binanceClient, 'USDT')
          doWeHaveCrypto = True
          buyingPrice = tradePrice
          maximumPrice = tradePrice
          madeFirstTrade = True
          # Insert in trade_history
          insertTradeHistory(log, sendMessage, config, databaseClient, binanceClient, currentTime, coin, "BUY", tradePrice, currentDollars, cryptoQuantity)
          time.sleep(timeBetweenRuns)
          continue

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
      sendMessage(log, config, message)
      sys.exit(1)

    # Read config file
    configObj = configparser.ConfigParser()
    configObj.read(configFile)
    config = configObj._sections[configSection]

    sendMessage(log, config, "[INFO] Bot restarted")

    # Create the database if it not exists
    if os.path.isfile(config["database_file"]) is False:
      message = "[FATAL] Database not found. Exiting."
      log.info(message)
      sendMessage(log, config, message)
      sys.exit(2)

    # Connect to database
    try:
      databaseClient = sqlite3.connect(config["database_file"])
    except Exception as e:
      message = "[FATAL] Couldn't connect to the database. Investigate manually"
      log.info(message)
      log.info(e)
      sendMessage(log, config, message)
      sys.exit(2)

    # Create table if it not exists
    createTables(log, sendMessage, config, databaseClient)

    # Get Binance client
    binanceClient = Client(config["api_key"], config["api_secret_key"])

    # The function should never end, that scrape, and write in the database
    trade(log, sendMessage, config, databaseClient, binanceClient)

    # Commit and close
    try:
      databaseClient.commit()
      databaseClient.close()
      message = "[FATAL] Unexpected end of script. Database successfully commited and closed"
      log.info(message)
      sendMessage(log, config, message)
    except Exception as e:
      message = "[FATAL] Unexpected end of script. Database successfully commited and closed"
      log.info(message)
      log.info("Fatal Error: {}".format(e))
      tracebackError = traceback.format_exc()
      log.info(tracebackError)
      sendMessage(log, config, message)


  ##### END #####
  except KeyboardInterrupt:
    try:
      databaseClient.commit()
      databaseClient.close()
    except:
      message = "[FATAL] Could not commit and close DB connection"
      log.info(message)
      sendMessage(log, config, message)
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
      sendMessage(log, config, message)
    sendMessage(log, config, str(e) + "\n\n\n\n" + str(tracebackError))
    sys.exit(99)


##### BODY #####
if __name__ == "__main__":

  if len(sys.argv) != 1:
    log.info("Wrong number of parameters. Use: python bot.py")
    sys.exit(99)
  else:
    mainFunction()