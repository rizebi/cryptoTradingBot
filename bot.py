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

# Function that makes the trades
def trade(log, sendMessage, config, databaseClient, binanceClient):
  # First we need to get the current state of liquidity
  # Extrapolate to many coins if the case
  coin = config["coins_to_scrape"].split("|")[0]

  # Get parameters from config
  # Sell if difference between maximum price for current trade - current price > peakIndexTreshold
  # This does not respect cooldown! (if treshold is exceeded, will sell even on next datapoint)
  peakIndexTreshold = float(config["peak_index_treshold"])
  # Buy if difference between current price and lookBackIntervals datapoints ago is bigger than lastlookBackIntervalsIndexTreshold
  # Currently this seems not to matter
  lastlookBackIntervalsIndexTreshold = float(config["buy_lookback_intervals_index_treshold"])
  cooldownDatapoints = int(config["cooldown_datapoints"])
  # Mow many datapoints to aggregate (average)
  aggregatedBy = int(config["aggregated_by"])
  # The bot will buy if  the current price is above average for lookBackIntervals
  # These are big intervals. Aggregated ones
  lookBackIntervals = int(config["buy_lookback_intervals"])
  # Time between runs
  timeBetweenRuns = int(config["seconds_between_scrapes"])

  # Get last transaction status
  status = getLastTransactionStatus(log, sendMessage, config, databaseClient, binanceClient, coin)
  lastBuyingTimestamp = status["timestamp"]
  doWeHaveCrypto = status["doWeHaveCrypto"]
  buyingPrice = status["buyingPrice"]
  currentDollars = status["currentDollars"]
  cryptoQuantity = status["cryptoQuantity"]
  gainOrLoss = status["gainOrLoss"]

  # If de we have crypto, we have to gate from history the maximum value of crypto after buying
  if doWeHaveCrypto == True:
    maximumPrice = getMaximumPriceAfter(log, sendMessage, config, databaseClient, binanceClient, lastBuyingTimestamp)
  else:
    maximumPrice = 0

  # Initialisations
  currentDatapoint = 0
  actionDatapoint = 0
  # This helps to not wait for a cooldown when starting the script, but also no make more than one Trade in the first cycle
  madeFirstTrade = False

  while True:
    # Update logger handler
    log = getLogger()

    currentTime = int(time.time())
    log.info("[Datapoint " + str(currentTime) + "] ######################################################")
    # Get the price history from database
    dataPoints = getPriceHistory(log, sendMessage, config, databaseClient, binanceClient, coin, aggregatedBy * lookBackIntervals)
    if len(dataPoints) < aggregatedBy * lookBackIntervals:
      log.info("Too few data to aggregate")
      currentDatapoint += 1
      time.sleep(timeBetweenRuns)
      continue

    # len(dataPoints) == (lookBackIntervals * aggregatedBy)
    i = 0
    history = []
    while i < len(dataPoints):
      suma = 0
      j = 0
      while j < aggregatedBy:
        suma += dataPoints[i]
        i += 1
        j += 1
      history.append(suma/aggregatedBy)
    currentDatapoint += 1
    # Now the logic comes. To buy, to wait, to sell
    currentPrice = dataPoints[-1]
    currentAggregatedPrice = history[-1]
    log.info("currentAggregatedPrice = " + str(currentAggregatedPrice))
    log.info(history)

    # Calculate change in the last lookBackIntervals datapoints
    #log.info("pricelookBackIntervalsDatapoints = " + str(history[-10]))
    #averagelookBackIntervalsDataPointsDiff = currentAggregatedPrice - history[(-1) * lookBackIntervals]
    averagelookBackIntervalsDataPoints = sum(history[(-1) * lookBackIntervals:])/lookBackIntervals
    averagelookBackIntervalsDataPointsDiff = currentAggregatedPrice - averagelookBackIntervalsDataPoints
    #log.info("averagelookBackIntervalsDataPointsDiff = " + str(averagelookBackIntervalsDataPointsDiff))
    averagelookBackIntervalsDatapointsIndex = averagelookBackIntervalsDataPointsDiff / averagelookBackIntervalsDataPoints
    #log.info("averagelookBackIntervalsDatapointsIndex = " + str(averagelookBackIntervalsDatapointsIndex))

    # Print stats
    log.info("doWeHaveCrypto = " + str(doWeHaveCrypto))
    if doWeHaveCrypto == True:
      log.info("buyingPrice = " + str(buyingPrice))
      log.info("maximumPrice = " + str(maximumPrice))

    if doWeHaveCrypto == True:
      if currentAggregatedPrice > maximumPrice:
        maximumPrice = currentAggregatedPrice
      # Calculate peakIndex
      peakDiffPrice = currentAggregatedPrice - maximumPrice
      aquisitionDiffPrice = currentAggregatedPrice - buyingPrice
      peakIndex = peakDiffPrice / maximumPrice

      if peakIndex >= 0:
        gain = aquisitionDiffPrice * cryptoQuantity
        log.info("GOOD JOB. WE ARE MAKING MONEY. Gainings for this trade: " + str(gain) + "$.")
        time.sleep(timeBetweenRuns)
        continue
      else:
        # peakIndex < 0
        if peakIndex < (-1) * peakIndexTreshold:
          # We exceeded treshold, get out
          # SELL
          message = "[SELL at aggregated " + str(currentAggregatedPrice) + "] We exceeded treshold, get out"
          message += "aggregatedHistory:\n"
          for price in history:
            message += str(price) + "\n"
          message += "peakIndex = " + str(peakIndex) + "\n"
          message += "peakIndexTreshold = " + str(peakIndexTreshold) + "\n"
          log.info(message)
          sendMessage(log, config, message)
          tradePrice = sellCrypto(log, sendMessage, config, binanceClient)

          # Update variables
          currentDollars = getCurrencyBalance(log, sendMessage, config, binanceClient, 'USDT')
          cryptoQuantity = getCurrencyBalance(log, sendMessage, config, binanceClient, 'BTC')
          actionDatapoint = currentDatapoint
          doWeHaveCrypto = False
          buyingPrice = 0
          madeFirstTrade = True
          # Insert in trade_history
          insertTradeHistory(log, sendMessage, config, databaseClient, binanceClient, currentTime, coin, "SELL", tradePrice, currentDollars, 0)
          time.sleep(timeBetweenRuns)

          continue
        else:
          # We did not exceeded treshold, maybe we will come back
          log.info("Treshold not exceeded. KEEP")
          time.sleep(timeBetweenRuns)
          continue

      if currentAggregatedPrice < buyingPrice:
        # No need to wait for cooldown if script was just restarted
        if ((madeFirstTrade == True) and (currentDatapoint <= cooldownDatapoints * aggregatedBy)) or ((currentDatapoint >= cooldownDatapoints * aggregatedBy) and (currentDatapoint - actionDatapoint < cooldownDatapoints * aggregatedBy)):
          log.info("WAIT FOR COOLDOWN. No selling.")
          time.sleep(timeBetweenRuns)
          continue
        # SELL
        message = "[SELL at aggregated " + str(currentAggregatedPrice) + "] currentAggregatedPrice < BuyingPrice"
        message += "aggregatedHistory:\n"
        for price in history:
          message += str(price) + "\n"
        message += "buyingPrice = " + str(buyingPrice) + "\n"
        log.info(message)
        sendMessage(log, config, message)
        tradePrice = sellCrypto(log, sendMessage, config, binanceClient)

        # Update variables
        currentDollars = getCurrencyBalance(log, sendMessage, config, binanceClient, 'USDT')
        cryptoQuantity = getCurrencyBalance(log, sendMessage, config, binanceClient, 'BTC')
        actionDatapoint = currentDatapoint
        doWeHaveCrypto = False
        buyingPrice = 0
        madeFirstTrade = True
        # Insert in trade_history
        insertTradeHistory(log, sendMessage, config, databaseClient, binanceClient, currentTime, coin, "SELL", tradePrice, currentDollars, 0)

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
          # No need to wait for cooldown if script was just restarted
          if ((madeFirstTrade == True) and (currentDatapoint <= cooldownDatapoints * aggregatedBy)) or ((currentDatapoint >= cooldownDatapoints * aggregatedBy) and (currentDatapoint - actionDatapoint < cooldownDatapoints * aggregatedBy)):
            log.info("WAIT FOR COOLDOWN. No buying.")
            time.sleep(timeBetweenRuns)
            continue
          # BUY
          message = "[BUY at aggregated " + str(currentAggregatedPrice) + "]\n"
          message += "aggregatedHistory:\n"
          for price in history:
            message += str(price) + "\n"
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
          actionDatapoint = currentDatapoint
          maximumPrice = tradePrice
          madeFirstTrade = True
          # Insert in trade_history
          insertTradeHistory(log, sendMessage, config, databaseClient, binanceClient, currentTime, coin, "BUY", tradePrice, 0, cryptoQuantity)
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