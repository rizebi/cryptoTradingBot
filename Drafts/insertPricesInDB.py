#! /usr/bin/python3
import os
import sys
import time # for sleep
import sqlite3 # for database connection
import datetime

pricesFile = "./Datasets/fullPerMinute.csv"
databaseFile = "./Datasets/databaseFullPerMinute.db"
coin = "BTCUSDT"

databaseClient = sqlite3.connect(databaseFile)
databaseCursor = databaseClient.cursor()

# Create price_history table
databaseCursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = databaseCursor.fetchall()
if ("price_history",) in tables:
  databaseClient.execute('''DELETE FROM price_history''')
else:
  databaseClient.execute('''CREATE TABLE price_history
               (timestamp text, date text, coin text, price real)''')

# Create trade_history table
databaseCursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = databaseCursor.fetchall()
if ("trade_history",) in tables:
  databaseClient.execute('''DELETE FROM trade_history''')
else:
  databaseClient.execute('''CREATE TABLE trade_history
             (timestamp text, date text, coin text, action text, tradeRealPrice real, tradeAggregatedPrice real, currentDollars real, cryptoQuantity real, gainOrLoss real)''')

databaseClient.commit()

data = open(pricesFile, "r")
data = data.read().split("\n")[0:-1]


# Sanitize data
dataPoints = []
for element in data:
  if "nan" in element.lower():
    continue
  dataPoints.append((int(element.split(",")[0]), float(element.split(",")[1])))

# Reverse if in file the prices are in descending order of timestamp
#dataPoints.reverse()

for dataPoint in dataPoints:
  timestamp = dataPoint[0]
  price = dataPoint[1]
  prettyDate = datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d_%H-%M-%S")
  query = "INSERT INTO price_history VALUES (" + str(timestamp) + ",'" + prettyDate + "','" + coin + "'," + str(price) + ")"
  databaseCursor.execute(query)

databaseClient.commit()