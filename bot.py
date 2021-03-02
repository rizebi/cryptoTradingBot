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

##### Constants #####
currentDir = os.getcwd()
configFile = "./configuration.cfg"
configSection = "configuration"

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

# Function that sends a message to Telegram
def sendMessage(log, message):
  try:
    payload = {
        'chat_id': config["bot_chat_id"],
        'text': message,
        'parse_mode': 'HTML'
    }
    # TODO uncomment
    #return requests.post("https://api.telegram.org/bot{token}/sendMessage".format(token=config["bot_token"]), data=payload).content
  except Exception as e:
    log.info("Error when sending Telegram message: {}".format(e))
    tracebackError = traceback.format_exc()
    log.info(tracebackError)

def createTables(log):
  log.info("Check if table <trade_history> exits")
  databaseCursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
  tables = databaseCursor.fetchall()
  if ("trade_history",) in tables:
    log.info("Table <trade_history> already exists. Continue.")
    return
  log.info("Table <trade_history> does not exists. Will create it now.")
  databaseConnection.execute('''CREATE TABLE trade_history
               (timestamp text, coin text, action text, currentPrice real, currentDollars real, cryptoQuantity real, gainOrLoss real)''')
  databaseConnection.commit()
  log.info("Table <trade_history> successfully created.")

def getPriceHistory(log, coin, howMany):
  databaseCursor.execute("SELECT price FROM price_history WHERE coin='" + coin + "' order by timestamp desc limit " + str(howMany))
  historyObj = databaseCursor.fetchall()
  historyObj.reverse()
  history = []
  for price in historyObj:
    history.append(price[0])
  return history

# Function that reads from DB the last transaction
def getLastTransactionStatus(log, coin):
  databaseCursor.execute("SELECT * FROM trade_history WHERE coin='" + coin + "' order by timestamp desc limit " + str(1))
  lastTransaction = databaseCursor.fetchall()
  if len(lastTransaction) == 0:
    log.info("No history on the database. Will go with the default option: no Crypto")
    return {"timestamp": 0, "doWeHaveCrypto": False, "currentPrice": 0, "currentDollars": 0, "cryptoQuantity": 0, "gainOrLoss": 0}
  else:
    if lastTransaction[2] == "BUY":
      doWeHaveCrypto = True
    else:
      doWeHaveCrypto = False
      return {"timestamp": lastTransaction[0], "doWeHaveCrypto": doWeHaveCrypto, "currentPrice": lastTransaction[3], "currentDollars": lastTransaction[4], "cryptoQuantity": lastTransaction[5], "gainOrLoss": lastTransaction[6]}

# If de we have crypto, we have to gate from history the maximum value of crypto after buying
def getMaximumPriceAfter(log, lastBuyingTimestamp):
  databaseCursor.execute("SELECT * max(price) price_history WHERE coin='" + coin + "' AND timestamp > " + lastBuyingTimestamp)
  maximumPrice = databaseCursor.fetchall()
  return maximumPrice[0]

def getCurrentDollars(log):
  pass
  # TODO implement

def getCryptoQuantity(log):
  pass
  # TODO implement

def buyCrypto(log):
  pass
  # TODO implement

def sellCrypto(log):
  pass
  # TODO implement

def insertTradeHistory(log, currentTime, coin, action, currentPrice, currentDollars, cryptoQuantity):
  pass
  # TODO implement

