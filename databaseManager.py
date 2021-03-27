import time
import datetime
import sqlite3 # for database connection
from functools import wraps # for measuring time of function

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

# Function used for backtesting.
# Excessive reading from the disk is slow.
def loadDatabaseInMemory(config):
  databaseClient = config["databaseClient"]
  databaseClientInMemory = sqlite3.connect(':memory:')
  databaseClient.backup(databaseClientInMemory)
  config["databaseClientInMemory"] = databaseClientInMemory

# Funciton used for backtesting
# Excessive reading from the disk is slow.
def writeDatabaseOnDisk(config):
  log = config["log"]
  log.info("Dumping database on disk.")
  databaseClient = config["databaseClient"]
  databaseClientInMemory = config["databaseClientInMemory"]
  databaseCursor = databaseClient.cursor()
  databaseCursor.execute("DROP TABLE price_history")
  databaseCursor.execute("DROP TABLE trade_history")
  databaseClientInMemory.backup(databaseClient)

# Funcion used only when back_testing
def emptyTradeHistoryDatabase(config):
  log = config["log"]
  databaseClient = config["databaseClient"]
  sendMessage = config["sendMessage"]
  log.info("EMPTYING trade_history table.")
  databaseClient.execute('''DELETE FROM trade_history''')
  databaseClient.commit()

@fn_timer
def getPriceHistory(config, coin, howMany):
  log = config["log"]
  if config["backtesting"] == "false":
    databaseClient = config["databaseClient"]
  else:
    databaseClient = config["databaseClientInMemory"]
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

  # When running in production, get the most recent prices
  # When running in backtesting mode, get until the currentDatapoint
  if config["backtesting"] == "false":
    query = "SELECT timestamp, price FROM price_history WHERE coin='" + coin + "'"
    databaseCursor.execute(query)
    dataPointsObj = databaseCursor.fetchall()
  else:
    currentDatapoint = config["currentDatapoint"]
    # From DB
    #query = "SELECT timestamp, price FROM price_history WHERE coin='" + coin + "' AND timestamp <= " + str(currentDatapoint) + " AND timestamp >= " + str(config["backtesting_start_timestamp"])
    #databaseCursor.execute(query)
    #dataPointsObj = databaseCursor.fetchall()
    # From variable
    dataPointsObj = getPricesBetweenTimestamps(config, coin, config["backtesting_start_timestamp"], currentDatapoint)

  dataPointsObj = dataPointsObj[len(dataPointsObj) - howMany:]

  dataPoints = []
  for price in dataPointsObj:
    dataPoints.append(price[1])
  return dataPoints

# Function that reads from DB the last transaction
def getLastTransactionStatus(config, coin):
  log = config["log"]
  if config["backtesting"] == "false":
    databaseClient = config["databaseClient"]
  else:
    databaseClient = config["databaseClientInMemory"]
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
      # If we have crypto, we have to get from history the maximum value of crypto after buying
      maximumPrice, maximumAggregatedPrice = getMaximumPriceAfterLastTransaction(config, int(lastTransaction[0][0]))
    else:
      doWeHaveCrypto = False
      maximumPrice = 0
      maximumAggregatedPrice = 0
    return {"timestamp": int(lastTransaction[0][0]), "doWeHaveCrypto": doWeHaveCrypto, "tradeRealPrice": float(lastTransaction[0][4]), "tradeAggregatedPrice": float(lastTransaction[0][5]), "currentDollars": float(lastTransaction[0][6]), "cryptoQuantity": float(lastTransaction[0][7]), "gainOrLoss": float(lastTransaction[0][8]), "maximumPrice": maximumPrice, "maximumAggregatedPrice": maximumAggregatedPrice}

