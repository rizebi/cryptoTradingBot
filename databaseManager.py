import time
import datetime

def createTables(config):
  log = config["log"]
  databaseClient = config["databaseClient"]
  sendMessage = config["sendMessage"]
  log.info("Check if table <trade_history> exits")
  databaseCursor = databaseClient.cursor()
  databaseCursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
  tables = databaseCursor.fetchall()
  if ("trade_history",) in tables:
    log.info("Table <trade_history> already exists. Continue.")
    return
  log.info("Table <trade_history> does not exists. Will create it now.")
  databaseClient.execute('''CREATE TABLE trade_history
               (timestamp text, date text, coin text, action text, tradeRealPrice real, tradeAggregatedPrice real, currentDollars real, cryptoQuantity real, gainOrLoss real)''')
  databaseClient.commit()
  log.info("Table <trade_history> successfully created.")

# Funcion used only when back_testing
def emptyTradeHistoryDatabase(config):
  log = config["log"]
  databaseClient = config["databaseClient"]
  sendMessage = config["sendMessage"]
  log.info("EMPTYING trade_history table.")
  databaseClient.execute('''DELETE FROM trade_history''')
  databaseClient.commit()

def getPriceHistory(config, coin, howMany):
  log = config["log"]
  databaseClient = config["databaseClient"]
  sendMessage = config["sendMessage"]
  # First, check the latest timestamp from database. If this is old, will return []
  databaseCursor = databaseClient.cursor()

  # Guardian in order for bot to not run if too old data in database
  if config["backtesting"] == "false":
    databaseCursor.execute("SELECT max(timestamp) FROM price_history")
    dataPointsObj = databaseCursor.fetchall()
    currentTime = time.time()
    if currentTime - float(dataPointsObj[0][0]) > 300:
      message = "[ERROR] Too old price history in database. Maybe scraper is down. Skipping the bot run for this time."
      log.info(message)
      sendMessage(config, message)
      return []

  # TODO here might be a problem when ordering by timestamp
  # It will see 100 < 94 for example
  # But, because epochTime has constant number of digits, it should be ok

  # When running in production, get the most recent prices
  # When running in backtesting mode, get until the currentDatapoint
  if config["backtesting"] == "false":
    query = "SELECT price FROM price_history WHERE coin='" + coin + "' order by timestamp desc limit " + str(howMany)
  else:
    currentDatapoint = config["currentDatapoint"]
    query = "SELECT price FROM price_history WHERE coin='" + coin + "' AND timestamp <= " + str(currentDatapoint) + " AND timestamp >= " + str(config["backtesting_start_timestamp"]) + " order by timestamp desc limit " + str(howMany)

  databaseCursor.execute(query)
  dataPointsObj = databaseCursor.fetchall()
  dataPointsObj.reverse()
  dataPoints = []
  for price in dataPointsObj:
    dataPoints.append(price[0])
  return dataPoints

# Function that reads from DB the last transaction
def getLastTransactionStatus(config, coin):
  log = config["log"]
  databaseClient = config["databaseClient"]
  sendMessage = config["sendMessage"]
  databaseCursor = databaseClient.cursor()
  databaseCursor.execute("SELECT * FROM trade_history WHERE coin='" + coin + "' AND timestamp = (SELECT MAX(timestamp + 0) FROM trade_history WHERE coin='" + coin + "')")
  lastTransaction = databaseCursor.fetchall()
  if len(lastTransaction) == 0:
    log.info("No history on the database. Will go with the default option: no Crypto")
    if config["backtesting"] == "false":
      currentDollars = 0
    else:
      currentDollars = 100 #TODO add in config
    return {"timestamp": 0, "doWeHaveCrypto": False, "tradeRealPrice": 0, "tradeAggregatedPrice": 0, "currentDollars": currentDollars, "cryptoQuantity": 0, "gainOrLoss": 0, "maximumPrice": 0, "maximumAggregatedPrice": 0}
  else:
    if lastTransaction[0][3] == "BUY":
      doWeHaveCrypto = True
      # If de we have crypto, we have to gate from history the maximum value of crypto after buying
      maximumPrice, maximumAggregatedPrice = getMaximumPriceAfterLastTransaction(config, int(lastTransaction[0][0]))
    else:
      doWeHaveCrypto = False
      maximumPrice = 0
      maximumAggregatedPrice = 0
    return {"timestamp": int(lastTransaction[0][0]), "doWeHaveCrypto": doWeHaveCrypto, "tradeRealPrice": float(lastTransaction[0][4]), "tradeAggregatedPrice": float(lastTransaction[0][5]), "currentDollars": float(lastTransaction[0][6]), "cryptoQuantity": float(lastTransaction[0][7]), "gainOrLoss": float(lastTransaction[0][8]), "maximumPrice": maximumPrice, "maximumAggregatedPrice": maximumAggregatedPrice}

