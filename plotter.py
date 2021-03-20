#! /usr/bin/python3
import os
import sys
import time # for sleep
import mpld3 # for WEB rendering of plots
import sqlite3 # for database connection
import logging # for logging
import datetime # for logging
import traceback # for error handling
import configparser # for configuration parser
import matplotlib.pyplot as plt
from scipy.ndimage.filters import gaussian_filter1d # for interpolation

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
  log_name = "" + str(now.year) + "." + '{:02d}'.format(now.month) + "." + '{:02d}'.format(now.day) + "-plotter.log"
  log_name = os.path.join(currentDir, "logs", log_name)
  logging.basicConfig(format='%(asctime)s  %(message)s', level=logging.NOTSET,
                      handlers=[
                      logging.FileHandler(log_name),
                      logging.StreamHandler()
                      ])
  log = logging.getLogger()
  return log

def getPrices(config, coin, startTime, endTime):
  log = config["log"]
  databaseClient = config["databaseClient"]
  databaseCursor = databaseClient.cursor()

  query = "SELECT timestamp, price FROM price_history WHERE coin='" + coin + "' AND timestamp >= " + str(startTime) + " AND timestamp <= " + str(endTime)
  databaseCursor.execute(query)
  pricesX = []
  pricesY = []
  maximumPrice = 0
  minimumPrice = 100000000
  for entry in databaseCursor.fetchall():
    #pricesList.append((entry[0], entry[1]))
    pricesX.append(datetime.datetime.fromtimestamp(int(entry[0])))
    pricesY.append(float(entry[1]))
    if float(entry[1]) > maximumPrice:
      maximumPrice = float(entry[1])
    if float(entry[1]) < minimumPrice:
      minimumPrice = float(entry[1])
  return pricesX, pricesY, minimumPrice, maximumPrice

def getTrades(config, coin, startTime, endTime):
  log = config["log"]
  databaseClient = config["databaseClient"]
  databaseCursor = databaseClient.cursor()

  query = "SELECT timestamp, action FROM trade_history WHERE coin='" + coin + "' AND timestamp >= " + str(startTime) + " AND timestamp <= " + str(endTime)

  databaseCursor.execute(query)
  buyTrades = []
  sellTrades = []
  for entry in databaseCursor.fetchall():
    if entry[1] == "BUY":
      buyTrades.append(datetime.datetime.fromtimestamp(int(entry[0])))
    else:
      sellTrades.append(datetime.datetime.fromtimestamp(int(entry[0])))

  return buyTrades, sellTrades

def getPricesSmoothed(config, pricesX, pricesY):
  log = config["log"]
  pricesX.reverse()
  pricesY.reverse()
  aggregatedBy = 30
  i = 0
  pricesXAggregated = []
  pricesYAggregated = []
  while i < len(pricesX):
    sumaX = 0
    sumaY = 0
    currentLen = 0
    j = 0
    while j < aggregatedBy:
      if i < len(pricesX):
        sumaX += pricesX[i].timestamp()
        sumaY += pricesY[i]
        currentLen += 1
      i += 1
      j += 1
    pricesXAggregated.append(datetime.datetime.fromtimestamp(sumaX/currentLen))
    pricesYAggregated.append(sumaY/currentLen)

  pricesXAggregated.reverse()
  pricesYAggregated.reverse()

  pricesYSmoothed = gaussian_filter1d(pricesYAggregated, sigma=4)
  return pricesXAggregated, pricesYSmoothed

def plot(config, outputFileName, startTime, endTime):
  log = config["log"]
  coin = "BTCUSDT"
  pricesX, pricesY, minimumPrice, maximumPrice = getPrices(config, coin, startTime, endTime)

  buyTrades, sellTrades = getTrades(config, coin, startTime, endTime)

  log.info("len(pricesX) = " + str(len(pricesX)))
  log.info("len(pricesY) = " + str(len(pricesY)))
  log.info("minimumPrice = " + str(minimumPrice))
  log.info("maximumPrice = " + str(maximumPrice))
  log.info("len(buyTrades) = " + str(len(buyTrades)))
  log.info("len(sellTrades) = " + str(len(sellTrades)))

  #Create the Python figure
  #Set the size of the matplotlib canvas
  fig = plt.figure(figsize = (18,8))

  # Details
  plt.title("Bot Trade History")
  plt.ylabel("BTC Price")
  plt.xlabel("Date")
  # Show axes in both sides
  ax = fig.add_subplot(111)
  ax.yaxis.tick_right() # This breaks for manual plot, but for API it puts ok the scale on the right
  ax.yaxis.set_ticks_position('both')
  ax.tick_params(labeltop=False, labelright=True)

  # Show grid
  plt.grid(color='grey', linestyle='-', linewidth=0.3)

  # Plot prices
  plt.plot(pricesX, pricesY, linewidth=3)

  minimumY = minimumPrice - 0.01 * minimumPrice
  maximumY = maximumPrice + 0.01 * maximumPrice

  # Plot buy trades
  for trade in buyTrades:
    #plt.axvline(x=trade, color='g') # Problem when redering as HTML
    plt.plot((trade, trade), (minimumY, maximumY), color='g', linewidth=3)
  # Plot sell trades
  for trade in sellTrades:
    #plt.axvline(x=trade, color='r') # Problem when redering as HTML
    plt.plot((trade, trade), (minimumY, maximumY), color='r', linewidth=3)

  # Plot interpolate
  pricesXSmoothed, pricesYSmoothed = getPricesSmoothed(config, pricesX, pricesY)
  plt.plot(pricesXSmoothed, pricesYSmoothed, '--', linewidth=3)

  # Create "templates" directory (needed by Flask)
  if not os.path.isdir(os.path.join(currentDir, "templates")):
    os.mkdir(os.path.join(currentDir, "templates"))

  html_str = mpld3.fig_to_html(fig)
  Html_file= open(os.path.join("templates", outputFileName),"w")
  Html_file.write(html_str)
  Html_file.close()

  # Show plot
  #plt.savefig('plot.png') # Maybe needed
  # plt.show()
  if config["backtesting"] == "true":
    log.info("########")
    log.info("You can see the plot at:")
    log.info("file://" + os.path.join(currentDir, "templates", outputFileName))

def mainFunction(outputFileName, startTime, endTime):
  log = getLogger()
  log.info("################################# New run plotter.py")
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

    # Construct plot
    plot(config, outputFileName, int(startTime), int(endTime))

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

  if len(sys.argv) != 4:
    print ("Wrong number of parameters. Use: python plotter.py <outputFileName> <startTime> <endTime>")
    sys.exit(99)
  else:
    mainFunction(sys.argv[1], sys.argv[2], sys.argv[3])