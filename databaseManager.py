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

def getPriceHistoryFromDatabase(config, coin, howMany):
  log = config["log"]
  databaseClient = config["databaseClient"]
  sendMessage = config["sendMessage"]
  # First, check the latest timestamp from database. If this is old, will return []
  databaseCursor = databaseClient.cursor()
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
  databaseCursor.execute("SELECT price FROM price_history WHERE coin='" + coin + "' order by timestamp desc limit " + str(howMany))
  dataPointsObj = databaseCursor.fetchall()
  dataPointsObj.reverse()
  dataPoints = []
  for price in dataPointsObj:
    dataPoints.append(price[0])
  return dataPoints


def getPriceHistoryFromFile(config, coin, howMany):
  log = config["log"]
  databaseClient = config["databaseClient"]
  sendMessage = config["sendMessage"]
  aggregatedBy = int(config["aggregated_by"])
  lookBackIntervals = int(config["buy_lookback_intervals"])
  currentDatapoint = config["currentDatapoint"]

  dataPoints = config["dataPoints"]

  if currentDatapoint < aggregatedBy * lookBackIntervals:
    return dataPoints[0:currentDatapoint]
  return dataPoints[currentDatapoint - aggregatedBy * lookBackIntervals: currentDatapoint]

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
    if config["dry_run"] == "false":
      currentDollars = 0
    else:
      currentDollars = 100 #TODO add in config
    return {"timestamp": 0, "doWeHaveCrypto": False, "tradeRealPrice": 0, "tradeAggregatedPrice": 0, "currentDollars": currentDollars, "cryptoQuantity": 0, "gainOrLoss": 0, "maximumPrice": 0}
  else:
    if lastTransaction[0][3] == "BUY":
      doWeHaveCrypto = True
      # If de we have crypto, we have to gate from history the maximum value of crypto after buying
      if config["dry_run"] == "false":
        maximumPrice = getMaximumPriceAfterLastTransactionFromDatabase(config, int(lastTransaction[0][0]))
      else:
        maximumPrice = getMaximumPriceAfterLastTransactionFromFile(config, int(lastTransaction[0][0]))
    else:
      doWeHaveCrypto = False
      maximumPrice = 0
    return {"timestamp": int(lastTransaction[0][0]), "doWeHaveCrypto": doWeHaveCrypto, "tradeRealPrice": float(lastTransaction[0][4]), "tradeAggregatedPrice": float(lastTransaction[0][5]), "currentDollars": float(lastTransaction[0][6]), "cryptoQuantity": float(lastTransaction[0][7]), "gainOrLoss": float(lastTransaction[0][8]), "maximumPrice": maximumPrice}

# If de we have crypto, we have to gate from history the maximum value of crypto after buying
def getMaximumPriceAfterLastTransactionFromDatabase(config, lastBuyingTimestamp):
  log = config["log"]
  databaseClient = config["databaseClient"]
  sendMessage = config["sendMessage"]
  coin = "BTCUSDT"
  databaseCursor = databaseClient.cursor()
  databaseCursor.execute("SELECT timestamp, max(price) FROM price_history WHERE coin='" + coin + "' AND timestamp > " + str(lastBuyingTimestamp))
  maximumPriceObj = databaseCursor.fetchall()
  maximumPriceTimestamp = int(maximumPriceObj[0][0])
  maximumPrice = float(maximumPriceObj[0][1])

  # Get list
  databaseCursor = databaseClient.cursor()
  query = "SELECT price FROM price_history WHERE coin='" + coin + "' AND timestamp >= " + str(maximumPriceTimestamp - 70 * int(config["aggregated_by"])) + " AND timestamp <= " + str(maximumPriceTimestamp + 70 * int(config["aggregated_by"]))
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
  while i < endIndex:
    i += 1
    suma += pricesList[i]
    lenSuma += 1

  maximumPriceNormalized = suma / lenSuma
  return maximumPriceNormalized

# Used from backtesting
def getMaximumPriceAfterLastTransactionFromFile(config, lastBuyingTimestamp):
  log = config["log"]
  databaseClient = config["databaseClient"]
  sendMessage = config["sendMessage"]
  currentDatapoint = config["currentDatapoint"]
  i = lastBuyingTimestamp - 2
  maximumPrice = 0
  while i <= currentDatapoint - 2:
    i += 1
    if maximumPrice < config["dataPoints"][i]:
      maximumPrice = config["dataPoints"][i]
      maximumIndex = i

  log.info("maximumPrice = " + str(maximumPrice))
  log.info("maximumIndex = " + str(maximumIndex))
  # Now try to normalize (average with neighbors).
  maximumIndexDiffEnd = (currentDatapoint - 1) - maximumIndex
  if maximumIndexDiffEnd >= int(config["aggregated_by"]) / 2:
    # We can put maximum exactly in the middle
    log.info("We can put maximum exactly in the middle")
    startIndex = int(maximumIndex - int(config["aggregated_by"]) / 2)
    endIndex = int(maximumIndex + int(config["aggregated_by"]) / 2)
  else:
    # We cannot put maximum exactly in the middle
    log.info("We CANNOT put maximum exactly in the middle")
    endIndex = int(currentDatapoint - 1)
    startIndex = int(endIndex - int(config["aggregated_by"]))
  suma = 0
  i = startIndex - 1
  lenSuma = 0
  while i < endIndex:
    i += 1
    suma += config["dataPoints"][i]
    lenSuma += 1

  maximumPriceNormalized = suma / lenSuma
  log.info("startIndex = " + str(startIndex))
  log.info("endIndex = " + str(endIndex))
  log.info("lenSuma = " + str(lenSuma))
  log.info("maximumPriceNormalized = " + str(maximumPriceNormalized))

  return maximumPriceNormalized

def insertTradeHistory(config, currentTime, coin, action, tradeRealPrice, tradeAggregatedPrice, currentDollars, cryptoQuantity):
  log = config["log"]
  databaseClient = config["databaseClient"]
  sendMessage = config["sendMessage"]
  # Here we have to calculate the gainOrLoss
  gainOrLoss = 0
  databaseCursor = databaseClient.cursor()
  if action == "SELL":
    query = "SELECT tradeRealPrice, cryptoQuantity from trade_history WHERE coin = '" + coin + "' AND timestamp = (SELECT MAX(timestamp + 0) FROM trade_history WHERE coin='" + coin + "')"

    databaseCursor.execute(query)
    dataPointsObj = databaseCursor.fetchall()
    oldDollars = dataPointsObj[0][0] * dataPointsObj[0][1]
    oldDollars += 0.001 * oldDollars
    gainOrLoss = currentDollars - oldDollars

  if config["dry_run"] == "true":
    currentTime = config["currentDatapoint"]
  try:
    prettyDate = datetime.datetime.fromtimestamp(currentTime).strftime("%Y-%m-%d_%H-%M-%S")
    query = "INSERT INTO trade_history VALUES (" + str(currentTime) + ",'" + prettyDate + "','" + coin + "','" + action + "'," + str(tradeRealPrice) + "," + str(tradeAggregatedPrice) + "," + str(currentDollars) + "," + str(cryptoQuantity) + "," + str(gainOrLoss) + ")"
    log.info(query)
    databaseClient.execute(query)
    databaseClient.commit()
  except Exception as e:
    message = "[ERROR] When saving scraping in the database: " + str(e)
    log.info(message)
    sendMessage(config, message)