# If de we have crypto, we have to gate from history the maximum value of crypto after buying
def getMaximumPriceAfterLastTransaction(config, lastBuyingTimestamp):
  log = config["log"]
  databaseClient = config["databaseClient"]
  sendMessage = config["sendMessage"]
  coin = "BTCUSDT"
  databaseCursor = databaseClient.cursor()
  if config["backtesting"] == "false":
    query = "SELECT timestamp, max(price) FROM price_history WHERE coin='" + coin + "' AND timestamp > " + str(lastBuyingTimestamp)
  else:
    query = "SELECT timestamp, max(price) FROM price_history WHERE coin='" + coin + "' AND timestamp > " + str(lastBuyingTimestamp) + " AND timestamp <= " + str(config["currentDatapoint"])

  databaseCursor.execute(query)
  maximumPriceObj = databaseCursor.fetchall()
  maximumPriceTimestamp = int(maximumPriceObj[0][0])
  maximumPrice = float(maximumPriceObj[0][1])

  # Get list
  databaseCursor = databaseClient.cursor()
  if config["backtesting"] == "false":
    query = "SELECT price FROM price_history WHERE coin='" + coin + "' AND timestamp >= " + str(maximumPriceTimestamp - 70 * int(config["aggregated_by"])) + " AND timestamp <= " + str(maximumPriceTimestamp + 70 * int(config["aggregated_by"]))
  else:
      query = "SELECT price FROM price_history WHERE coin='" + coin + "' AND timestamp >= " + str(maximumPriceTimestamp - 70 * int(config["aggregated_by"])) + " AND timestamp <= " + str(maximumPriceTimestamp + 70 * int(config["aggregated_by"])) + " AND timestamp <= " + str(config["currentDatapoint"])
  databaseCursor.execute(query)
  pricesList = []
  for entry in databaseCursor.fetchall():
    pricesList.append(entry[0])

  maximumIndex = pricesList.index(maximumPrice)
  currentTime = int(time.time())
  if (currentTime - maximumPriceTimestamp) / 60 >= int(config["aggregated_by"]) / 2:
    # We can put maximum exactly in the middle
    startIndex = int(maximumIndex - int(config["aggregated_by"]) / 2)
    endIndex = int(maximumIndex + int(config["aggregated_by"]) / 2)
  else:
    # We cannot put maximum exactly in the middle
    endIndex = int(len(pricesList) - 1)
    startIndex = int(endIndex - int(config["aggregated_by"]))

  suma = 0
  i = startIndex - 1
  lenSuma = 0
  # TODO check for index out of range
  while i < endIndex:
    i += 1
    if i < len(pricesList):
      suma += pricesList[i]
      lenSuma += 1
    else:
      message = "[DEBUG] We encountered index out of range in getMaximumPriceAfterLastTransaction when calculating averageMaximum.\n"
      message += "startIndex = " + str(startIndex) + "\n"
      message += "endIndex = " + str(endIndex) + "\n"
      message += "i = " + str(i) + "\n"
      message += "len(pricesList) = " + str(len(pricesList)) + "\n"
      message += "lenSuma = " + str(lenSuma) + "\n"
      sendMessage(config, message)

  maximumAggregatedPrice = suma / lenSuma
  return maximumPrice, maximumAggregatedPrice

