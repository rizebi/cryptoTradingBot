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
        'text': "[bot]" + message,
        'parse_mode': 'HTML'
    }
    return requests.post("https://api.telegram.org/bot{token}/sendMessage".format(token=config["bot_token"]), data=payload).content
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
  # First, check the latest timestamp from database. If this is old, will return []
  databaseCursor.execute("SELECT max(timestamp) FROM price_history")
  dataPointsObj = databaseCursor.fetchall()
  currentTime = time.time()
  if currentTime - float(dataPointsObj[0][0]) > 300:
    message = "[ERROR] Too old price history in database. Maybe scraper is down. Skipping the bot run for this time."
    log.info(message)
    sendMessage(log, message)
    return []

  databaseCursor.execute("SELECT price FROM price_history WHERE coin='" + coin + "' order by timestamp desc limit " + str(howMany))
  dataPointsObj = databaseCursor.fetchall()
  dataPointsObj.reverse()
  dataPoints = []
  for price in dataPointsObj:
    dataPoints.append(price[0])
  return dataPoints

# Function that reads from DB the last transaction
def getLastTransactionStatus(log, coin):
  # Get current balance
  currentDollars = getCurrencyBalance(log, "USDT")
  cryptoQuantity = getCurrencyBalance(log, "BTC")

  databaseCursor.execute("SELECT * FROM trade_history WHERE coin='" + coin + "' order by timestamp desc limit " + str(1))
  lastTransaction = databaseCursor.fetchall()
  if len(lastTransaction) == 0:
    log.info("No history on the database. Will go with the default option: no Crypto")
    return {"timestamp": 0, "doWeHaveCrypto": False, "buyingPrice": 0, "currentDollars": 0, "cryptoQuantity": 0, "gainOrLoss": 0}
  else:
    if lastTransaction[0][2] == "BUY":
      doWeHaveCrypto = True
      return {"timestamp": lastTransaction[0][0], "doWeHaveCrypto": doWeHaveCrypto, "buyingPrice": lastTransaction[0][3], "currentDollars": currentDollars, "cryptoQuantity": cryptoQuantity, "gainOrLoss": lastTransaction[0][6]}
    else:
      doWeHaveCrypto = False
      return {"timestamp": lastTransaction[0][0], "doWeHaveCrypto": doWeHaveCrypto, "buyingPrice": 0, "currentDollars": currentDollars, "cryptoQuantity": cryptoQuantity, "gainOrLoss": lastTransaction[0][6]}

# If de we have crypto, we have to gate from history the maximum value of crypto after buying
def getMaximumPriceAfter(log, lastBuyingTimestamp):
  coin = "BTCUSDT"
  databaseCursor.execute("SELECT max(price) FROM price_history WHERE coin='" + coin + "' AND timestamp > " + lastBuyingTimestamp)
  maximumPrice = databaseCursor.fetchall()
  return maximumPrice[0][0]

def getCurrencyBalance(log, currency):
  i = 0
  while i <= 5:
    i += 1
    try:
      if i > 1:
        log.info("Retry number " + str(i) + " to get account balance.")
      balances = client.get_account()[u'balances']
      break
    except BinanceAPIException as e:
      message = "[ERROR API] Couldn't get balances from Binance: " + str(e)
      log.info(message)
      log.info(e)
    except Exception as e:
      message = "[ERROR] Couldn't get balances from Binance: " + str(e)
      log.info(message)
      log.info(e)
    time.sleep(5)
  if i == 11:
    message = "[ERROR] Couldn't get balances from Binance after 10 retries"
    log.info(message)
    sendMessage(log, message)
    return (-1)

  for currency_balance in balances:
      if currency_balance[u'asset'] == currency:
          return float(currency_balance[u'free'])
  return None

def getCurrentCoinPrice(log, coin):
  i = 0
  while i <= 10:
    i += 1
    if i > 1:
      log.info("Retry number " + str(i) + " for coin: '" + coin + "'")
    try:
      return float(client.get_symbol_ticker(symbol=coin)["price"])
    except BinanceAPIException as e:
      message = "[ERROR API] When getting current price: " + str(e)
      log.info(message)
      sendMessage(log, message)
    except Exception as e:
      message = "[ERROR] When getting current price: " + str(e)
      log.info(message)
      sendMessage(log, message)
    time.sleep(1)
  if i == 11:
    message = "[ERROR] Couldn't get current price from Binance after 10 retries"
    log.info(message)
    sendMessage(log, message)
  return None

