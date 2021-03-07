#! /usr/bin/python3
import os
import sys
import time # for sleep
import sqlite3 # for database connection
import logging # for logging
import datetime # for logging
import traceback # for error handling
import configparser # for configuration parser
import matplotlib.pyplot as plt

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
  log_name = "" + str(now.year) + "." + '{:02d}'.format(now.month) + "-plotter.log"
  log_name = os.path.join(currentDir, "logs", log_name)
  logging.basicConfig(format='%(asctime)s  %(message)s', level=logging.NOTSET,
                      handlers=[
                      logging.FileHandler(log_name),
                      logging.StreamHandler()
                      ])
  log = logging.getLogger()
  return log

def getPrices(log, coin):
  log = config["log"]
  databaseClient = config["databaseClient"]
  databaseCursor = databaseClient.cursor()

  query = "SELECT timestamp, price FROM price_history WHERE coin='" + coin + "'"
  databaseCursor.execute(query)
  pricesX = []
  pricesY = []
  for entry in databaseCursor.fetchall():
    #pricesList.append((entry[0], entry[1]))
    pricesX.append(datetime.datetime.fromtimestamp(int(entry[0])))
    pricesY.append(float(entry[1]))
  return pricesX, pricesY

def getTrades(log, coin):
  log = config["log"]
  databaseClient = config["databaseClient"]
  databaseCursor = databaseClient.cursor()

  query = "SELECT timestamp, action FROM trade_history WHERE coin='" + coin + "'"
  databaseCursor.execute(query)
  buyTrades = []
  sellTrades = []
  for entry in databaseCursor.fetchall():
    if entry[1] == "BUY":
      buyTrades.append(datetime.datetime.fromtimestamp(int(entry[0])))
    else:
      sellTrades.append(datetime.datetime.fromtimestamp(int(entry[0])))
  return buyTrades, sellTrades

def plot(config):
  log = config["log"]
  coin = "BTCUSDT"
  pricesX, pricesY = getPrices(config, coin)
  buyTrades, sellTrades = getTrades(config, coin)

  log.info("len(pricesX) = " + str(len(pricesX)))
  log.info("len(pricesY) = " + str(len(pricesY)))
  log.info("len(buyTrades) = " + str(len(buyTrades)))
  log.info("len(sellTrades) = " + str(len(sellTrades)))

  # Details
  plt.title("Bot Trade History")
  plt.ylabel("BTC Price")
  plt.xlabel("Date")

  # Plot prices
  plt.plot(pricesX, pricesY)

  # Plot buy trades
  for trade in buyTrades:
    plt.axvline(x=trade, color='g')

  # Plot sell trades
  for trade in sellTrades:
    plt.axvline(x=trade, color='r')

  # Show plot
  #plt.savefig('bank_data.png')
  plt.show()

def mainFunction():
  log = getLogger()
  log.info("################################# New run")
  try:
    # Check if configuration file exists, and exit if it is not
    if os.path.isfile(configFile) is False:
      message = "[FATAL] Config file does not exist. Exiting"
      log.info(message)
      sys.exit(1)

    # Read config file
    configObj = configparser.ConfigParser()
    configObj.read(configFile)
    global config
    config = configObj._sections[configSection]

    # Create the database if it not exists
    if os.path.isfile(config["database_file"]) is False:
      log.info("Database does not exist. It will be created now.")

    # If database does not exist, the first connect will create it
    try:
      databaseClient = sqlite3.connect(config["database_file"])
    except Exception as e:
      message = "[FATAL] Couldn't connect to the database. Investigate manually"
      log.info(message)
      log.info(e)
      sys.exit(2)

    config["databaseClient"] = databaseClient
    config["log"] = log
    plot(config)

  ##### END #####
  except KeyboardInterrupt:
    log.info("Ctrl+C received. Gracefully quiting.")
    sys.exit(0)
  except Exception as e:
    log.info("Fatal Error: {}".format(e))
    tracebackError = traceback.format_exc()
    log.info(tracebackError)
    sys.exit(99)

##### BODY #####
if __name__ == "__main__":

  if len(sys.argv) != 1:
    log.info("Wrong number of parameters. Use: python plotter.py")
    sys.exit(99)
  else:
    mainFunction()