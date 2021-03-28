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
  log_name = "" + str(now.year) + "." + '{:02d}'.format(now.month) + "." + '{:02d}'.format(now.day) + "-scraper.log"
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
        'text': "[scraper]" + message,
        'parse_mode': 'HTML'
    }
    return requests.post("https://api.telegram.org/bot{token}/sendMessage".format(token=config["bot_token"]), data=payload).content
  except Exception as e:
    log.info("Error when sending Telegram message: {}".format(e))
    tracebackError = traceback.format_exc()
    log.info(tracebackError)

def createTable(log):
  log.info("Check if table exits")
  databaseCursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
  tables = databaseCursor.fetchall()
  print(tables)
  if ("price_history",) in tables:
    log.info("Table <price_history> already exists. Continue.")
    return

  log.info("Table <price_history> does not exists. Will create it now.")
  databaseConnection.execute('''CREATE TABLE price_history
               (timestamp text, date text, coin text, price real)''')
  databaseConnection.commit()
  log.info("Table <price_history> successfully created.")

def getCoinPrice(log, client, coin):
  i = 0
  while i <= 10:
    i += 1
    if i > 1:
      log.info("Retry number " + str(i) + " for coin: '" + coin + "'")
    try:
      # This will return the actual price (too spikey)
      return float(client.get_symbol_ticker(symbol=coin)["price"])
      # This will return avg(5min)
      #return client.get_avg_price(symbol=coin)["price"]
    except BinanceAPIException as e:
      message = "[ERROR API] When getting current price for " + coin + ": " + str(e)
      log.info(message)
      sendMessage(log, message)
    except Exception as e:
      message = "[ERROR] When getting current price for " + coin + ": " + str(e)
      log.info(message)
      sendMessage(log, message)
    time.sleep(1)
  return None

def savePriceInDatabase(log, currentTime, coin, currentPrice):
  try:
    prettyDate = datetime.datetime.fromtimestamp(currentTime).strftime("%Y-%m-%d_%H-%M-%S")
    query = "INSERT INTO price_history VALUES (" + str(currentTime) + ",'" + prettyDate + "','" + coin + "'," + str(currentPrice) + ")"
    log.info(query)
    databaseConnection.execute(query)
    databaseConnection.commit()
  except Exception as e:
    message = "[ERROR] When saving price scraping in the database: " + str(e)
    log.info(message)
    sendMessage(log, message)

# The function should never end, that scrape, and write in the database
def scrape(log):
  log.info("Starting scraping.")
  scrapesNumberPerInterval = int(config["scrapes_number_per_interval"])
  secondsBetweenScrapes = int(config["seconds_between_scrapes"])
  # We will insert in DB one price every secondsBetweenScrapes seconds
  # That price will be the average between scrapesNumberPerInterval scrapes
  # Calculate the sleepTime between queries to binance
  sleepTime = float(secondsBetweenScrapes / scrapesNumberPerInterval)
  pricesDict = {}
  clientStartTime = 0
  clientAgeMaximumAge = 3600

  while True:
    # Update logger handler
    log = getLogger()
    log.info("DEBUG: New loop")
    # Refresh Binance client if time.time() - clientStartTime exceeded clientAgeMaximumAge
    if time.time() - clientStartTime >= clientAgeMaximumAge:
      try:
        client = Client(config["api_key"], config["api_secret_key"])
        clientStartTime = time.time()
      except BinanceAPIException as e:
        message = "[ERROR API] When getting refreshing client: " + str(e)
        log.info(message)
        sendMessage(log, message)
        time.sleep(3)
        continue
      except Exception as e:
        message = "[ERROR] When getting refreshing client: " + str(e)
        log.info(message)
        sendMessage(log, message)
        time.sleep(3)
        continue

    startTime = time.time()
    for coin in config["coins_to_scrape"].split("|"):
        currentPrice = getCoinPrice(log, client, coin)
        if currentPrice == None:
          message = "Got no data now for coin " + coin + ". Continuing.."
          sendMessage(log, message)
          continue
        log.info("For coin " + coin + " we got price: " + str(currentPrice))

        if coin not in pricesDict:
          pricesDict[coin] = []
          if currentPrice != None:
            pricesDict[coin].append(currentPrice)
        else:
          if len(pricesDict[coin]) < scrapesNumberPerInterval - 1:
            # Just add to the list
            if currentPrice != None:
              pricesDict[coin].append(currentPrice)
          else:
            # Add the current scrape, and write in the DB the average, and empty the list
            if currentPrice != None:
              pricesDict[coin].append(currentPrice)
            if len(pricesDict[coin]) == scrapesNumberPerInterval:
              currentTime = int(time.time())
              log.info("DEBUG: pricesDict = " + str(pricesDict))
              coinPrice = sum(pricesDict[coin]) / len(pricesDict[coin])
              savePriceInDatabase(log, currentTime, coin, coinPrice)
              pricesDict[coin] = []

    endTime = time.time()
    # Sleep until sleepTime seconds
    if sleepTime - (endTime - startTime) > 0:
      time.sleep(sleepTime - (endTime - startTime))

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
      log.info("Database does not exist. It will be created now.")

    # If database does not exist, the first connect will create it
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
    createTable(log)

    # The function should never end, that scrape, and write in the database
    scrape(log)

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
    log.info("Wrong number of parameters. Use: python scraper.py")
    sys.exit(99)
  else:
    mainFunction()