def wait_for_order(log, symbol, order_id):
  log.info("Wait for order")
  i = 0
  while True:
    i += 1
    try:
      order_status = client.get_order(symbol="BTCUSDT", orderId=order_id)
      break
    except BinanceAPIException as e:
      message = "[ERROR API] When waiting for order: " + str(e)
      log.info(message)
      sendMessage(log, message)
      time.sleep(1)
    except Exception as e:
      message = "[ERROR] When waiting for order: " + str(e)
      log.info(message)
      sendMessage(log, message)
      time.sleep(1)

    if i == 10 or i == 100 or i == 500:
      message = "[ERROR] Couldn't wait for order after " + str(i) + " retries"
      log.info(message)
      sendMessage(log, message)

  log.info(order_status)

  i = 0
  while order_status[u'status'] != 'FILLED':
    i += 1
    try:
      order_status = self.BinanceClient.get_order(
          symbol="BTCUSDT", orderId=order_id)
    except BinanceAPIException as e:
      message = "[ERROR API] when querying if status is FILLED: " + str(e)
      log.info(message)
      sendMessage(log, message)
      time.sleep(1)
    except Exception as e:
      message = "[ERROR] when querying if status is FILLED: " + str(e)
      log.info(message)
      sendMessage(log, message)
      time.sleep(1)

    if i == 10 or i == 100 or i == 500:
      message = "[ERROR] Couldn't query if status is FILLED " + str(i) + " retries"
      log.info(message)
      sendMessage(log, message)

  return order_status

def buyCrypto(log):
  currentDollars = getCurrencyBalance(log, 'USDT')

  order = None
  i = 0
  while order is None:
    i += 1
    try:
      currentPrice = getCurrentCoinPrice(log, 'BTCUSDT')
      quantityWanted = currentDollars / currentPrice
      quantityWanted = quantityWanted - 0.01 * quantityWanted
      quantityWanted = float(str(quantityWanted).split(".")[0] + "." + str(quantityWanted).split(".")[1][:6])
      log.info("quantity = " + str(quantityWanted))
      order = client.order_market_buy(
       symbol="BTCUSDT", quantity=(quantityWanted)
      )
    except BinanceAPIException as e:
      message = "[ERROR API] when placing BUY crypto order: " + str(e)
      log.info(message)
      sendMessage(log, message)
      time.sleep(1)
    except Exception as e:
      message = "[ERROR] when placing BUY crypto order: " + str(e)
      log.info(message)
      sendMessage(log, message)
      time.sleep(1)

    if i == 10 or i == 100 or i == 500:
      message = "[ERROR] Couldn't place BUY crypto order " + str(i) + " retries"
      log.info(message)
      sendMessage(log, message)

  log.info("BUY crypto order placed:")
  log.info(order)

  # Binance server can take some time to save the order
  log.info("Waiting for Binance")

  stat = wait_for_order(log, "BTCUSDT", order[u'orderId'])

  oldDollars = currentDollars
  newDollars = getCurrencyBalance(log, 'USDT')
  while newDollars >= oldDollars:
      newDollars = getCurrencyBalance(log, 'USDT')
      time.sleep(5)

  newCrypto = getCurrencyBalance(log, 'BTC')

  message = "BUY crypto successful\n"
  message += "############## BUY CRYPTO TRADE STATS #############\n"
  message += "currentPrice = " + str(currentPrice) + "\n"
  message += "oldDollars = " + str(oldDollars) + "\n"
  message += "newCrypto = " + str(newCrypto) + "\n"
  message += "####################################################"
  log.info(message)
  sendMessage(log, message)

def sellCrypto(log):
  currentCrypto = getCurrencyBalance(log, 'BTC')
  log.info("currentCrypto = " + str(currentCrypto))
  log.info("Try to launch a SELL Crypto order")

  order = None
  i = 0
  while order is None:
    i += 1
    try:
      currentPrice = getCurrentCoinPrice(log, 'BTCUSDT')
      quantityWanted = float(str(currentCrypto).split(".")[0] + "." + str(currentCrypto).split(".")[1][:6])
      log.info("quantity = " + str(quantityWanted))
      order = client.order_market_sell(
        symbol="BTCUSDT", quantity=(quantityWanted)
      )
    except BinanceAPIException as e:
      message = "[ERROR API] when placing SELL crypto order: " + str(e)
      log.info(message)
      sendMessage(log, message)
      time.sleep(1)
    except Exception as e:
      message = "[ERROR] when placing SELL crypto order: " + str(e)
      log.info(message)
      sendMessage(log, message)
      time.sleep(1)

    if i == 10 or i == 100 or i == 500:
      message = "[ERROR] Couldn't place SELL crypto order " + str(i) + " retries"
      log.info(message)
      sendMessage(log, message)

  log.info("SELL crypto order placed:")
  log.info(order)

  # Binance server can take some time to save the order
  log.info("Waiting for Binance")

  stat = wait_for_order(log, "BTCUSD", order[u'orderId'])

  oldCrypto = currentCrypto
  newCrypto = getCurrencyBalance(log, 'BTC')
  while newCrypto >= oldCrypto:
      newCrypto = getCurrencyBalance(log, 'BTC')
      time.sleep(5)

  log.info("SOLD crypto successful")

  newDollars = getCurrencyBalance(log, 'USDT')

  message = "SELL crypto successful\n"
  message += "############## SELL CRYPTO TRADE STATS #############\n"
  message += "currentPrice = " + str(currentPrice) + "\n"
  message += "newDollars = " + str(newDollars) + "\n"
  message += "oldCrypto = " + str(oldCrypto) + "\n"
  message += "####################################################"
  log.info(message)
  sendMessage(log, message)

