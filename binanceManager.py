import time
from binance.client import Client
from binance.exceptions import BinanceAPIException

def getCurrencyBalance(log, sendMessage, config, binanceClient, currency):
  i = 0
  while i <= 5:
    i += 1
    try:
      if i > 1:
        log.info("Retry number " + str(i) + " to get account balance.")
      balances = binanceClient.get_account()[u'balances']
      break
    except BinanceAPIException as e:
      message = "[ERROR API] Couldn't get balances from Binance: " + str(e)
      log.info(message)
      log.info(e)
    except Exception as e:
      message = "[ERROR] Couldn't get balances from Binance: " + str(e)
      log.info(message)
      log.info(e)
    time.sleep(5)
  if i == 11:
    message = "[ERROR] Couldn't get balances from Binance after 10 retries"
    log.info(message)
    sendMessage(log, config, message)
    return (-1)

  for currency_balance in balances:
      if currency_balance[u'asset'] == currency:
          return float(currency_balance[u'free'])
  return None

def getCurrentCoinPrice(log, sendMessage, config, binanceClient, coin):
  i = 0
  while i <= 10:
    i += 1
    if i > 1:
      log.info("Retry number " + str(i) + " for coin: '" + coin + "'")
    try:
      return float(binanceClient.get_symbol_ticker(symbol=coin)["price"])
    except BinanceAPIException as e:
      message = "[ERROR API] When getting current price: " + str(e)
      log.info(message)
      sendMessage(log, config, message)
    except Exception as e:
      message = "[ERROR] When getting current price: " + str(e)
      log.info(message)
      sendMessage(log, config, message)
    time.sleep(1)
  if i == 11:
    message = "[ERROR] Couldn't get current price from Binance after 10 retries"
    log.info(message)
    sendMessage(log, config, message)
  return None

def wait_for_order(log, sendMessage, config, binanceClient, symbol, order_id):
  log.info("Wait for order")
  i = 0
  while True:
    i += 1
    try:
      order_status = binanceClient.get_order(symbol="BTCUSDT", orderId=order_id)
      break
    except BinanceAPIException as e:
      message = "[ERROR API] When waiting for order: " + str(e)
      log.info(message)
      sendMessage(log, config, message)
      time.sleep(1)
    except Exception as e:
      message = "[ERROR] When waiting for order: " + str(e)
      log.info(message)
      sendMessage(log, config, message)
      time.sleep(1)

    if i == 10 or i == 100 or i == 500:
      message = "[ERROR] Couldn't wait for order after " + str(i) + " retries"
      log.info(message)
      sendMessage(log, config, message)

  log.info(order_status)

  i = 0
  while order_status[u'status'] != 'FILLED':
    i += 1
    try:
      order_status = self.BinanceClient.get_order(
          symbol="BTCUSDT", orderId=order_id)
    except BinanceAPIException as e:
      message = "[ERROR API] when querying if status is FILLED: " + str(e)
      log.info(message)
      sendMessage(log, config, message)
      time.sleep(1)
    except Exception as e:
      message = "[ERROR] when querying if status is FILLED: " + str(e)
      log.info(message)
      sendMessage(log, config, message)
      time.sleep(1)

    if i == 10 or i == 100 or i == 500:
      message = "[ERROR] Couldn't query if status is FILLED " + str(i) + " retries"
      log.info(message)
      sendMessage(log, config, message)

  return order_status

