import datetime
import sqlite3 # for database connection

# Stop scraper

database_file = "./database.db"

databaseClient = sqlite3.connect(database_file)
databaseClient.execute('''CREATE TABLE price_history_new (timestamp text, date text, coin text, price real)''')

databaseCursor = databaseClient.cursor()
databaseCursor.execute("SELECT * FROM price_history")
prices = databaseCursor.fetchall()

for price in prices:
  print(price)
  prettyDate = datetime.datetime.fromtimestamp(int(price[0])).strftime("%Y-%m-%d_%H-%M-%S")
  query = "INSERT INTO price_history_new VALUES (" + price[0] + ",'" + prettyDate + "','" + price[1] + "'," + str(price[2]) + ")"
  databaseClient.execute(query)

databaseClient.execute('''DROP TABLE price_history''')
databaseClient.execute('''CREATE TABLE price_history (timestamp text, date text, coin text, price real)''')
databaseClient.execute('''INSERT INTO price_history SELECT * FROM price_history_new''')
databaseClient.execute('''DROP TABLE price_history_new''')

databaseClient.commit()