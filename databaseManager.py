import time
import datetime
from binanceManager import getCurrencyBalance

def createTables(log, sendMessage, config, databaseClient):
  log.info("Check if table <trade_history> exits")
  databaseCursor = databaseClient.cursor()
  databaseCursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
  tables = databaseCursor.fetchall()
  if ("trade_history",) in tables:
    log.info("Table <trade_history> already exists. Continue.")
    return
  log.info("Table <trade_history> does not exists. Will create it now.")
  databaseClient.execute('''CREATE TABLE trade_history
               (timestamp text, date text, coin text, action text, tradePrice real, currentDollars real, cryptoQuantity real, gainOrLoss real)''')
  databaseClient.commit()
  log.info("Table <trade_history> successfully created.")

# Funcion used only when back_testing
def emptyTradeHistoryDatabase(log, sendMessage, config, databaseClient, binanceClient):
  log.info("EMPTYING trade_history table.")
  databaseClient.execute('''DELETE FROM trade_history''')
  databaseClient.commit()

def getPriceHistoryFromDatabase(log, sendMessage, config, databaseClient, binanceClient, coin, howMany):
  # First, check the latest timestamp from database. If this is old, will return []
  databaseCursor = databaseClient.cursor()
  databaseCursor.execute("SELECT max(timestamp) FROM price_history")
  dataPointsObj = databaseCursor.fetchall()
  currentTime = time.time()
  if currentTime - float(dataPointsObj[0][0]) > 300:
    message = "[ERROR] Too old price history in database. Maybe scraper is down. Skipping the bot run for this time."
    log.info(message)
    sendMessage(log, config, message)
    return []

  databaseCursor.execute("SELECT price FROM price_history WHERE coin='" + coin + "' order by timestamp desc limit " + str(howMany))
  dataPointsObj = databaseCursor.fetchall()
  dataPointsObj.reverse()
  dataPoints = []
  for price in dataPointsObj:
    dataPoints.append(price[0])
  return dataPoints


def getPriceHistoryFromFile(log, sendMessage, config, databaseClient, binanceClient, coin, howMany):
  aggregatedBy = int(config["aggregated_by"])
  lookBackIntervals = int(config["buy_lookback_intervals"])
  currentDatapoint = config["currentDatapoint"]

  dataPoints = config["dataPoints"]

  if currentDatapoint < aggregatedBy * lookBackIntervals:
    return dataPoints[0:currentDatapoint]
  return dataPoints[currentDatapoint - aggregatedBy * lookBackIntervals: currentDatapoint]

# Function that reads from DB the last transaction
def getLastTransactionStatus(log, sendMessage, config, databaseClient, binanceClient, coin):
  # Get current balance. Do I really need to to this? Isn't it enough to take the data from last transaction?
  #currentDollars = getCurrencyBalance(log, sendMessage, config, binanceClient, "USDT")
  #cryptoQuantity = getCurrencyBalance(log, sendMessage, config, binanceClient, "BTC")
  databaseCursor = databaseClient.cursor()
  databaseCursor.execute("SELECT * FROM trade_history WHERE coin='" + coin + "' order by timestamp desc limit " + str(1))
  lastTransaction = databaseCursor.fetchall()
  if len(lastTransaction) == 0:
    log.info("No history on the database. Will go with the default option: no Crypto")
    if config["dry_run"] == "false":
      currentDollars = 0
    else:
      currentDollars = 100 #TODO add in config
    return {"timestamp": 0, "doWeHaveCrypto": False, "buyingPrice": 0, "currentDollars": currentDollars, "cryptoQuantity": 0, "gainOrLoss": 0, "maximumPrice": 0}
  else:
    if lastTransaction[0][3] == "BUY":
      doWeHaveCrypto = True
      # If de we have crypto, we have to gate from history the maximum value of crypto after buying
      if config["dry_run"] == "false":
        maximumPrice = getMaximumPriceAfterLastTransactionFromDatabase(log, sendMessage, config, databaseClient, binanceClient, int(lastTransaction[0][0]))
      else:
        maximumPrice = getMaximumPriceAfterLastTransactionFromFile(log, sendMessage, config, databaseClient, binanceClient, int(lastTransaction[0][0]))
    else:
      doWeHaveCrypto = False
      maximumPrice = 0
    return {"timestamp": int(lastTransaction[0][0]), "doWeHaveCrypto": doWeHaveCrypto, "buyingPrice": float(lastTransaction[0][4]), "currentDollars": float(lastTransaction[0][5]), "cryptoQuantity": float(lastTransaction[0][6]), "gainOrLoss": float(lastTransaction[0][7]), "maximumPrice": maximumPrice}

# If de we have crypto, we have to gate from history the maximum value of crypto after buying
def getMaximumPriceAfterLastTransactionFromDatabase(log, sendMessage, config, databaseClient, binanceClient, lastBuyingTimestamp):
  coin = "BTCUSDT"
  databaseCursor = databaseClient.cursor()
  databaseCursor.execute("SELECT max(price) FROM price_history WHERE coin='" + coin + "' AND timestamp > " + str(lastBuyingTimestamp))
  maximumPrice = databaseCursor.fetchall()
  return maximumPrice[0][0]

# Used from backtesting
def getMaximumPriceAfterLastTransactionFromFile(log, sendMessage, config, databaseClient, binanceClient, lastBuyingTimestamp):

  currentDatapoint = config["currentDatapoint"]
  i = lastBuyingTimestamp - 2
  maximumPrice = 0
  while i <= currentDatapoint - 2:
    i += 1
    if maximumPrice < config["dataPoints"][i]:
      maximumPrice = config["dataPoints"][i]
  return maximumPrice

def insertTradeHistory(log, sendMessage, config, databaseClient, binanceClient, currentTime, coin, action, tradePrice, currentDollars, cryptoQuantity):
  # Here we have to calculate the gainOrLoss
  # For now, enter 0
  # TODO
  gainOrLoss = 0
  if config["dry_run"] == "true":
    currentTime = config["currentDatapoint"]
  try:
    prettyDate = datetime.datetime.fromtimestamp(currentTime).strftime("%Y-%m-%d_%H-%M-%S")
    query = "INSERT INTO trade_history VALUES (" + str(currentTime) + ",'" + prettyDate + "','" + coin + "','" + action + "'," + str(tradePrice) + "," + str(currentDollars) + "," + str(cryptoQuantity) + "," + str(gainOrLoss) + ")"
    log.info(query)
    databaseClient.execute(query)
    databaseClient.commit()
  except Exception as e:
    message = "[ERROR] When saving scraping in the database: " + str(e)
    log.info(message)
    sendMessage(log, config, message)