def buyCrypto(log, sendMessage, config, binanceClient):
  currentDollars = getCurrencyBalance(log, sendMessage, config, binanceClient, 'USDT')

  order = None
  i = 0
  while order is None:
    i += 1
    try:
      currentPrice = getCurrentCoinPrice(log, sendMessage, config, binanceClient, 'BTCUSDT')
      quantityWanted = currentDollars / currentPrice
      quantityWanted = quantityWanted - 0.01 * quantityWanted
      quantityWanted = float(str(quantityWanted).split(".")[0] + "." + str(quantityWanted).split(".")[1][:6])
      log.info("quantity = " + str(quantityWanted))
      if config["dry_run"] == "false":
        order = binanceClient.order_market_buy(symbol="BTCUSDT", quantity=(quantityWanted))
      else:
        order = "dummy"
        message = "[INFO] Running in dry-run mode. No BUY Crypto order sent"
        log.info(message)
        sendMessage(log, config, message)
    except BinanceAPIException as e:
      message = "[ERROR API] when placing BUY crypto order: " + str(e)
      log.info(message)
      sendMessage(log, config, message)
      time.sleep(1)
    except Exception as e:
      message = "[ERROR] when placing BUY crypto order: " + str(e)
      log.info(message)
      sendMessage(log, config, message)
      time.sleep(1)

    if i == 10 or i == 100 or i == 500:
      message = "[ERROR] Couldn't place BUY crypto order " + str(i) + " retries"
      log.info(message)
      sendMessage(log, config, message)

  if config["dry_run"] == "false":
    log.info("BUY crypto order placed:")
    log.info(order)

    # Binance server can take some time to save the order
    log.info("Waiting for Binance")

    stat = wait_for_order(log, sendMessage, config, binanceClient, "BTCUSDT", order[u'orderId'])

    oldDollars = currentDollars
    newDollars = getCurrencyBalance(log, sendMessage, config, binanceClient, 'USDT')
    while newDollars >= oldDollars:
        newDollars = getCurrencyBalance(log, sendMessage, config, binanceClient, 'USDT')
        time.sleep(5)

  oldDollars = currentDollars
  newCrypto = getCurrencyBalance(log, sendMessage, config, binanceClient, 'BTC')

  message = "BUY crypto successful\n"
  message += "############## BUY CRYPTO TRADE STATS #############\n"
  message += "currentPrice = " + str(currentPrice) + "\n"
  message += "oldDollars = " + str(oldDollars) + "\n"
  message += "newCrypto = " + str(newCrypto) + "\n"
  message += "####################################################"
  log.info(message)
  sendMessage(log, config, message)

def sellCrypto(log, sendMessage, config, binanceClient):
  currentCrypto = getCurrencyBalance(log, sendMessage, config, binanceClient, 'BTC')
  log.info("currentCrypto = " + str(currentCrypto))
  log.info("Try to launch a SELL Crypto order")

  order = None
  i = 0
  while order is None:
    i += 1
    try:
      currentPrice = getCurrentCoinPrice(log, sendMessage, config, binanceClient, 'BTCUSDT')
      quantityWanted = float(str(currentCrypto).split(".")[0] + "." + str(currentCrypto).split(".")[1][:6])
      log.info("quantity = " + str(quantityWanted))
      if config["dry_run"] == "false":
        order = binanceClient.order_market_sell(symbol="BTCUSDT", quantity=(quantityWanted))
      else:
        order = "dummy"
        message = "[INFO] Running in dry-run mode. No SELL Crypto order sent"
        log.info(message)
        sendMessage(log, config, message)
    except BinanceAPIException as e:
      message = "[ERROR API] when placing SELL crypto order: " + str(e)
      log.info(message)
      sendMessage(log, config, message)
      time.sleep(1)
    except Exception as e:
      message = "[ERROR] when placing SELL crypto order: " + str(e)
      log.info(message)
      sendMessage(log, config, message)
      time.sleep(1)

    if i == 10 or i == 100 or i == 500:
      message = "[ERROR] Couldn't place SELL crypto order " + str(i) + " retries"
      log.info(message)
      sendMessage(log, config, message)

  if config["dry_run"] == "false":
    log.info("SELL crypto order placed:")
    log.info(order)

    # Binance server can take some time to save the order
    log.info("Waiting for Binance")

    stat = wait_for_order(log, sendMessage, config, binanceClient, "BTCUSD", order[u'orderId'])

    oldCrypto = currentCrypto
    newCrypto = getCurrencyBalance(log, sendMessage, config, binanceClient, 'BTC')
    while newCrypto >= oldCrypto:
        newCrypto = getCurrencyBalance(log, sendMessage, config, binanceClient, 'BTC')
        time.sleep(5)

    log.info("SOLD crypto successful")

  oldCrypto = currentCrypto
  newDollars = getCurrencyBalance(log, sendMessage, config, binanceClient, 'USDT')

  message = "SELL crypto successful\n"
  message += "############## SELL CRYPTO TRADE STATS #############\n"
  message += "currentPrice = " + str(currentPrice) + "\n"
  message += "newDollars = " + str(newDollars) + "\n"
  message += "oldCrypto = " + str(oldCrypto) + "\n"
  message += "####################################################"
  log.info(message)
  sendMessage(log, config, message)