def insertTradeHistory(config, currentTime, coin, action, tradeRealPrice, tradeAggregatedPrice, currentDollars, cryptoQuantity):
  log = config["log"]
  databaseClient = config["databaseClient"]
  sendMessage = config["sendMessage"]
  # Here we have to calculate the gainOrLoss
  gainOrLoss = 0
  databaseCursor = databaseClient.cursor()
  if action == "SELL":
    query = "SELECT tradeRealPrice, cryptoQuantity from trade_history WHERE coin = '" + coin + "' AND timestamp = (SELECT MAX(timestamp + 0) FROM trade_history WHERE coin='" + coin + "')"

    # TODO. Aici ar trebui sa se calculeze mai corect. Nu cu 0.001. Si diferentiat intre backtesting si non backtesting
    databaseCursor.execute(query)
    dataPointsObj = databaseCursor.fetchall()
    oldDollars = dataPointsObj[0][0] * dataPointsObj[0][1]
    oldDollars += 0.001 * oldDollars
    gainOrLoss = currentDollars - oldDollars

  if config["backtesting"] == "true":
    currentTime = config["currentDatapoint"]
  try:
    prettyDate = datetime.datetime.fromtimestamp(currentTime).strftime("%Y-%m-%d_%H-%M-%S")
    query = "INSERT INTO trade_history VALUES (" + str(currentTime) + ",'" + prettyDate + "','" + coin + "','" + action + "'," + str(tradeRealPrice) + "," + str(tradeAggregatedPrice) + "," + str(currentDollars) + "," + str(cryptoQuantity) + "," + str(gainOrLoss) + ")"
    log.info(query)
    databaseClient.execute(query)
    databaseClient.commit()
  except Exception as e:
    message = "[ERROR] When saving trade in the database: " + str(e)
    log.info(message)
    sendMessage(config, message)

# tradeMethod is BUY or SELL in order to choose the right parameter
def arePricesGoingUp(config, coin, tradeMethod):
  log = config["log"]
  databaseClient = config["databaseClient"]
  # We do all of this in a try because in case of any error, the bot will not sell. So will return False if any error in order to not disturb functionality
  try:
    databaseCursor = databaseClient.cursor()
    if tradeMethod == "BUY":
      trendLookbackIntervals = int(config["trend_direction_buy_intervals"])
    else:
      trendLookbackIntervals = int(config["trend_direction_sell_intervals"])

    if config["backtesting"] == "false":
      query = "SELECT price FROM price_history WHERE coin='" + coin + "' order by timestamp desc limit " + str(trendLookbackIntervals)
    else:
      query = "SELECT price FROM price_history WHERE coin='" + coin + "' AND timestamp <= " + str(config["currentDatapoint"]) + " order by timestamp desc limit " + str(trendLookbackIntervals)
    databaseCursor.execute(query)
    dataPointsObj = databaseCursor.fetchall()
    dataPointsObj.reverse()
    dataPoints = []
    for price in dataPointsObj:
      dataPoints.append(price[0])
    # The commented 3 lines are for average
    #currentRealPrice = dataPoints[-1]
    #averagePrice = sum(dataPoints) / trendLookbackIntervals
    #return currentRealPrice >= averagePrice
    i = 0
    while i < len(dataPoints) - 1:
      i += 1
      if dataPoints[i - 1] > dataPoints[i]:
        return False
    return True
  except Exception as e:
    message = "[ERROR] arePricesGoingUp!!!!!! INVESTIGATE"
    log.info(message)
    log.info(e)
    sendMessage(config, message)
    return False

def getOldestPriceAfterCurrentDatapoint(config, coin):
  log = config["log"]
  databaseClient = config["databaseClient"]
  sendMessage = config["sendMessage"]
  # First, check the latest timestamp from database. If this is old, will return []
  databaseCursor = databaseClient.cursor()
  currentDatapoint = config["currentDatapoint"]

  query = "SELECT timestamp FROM price_history WHERE coin='" + coin + "' AND timestamp > " + str(currentDatapoint) + " AND timestamp < " + str(config["backtesting_end_timestamp"]) + " order by timestamp asc limit 1"

  databaseCursor.execute(query)
  nextDatapointObj = databaseCursor.fetchall()
  if len(nextDatapointObj) != 0:
    return int(nextDatapointObj[0][0])
  else:
    # Return 0 in order to stop
    return 0