# If de we have crypto, we have to gate from history the maximum value of crypto after buying
@fn_timer
def getMaximumPriceAfterLastTransaction(config, lastBuyingTimestamp):
  log = config["log"]
  if config["backtesting"] == "false":
    databaseClient = config["databaseClient"]
  else:
    databaseClient = config["databaseClientInMemory"]
  sendMessage = config["sendMessage"]
  coin = "BTCUSDT"
  databaseCursor = databaseClient.cursor()
  if config["backtesting"] == "false":
    query = "SELECT timestamp, max(price) FROM price_history WHERE coin='" + coin + "' AND timestamp > " + str(lastBuyingTimestamp)
    databaseCursor.execute(query)
    maximumPriceObj = databaseCursor.fetchall()
    maximumPriceTimestamp = int(maximumPriceObj[0][0])
    maximumPrice = float(maximumPriceObj[0][1])
  else:
    # From DB
    #query = "SELECT timestamp, max(price) FROM price_history WHERE coin='" + coin + "' AND timestamp > " + str(lastBuyingTimestamp) + " AND timestamp <= " + str(config["currentDatapoint"])
    #databaseCursor.execute(query)
    #maximumPriceObj = databaseCursor.fetchall()
    #maximumPriceTimestamp = int(maximumPriceObj[0][0])
    #maximumPrice = float(maximumPriceObj[0][1])
    # From variable
    dataPointsObj = getPricesBetweenTimestamps(config, coin, lastBuyingTimestamp, config["currentDatapoint"])
    # Now calculate maximum
    maximumPriceObj = max(dataPointsObj, key=lambda x: x[1])
    maximumPriceTimestamp = int(maximumPriceObj[0])
    maximumPrice = float(maximumPriceObj[1])

  # Get list
  databaseCursor = databaseClient.cursor()
  if config["backtesting"] == "false":
    query = "SELECT timestamp, price FROM price_history WHERE coin='" + coin + "' AND timestamp >= " + str(maximumPriceTimestamp - 70 * int(config["aggregated_by"])) + " AND timestamp <= " + str(maximumPriceTimestamp + 70 * int(config["aggregated_by"]))
    databaseCursor.execute(query)
    dataPointsObj = databaseCursor.fetchall()
  else:
    # From DB
    #query = "SELECT timestamp, price FROM price_history WHERE coin='" + coin + "' AND timestamp >= " + str(maximumPriceTimestamp - 70 * int(config["aggregated_by"])) + " AND timestamp <= " + str(maximumPriceTimestamp + 70 * int(config["aggregated_by"])) + " AND timestamp <= " + str(config["currentDatapoint"])
    #databaseCursor.execute(query)
    #dataPointsObj = databaseCursor.fetchall()
    # From variable
    startTimestamp = maximumPriceTimestamp - 70 * int(config["aggregated_by"])
    endTimestamp = min(maximumPriceTimestamp + 70 * int(config["aggregated_by"]), config["currentDatapoint"])
    dataPointsObj = getPricesBetweenTimestamps(config, coin, startTimestamp, endTimestamp)

  pricesList = []
  for entry in dataPointsObj:
    pricesList.append(entry[1])

  maximumIndex = pricesList.index(maximumPrice)
  if config["backtesting"] == "false":
    currentTime = int(time.time())
  else:
    currentTime = config["currentDatapoint"]
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
  # TODO check for backtesting to not use next variables. Maybe do a deepcopy to be sure that index is not exceeded
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
  if config["backtesting"] == "false":
    databaseClient = config["databaseClient"]
  else:
    databaseClient = config["databaseClientInMemory"]
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
@fn_timer
def arePricesGoingUp(config, coin, tradeMethod):
  log = config["log"]
  if config["backtesting"] == "false":
    databaseClient = config["databaseClient"]
  else:
    databaseClient = config["databaseClientInMemory"]
  # We do all of this in a try because in case of any error, the bot will not sell. So will return False if any error in order to not disturb functionality
  try:
    databaseCursor = databaseClient.cursor()
    if tradeMethod == "BUY":
      trendLookbackIntervals = int(config["trend_direction_buy_intervals"])
    else:
      trendLookbackIntervals = int(config["trend_direction_sell_intervals"])

    if config["backtesting"] == "false":
      query = "SELECT price FROM price_history WHERE coin='" + coin
      databaseCursor.execute(query)
      dataPointsObj = databaseCursor.fetchall()
    else:
      # From DB
      #query = "SELECT price FROM price_history WHERE coin='" + coin + "' AND timestamp <= " + str(config["currentDatapoint"])
      #databaseCursor.execute(query)
      #dataPointsObj = databaseCursor.fetchall()
      dataPointsObj = getPricesBetweenTimestamps(config, coin, 0, config["currentDatapoint"])

    dataPointsObj = dataPointsObj[len(dataPointsObj) - trendLookbackIntervals:]
    dataPoints = []
    for price in dataPointsObj:
      dataPoints.append(price[1])
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