def insertTradeHistory(log, currentTime, coin, action, currentPrice, currentDollars, cryptoQuantity):
  # Here we have to calculate the gainOrLoss
  # For now, enter 0
  # TODO
  gainOrLoss = 0
  try:
    query = "INSERT INTO trade_history VALUES (" + str(currentTime) + ",'" + coin + "','" + action + "'," + str(currentPrice) + "," + str(currentDollars) + "," + str(cryptoQuantity) + "," + str(gainOrLoss) + ")"
    log.info(query)
    databaseConnection.execute(query)
    databaseConnection.commit()
  except Exception as e:
    message = "[ERROR] When saving scraping in the database: " + str(e)
    log.info(message)
    sendMessage(log, message)

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
  buyingPrice = status["buyingPrice"]
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
  actionDatapoint = 0
  history = []
  # This helps to not wait for a cooldown when starting the script, but also no make more than one Trade in the first cycle
  madeFirstTrade = False

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

    # len(dataPoints) == (lookBackIntervals * aggregatedBy)
    i = 0
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
          message = "peakIndex = " + str(peakIndex) + "\n"
          message += "peakIndexTreshold = " + str(peakIndexTreshold) + "\n"
          message = "[SELL at " + str(currentPrice) + "] We exceeded treshold, get out"
          log.info(message)
          sendMessage(log, message)
          sellCrypto(log)

          # Update variables
          currentDollars = getCurrencyBalance(log, 'USDT')
          actionDatapoint = currentDatapoint
          doWeHaveCrypto = False
          cryptoQuantity = 0
          buyingPrice = 0
          madeFirstTrade = True
          # Insert in trade_history
          insertTradeHistory(log, currentTime, coin, "SELL", currentPrice, currentDollars, 0)
          time.sleep(timeBetweenRuns)

          continue
        else:
          # We did not exceeded treshold, maybe we will come back
          log.info("Treshold not exceeded. KEEP")
          time.sleep(timeBetweenRuns)
          continue

      if currentPrice < buyingPrice:
        # No need to wait for cooldown if script was just restarted
        if ((madeFirstTrade == True) and (currentDatapoint <= cooldownDatapoints * aggregatedBy)) or ((currentDatapoint >= cooldownDatapoints * aggregatedBy) and (currentDatapoint - actionDatapoint < cooldownDatapoints * aggregatedBy)):
          log.info("WAIT FOR COOLDOWN. No selling.")
          time.sleep(timeBetweenRuns)
          continue
        # SELL
        message = "currentPrice = " + str(currentPrice) + "\n"
        message += "buyingPrice = " + str(buyingPrice) + "\n"
        message += "[SELL at " + str(currentPrice) + "] CurrentPrice < BuyingPrice"
        log.info(message)
        sendMessage(log, message)
        sellCrypto(log)

        # Update variables
        currentDollars = getCurrencyBalance(log, 'USDT')
        actionDatapoint = currentDatapoint
        doWeHaveCrypto = False
        cryptoQuantity = 0
        buyingPrice = 0
        madeFirstTrade = True
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
          # No need to wait for cooldown if script was just restarted
          if ((madeFirstTrade == True) and (currentDatapoint <= cooldownDatapoints * aggregatedBy)) or ((currentDatapoint >= cooldownDatapoints * aggregatedBy) and (currentDatapoint - actionDatapoint < cooldownDatapoints * aggregatedBy)):
            log.info("WAIT FOR COOLDOWN. No buying.")
            time.sleep(timeBetweenRuns)
            continue
          # BUY
          message = "averagelookBackIntervalsDatapointsIndex = " + str(averagelookBackIntervalsDatapointsIndex) + "\n"
          message += "lastlookBackIntervalsIndexTreshold = " + str(lastlookBackIntervalsIndexTreshold) + "\n"
          message += "[BUY at " + str(currentPrice) + "]"
          log.info(message)
          sendMessage(log, message)
          buyCrypto(log)

          # Update variables
          cryptoQuantity = getCurrencyBalance(log, 'BTC')
          doWeHaveCrypto = True
          buyingPrice = currentPrice
          actionDatapoint = currentDatapoint
          maximumPrice = currentPrice
          currentDollars = 0
          madeFirstTrade = True
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

    sendMessage(log, "[INFO] Bot restarted")

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

    # Get Binance client
    global client
    client = Client(config["api_key"], config["api_secret_key"])

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