# Function that makes the trades
def trade(log):
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
  status = getLastTransactionStatus(log, coin)
  lastBuyingTimestamp = status["timestamp"]
  doWeHaveCrypto = status["doWeHaveCrypto"]
  currentPrice = status["currentPrice"]
  currentDollars = status["currentDollars"]
  cryptoQuantity = status["cryptoQuantity"]
  gainOrLoss = status["gainOrLoss"]

  # If de we have crypto, we have to gate from history the maximum value of crypto after buying
  if doWeHaveCrypto == True:
    maximumPrice = getMaximumPriceAfter(log, lastBuyingTimestamp)
  else:
    maximumPrice = 0

  # Initialisations
  currentDatapoint = 0
  history = []

  while True:
    currentTime = int(time.time())
    log.info("[Datapoint " + str(currentTime) + "] ######################################################")
    # Get the price history from database
    dataPoints = getPriceHistory(log, coin, aggregatedBy * lookBackIntervals)
    if len(dataPoints) < aggregatedBy * lookBackIntervals:
      log.info("Too few data to aggregate")
      currentDatapoint += 1
      time.sleep(timeBetweenRuns)
      continue

    i = currentDatapoint - (lookBackIntervals * aggregatedBy) + 1
    while i <= currentDatapoint:
      suma = 0
      j = 0
      while j < aggregatedBy:
        suma += dataPoints[i]
        i += 1
        j += 1
      history.append(suma/aggregatedBy)
    currentDatapoint += 1
    # Now the logic comes. To buy, to wait, to sell
    currentPrice = history[-1]
    log.info("currentPrice = " + str(currentPrice))

    # Calculate change in the last lookBackIntervals datapoints
    #log.info("pricelookBackIntervalsDatapoints = " + str(history[-10]))
    #averagelookBackIntervalsDataPointsDiff = currentPrice - history[(-1) * lookBackIntervals]
    averagelookBackIntervalsDataPoints = sum(history[(-1) * lookBackIntervals:])/lookBackIntervals
    averagelookBackIntervalsDataPointsDiff = currentPrice - averagelookBackIntervalsDataPoints
    #log.info("averagelookBackIntervalsDataPointsDiff = " + str(averagelookBackIntervalsDataPointsDiff))
    averagelookBackIntervalsDatapointsIndex = averagelookBackIntervalsDataPointsDiff / averagelookBackIntervalsDataPoints
    #log.info("averagelookBackIntervalsDatapointsIndex = " + str(averagelookBackIntervalsDatapointsIndex))

    # Print stats
    log.info("doWeHaveCrypto = " + str(doWeHaveCrypto))
    if doWeHaveCrypto == True:
      log.info("buyingPrice = " + str(buyingPrice))
      log.info("maximumPrice = " + str(maximumPrice))

    if doWeHaveCrypto == True:
      if currentPrice > maximumPrice:
        maximumPrice = currentPrice
      # Calculate peakIndex
      peakDiffPrice = currentPrice - maximumPrice
      aquisitionDiffPrice = currentPrice - buyingPrice
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
          message = "[SELL at " + str(currentPrice) + "] We exceeded treshold, get out"
          log.info(message)
          sendMessage(message)
          sellCrypto(log)

          # Update variables
          currentDollars = getCurrentDollars(log)
          actionDatapoint = currentDatapoint
          doWeHaveCrypto = False
          cryptoQuantity = 0
          buyingPrice = 0
          time.sleep(timeBetweenRuns)

          # Insert in trade_history
          insertTradeHistory(log, currentTime, coin, "SELL", currentPrice, currentDollars, 0)

          continue
        else:
          # We did not exceeded treshold, maybe we will come back
          log.info("Treshold not exceeded. KEEP")
          time.sleep(timeBetweenRuns)
          continue

      if currentPrice < buyingPrice:
        if currentDatapoint - actionDatapoint < cooldownDatapoints * aggregatedBy:
          log.info("WAIT FOR COOLDOWN. No selling.")
          time.sleep(timeBetweenRuns)
          continue
        # SELL
        message = "[SELL at " + str(currentPrice) + "] CurrentPrice < BuyingPrice"
        log.info(message)
        sendMessage(message)
        sellCrypto(log)

        # Update variables
        currentDollars = getCurrentDollars(log)
        actionDatapoint = currentDatapoint
        doWeHaveCrypto = False
        cryptoQuantity = 0
        buyingPrice = 0
        # Insert in trade_history
        insertTradeHistory(log, currentTime, coin, "SELL", currentPrice, currentDollars, 0)

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
          if currentDatapoint - actionDatapoint < cooldownDatapoints * aggregatedBy:
            log.info("WAIT FOR COOLDOWN. No buying.")
            time.sleep(timeBetweenRuns)
            continue
          # BUY
          message = "[BUY at " + str(currentPrice) + "]"
          log.info(message)
          sendMessage(message)
          buyCrypto(log)

          # Update variables
          cryptoQuantity = getCryptoQuantity(log)
          doWeHaveCrypto = True
          buyingPrice = currentPrice
          actionDatapoint = currentDatapoint
          maximumPrice = currentPrice
          currentDollars = 0

          # Insert in trade_history
          insertTradeHistory(log, currentTime, coin, "BUY", currentPrice, 0, cryptoQuantity)

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
      sendMessage(log, message)
      sys.exit(1)

    # Read config file
    configObj = configparser.ConfigParser()
    configObj.read(configFile)
    global config
    config = configObj._sections[configSection]

    # Create the database if it not exists
    if os.path.isfile(config["database_file"]) is False:
      message = "[FATAL] Database not found. Exiting."
      log.info(message)
      sendMessage(log, message)
      sys.exit(2)

    # Connect to database
    try:
      global databaseConnection
      global databaseCursor
      databaseConnection = sqlite3.connect(config["database_file"])
      databaseCursor = databaseConnection.cursor()
    except Exception as e:
      message = "[FATAL] Couldn't connect to the database. Investigate manually"
      log.info(message)
      log.info(e)
      sendMessage(log, message)
      sys.exit(2)

    # Create table if it not exists
    createTables(log)

    # The function should never end, that scrape, and write in the database
    trade(log)

    # Commit and close
    try:
      databaseConnection.commit()
      databaseConnection.close()
      message = "[FATAL] Unexpected end of script. Database successfully commited and closed"
      log.info(message)
      sendMessage(log, message)
    except Exception as e:
      message = "[FATAL] Unexpected end of script. Database successfully commited and closed"
      log.info(message)
      log.info("Fatal Error: {}".format(e))
      tracebackError = traceback.format_exc()
      log.info(tracebackError)
      sendMessage(log, message)


  ##### END #####
  except KeyboardInterrupt:
    try:
      databaseConnection.commit()
      databaseConnection.close()
    except:
      message = "[FATAL] Could not commit and close DB connection"
      log.info(message)
      sendMessage(log, message)
    log.info("DB commited and closed. Gracefully quiting")
    sys.exit(0)
  except Exception as e:
    log.info("Fatal Error: {}".format(e))
    tracebackError = traceback.format_exc()
    log.info(tracebackError)
    try:
      databaseConnection.commit()
      databaseConnection.close()
    except:
      message = "[FATAL] Could not commit and close DB connection."
      log.info(message)
      sendMessage(log, message)
    sendMessage(log, str(e) + "\n\n\n\n" + str(tracebackError))
    sys.exit(99)


##### BODY #####
if __name__ == "__main__":

  if len(sys.argv) != 1:
    log.info("Wrong number of parameters. Use: python bot.py")
    sys.exit(99)
  else:
    mainFunction()