# Used for backtesting
@fn_timer
def getOldestPriceAfterCurrentDatapoint(config, coin):
  log = config["log"]
  if config["backtesting"] == "false":
    databaseClient = config["databaseClient"]
  else:
    databaseClient = config["databaseClientInMemory"]
  sendMessage = config["sendMessage"]
  # First, check the latest timestamp from database. If this is old, will return []
  databaseCursor = databaseClient.cursor()
  currentDatapoint = config["currentDatapoint"]

  # From DB
  #query = "SELECT timestamp, price FROM price_history WHERE coin='" + coin + "' AND timestamp > " + str(currentDatapoint) + " AND timestamp < " + str(config["backtesting_end_timestamp"]) + " limit 1"
  #databaseCursor.execute(query)
  #nextDatapointObj = databaseCursor.fetchall()
  #if len(nextDatapointObj) != 1:
  #  return int(nextDatapointObj[0][0])
  # From variable
  nextDatapointObj = getPricesBetweenTimestamps(config, coin, currentDatapoint, config["backtesting_end_timestamp"])
  if len(nextDatapointObj) != 1:
    if int(nextDatapointObj[1][0]) <= int(config["backtesting_end_timestamp"]):
      return int(nextDatapointObj[1][0])

  # Return 0 in order to stop
  return 0

# Function used for backtesting.
# When price_history gets bigger, the lookup in the price_history for each datapoint gets heavier.
def readPriceHistoryInMemory(config):
  log = config["log"]
  databaseClient = config["databaseClientInMemory"]
  databaseCursor = databaseClient.cursor()
  priceDictionary = {}
  for coin in config["coins_to_scrape"].split("|"):
    query = "SELECT timestamp, price FROM price_history WHERE coin='" + coin + "'"
    databaseCursor.execute(query)
    pricesObj = databaseCursor.fetchall()
    priceDictionary[coin] = pricesObj

  # Create hashtable with the prices (for better lookup)
  datapointsIndexDictionnary = {}
  for coin in config["coins_to_scrape"].split("|"):
    datapointsIndexDictionnary[coin] = {}
    for i, datapoint in enumerate(priceDictionary[coin]):
      datapointsIndexDictionnary[coin][str(datapoint[0])] = i

    # Add config["backtesting_start_timestamp"] and config["backtesting_end_timestamp"] in the hashtable.
    if str(config["backtesting_start_timestamp"]) not in datapointsIndexDictionnary[coin]:
      for i, priceObj in enumerate(priceDictionary[coin]):
        if int(priceObj[0]) >= int(config["backtesting_start_timestamp"]):
          datapointsIndexDictionnary[coin][str(config["backtesting_start_timestamp"])] = i
          break
    if str(config["backtesting_end_timestamp"]) not in datapointsIndexDictionnary[coin]:
      for i, priceObj in enumerate(priceDictionary[coin]):
        if int(priceObj[0]) > int(config["backtesting_end_timestamp"]):
          datapointsIndexDictionnary[coin][str(config["backtesting_end_timestamp"])] = i
          break

    # Add 0 and 3000000000
    datapointsIndexDictionnary[coin]["0"] = 0
    datapointsIndexDictionnary[coin]["3000000000"] = len(priceDictionary[coin]) - 1
    datapointsIndexDictionnary[coin][str(config["backtesting_end_timestamp"])] = len(priceDictionary[coin]) - 1

  config["priceDictionary"] = priceDictionary
  config["datapointsIndexDictionnary"] = datapointsIndexDictionnary

  log.info("Prices successfully read in memory to avoid DB access for each datapoint")

# Used for backtesting. Prices are not read from the DB, but from a variable
# Because it is backtesting, we have all the values in a variable
# And we need only the prices between a timestamp
# Function will return prices: [startTimestamp, endTimestamp] - closed intervals
@fn_timer
def getPricesBetweenTimestamps(config, coin, startTimestamp, endTimestamp):
  log = config["log"]

  if str(startTimestamp) in config["datapointsIndexDictionnary"][coin] and str(endTimestamp) in config["datapointsIndexDictionnary"][coin]:
    startIndex = config["datapointsIndexDictionnary"][coin][str(startTimestamp)]
    endIndex = config["datapointsIndexDictionnary"][coin][str(endTimestamp)]
    return config["priceDictionary"][coin][startIndex:endIndex + 1]

  startIndex = -1
  endIndex = -1
  i = 0
  for i, priceObj in enumerate(config["priceDictionary"][coin]):
    if int(priceObj[0]) >= int(startTimestamp) and startIndex == -1:
      startIndex = i
    if int(priceObj[0]) > int(endTimestamp):
      endIndex = i
      return config["priceDictionary"][coin][startIndex:endIndex]
  return config["priceDictionary"][coin][startIndex:len(config["priceDictionary"][coin])]
