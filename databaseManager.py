import time
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
               (timestamp text, coin text, action text, currentPrice real, currentDollars real, cryptoQuantity real, gainOrLoss real)''')
  databaseClient.commit()
  log.info("Table <trade_history> successfully created.")

def getPriceHistory(log, sendMessage, config, databaseClient, binanceClient, coin, howMany):
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

# Function that reads from DB the last transaction
def getLastTransactionStatus(log, sendMessage, config, databaseClient, binanceClient, coin):
  # Get current balance
  currentDollars = getCurrencyBalance(log, sendMessage, config, binanceClient, "USDT")
  cryptoQuantity = getCurrencyBalance(log, sendMessage, config, binanceClient, "BTC")

  databaseCursor = databaseClient.cursor()
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
def getMaximumPriceAfter(log, sendMessage, config, databaseClient, binanceClient, lastBuyingTimestamp):
  coin = "BTCUSDT"
  databaseCursor = databaseClient.cursor()
  databaseCursor.execute("SELECT max(price) FROM price_history WHERE coin='" + coin + "' AND timestamp > " + lastBuyingTimestamp)
  maximumPrice = databaseCursor.fetchall()
  return maximumPrice[0][0]

def insertTradeHistory(log, sendMessage, config, databaseClient, binanceClient, currentTime, coin, action, currentPrice, currentDollars, cryptoQuantity):
  # Here we have to calculate the gainOrLoss
  # For now, enter 0
  # TODO
  gainOrLoss = 0
  try:
    query = "INSERT INTO trade_history VALUES (" + str(currentTime) + ",'" + coin + "','" + action + "'," + str(currentPrice) + "," + str(currentDollars) + "," + str(cryptoQuantity) + "," + str(gainOrLoss) + ")"
    log.info(query)
    databaseClient.execute(query)
    databaseClient.commit()
  except Exception as e:
    message = "[ERROR] When saving scraping in the database: " + str(e)
    log.info(message)
    sendMessage(log, config, message)