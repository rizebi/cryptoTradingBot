import time
from binance.client import Client
from binance.exceptions import BinanceAPIException

def getCurrencyBalance(config, currency):
  log = config["log"]
  binanceClient = config["binanceClient"]
  sendMessage = config["sendMessage"]
  if config["dry_run"] == "false":
    log.info("Get balance for: " + currency)
  i = 0
  while i <= 10:
    i += 1
    try:
      if i > 1:
        log.info("Retry number " + str(i) + " to get account balance.")
      if config["dry_run"] == "false":
        balances = binanceClient.get_account()[u'balances']
      else:
        if currency == "USDT":
          returnValue = -12
        else:
          returnValue = -13
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
    sendMessage(config, message)
    returnValue = -10000

  if config["dry_run"] == "false":
    for currency_balance in balances:
        if currency_balance[u'asset'] == currency:
            returnValue = float(currency_balance[u'free'])
  if config["dry_run"] == "false":
    log.info("Got: " + str('{:.10f}'.format(returnValue))  + " " + currency)
  return returnValue

def getCurrentCoinPrice(config, coin):
  log = config["log"]
  binanceClient = config["binanceClient"]
  sendMessage = config["sendMessage"]
  i = 0
  while i <= 10:
    i += 1
    if i > 1:
      log.info("Retry number " + str(i) + " for coin: '" + coin + "'")
    try:
      if config["dry_run"] == "false":
        return float(binanceClient.get_symbol_ticker(symbol=coin)["price"])
      else:
        return -15
    except BinanceAPIException as e:
      message = "[ERROR API] When getting current price: " + str(e)
      log.info(message)
      sendMessage(config, message)
    except Exception as e:
      message = "[ERROR] When getting current price: " + str(e)
      log.info(message)
      sendMessage(config, message)
    time.sleep(1)
  if i == 11:
    message = "[ERROR] Couldn't get current price from Binance after 10 retries"
    log.info(message)
    sendMessage(config, message)
  return None

def getTradeRealPrice(config, order_status):
  log = config["log"]
  binanceClient = config["binanceClient"]
  sendMessage = config["sendMessage"]
  try:
    return float(order_status["cummulativeQuoteQty"]) / float(order_status["executedQty"])
  except:
    message = "[ERROR] Different order_status othat expected: " + str(order_status)
    log.info(message)
    sendMessage(config, message)
    return -1

def wait_for_order(config, symbol, order_id):
  log = config["log"]
  binanceClient = config["binanceClient"]
  sendMessage = config["sendMessage"]
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
      sendMessage(config, message)
      time.sleep(1)
    except Exception as e:
      message = "[ERROR] When waiting for order: " + str(e)
      log.info(message)
      sendMessage(config, message)
      time.sleep(5)

    if i == 10 or i == 100 or i == 500:
      message = "[ERROR] Couldn't wait for order after " + str(i) + " retries"
      log.info(message)
      sendMessage(config, message)

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
      sendMessage(config, message)
      time.sleep(1)
    except Exception as e:
      message = "[ERROR] when querying if status is FILLED: " + str(e)
      log.info(message)
      sendMessage(config, message)
      time.sleep(5)

    if i == 10 or i == 100 or i == 500:
      message = "[ERROR] Couldn't query if status is FILLED " + str(i) + " retries"
      log.info(message)
      sendMessage(config, message)

  return order_status

def buyCrypto(config):
  log = config["log"]
  binanceClient = config["binanceClient"]
  sendMessage = config["sendMessage"]
  currentDollars = getCurrencyBalance(config, 'USDT')

  order = None
  i = 0
  while order is None:
    i += 1
    try:
      currentPrice = getCurrentCoinPrice(config, 'BTCUSDT')
      quantityWanted = currentDollars / currentPrice
      quantityWanted = quantityWanted - 0.01 * quantityWanted
      if "." in str(quantityWanted):
        # Remove too many decimals
        quantityWanted = float(str(quantityWanted).split(".")[0] + "." + str(quantityWanted).split(".")[1][:6])
      log.info("quantity = " + str(quantityWanted))
      if config["dry_run"] == "false":
        order = binanceClient.order_market_buy(symbol="BTCUSDT", quantity=(quantityWanted))
      else:
        order = "dummy"
        message = "[INFO] Running in dry_run mode. No BUY Crypto order sent"
        log.info(message)
        sendMessage(config, message)
    except BinanceAPIException as e:
      message = "[ERROR API] when placing BUY crypto order: " + str(e)
      log.info(message)
      sendMessage(config, message)
      time.sleep(3)
    except Exception as e:
      message = "[ERROR] when placing BUY crypto order: " + str(e)
      log.info(message)
      sendMessage(config, message)
      time.sleep(3)

    if i == 10 or i == 100 or i == 500:
      message = "[ERROR] Couldn't place BUY crypto order " + str(i) + " retries"
      log.info(message)
      sendMessage(config, message)

  if config["dry_run"] == "false":
    log.info("BUY crypto order placed:")
    log.info(order)

    # Binance server can take some time to save the order
    log.info("Waiting for Binance")
    time.sleep(3)
    order_status = wait_for_order(config, "BTCUSDT", order[u'orderId'])

    oldDollars = currentDollars
    newDollars = getCurrencyBalance(config, 'USDT')
    while newDollars >= oldDollars:
        newDollars = getCurrencyBalance(config, 'USDT')
        time.sleep(5)
    tradeRealPrice = getTradeRealPrice(config, order_status)
  else:
    tradeRealPrice = -10

  oldDollars = currentDollars
  newCrypto = getCurrencyBalance(config, 'BTC')

  if config["dry_run"] == "false":
    message = "[BUY Crypto successful]\n"
    message += "Summary\n"
    message += "tradeRealPrice = " + str(tradeRealPrice) + "\n"
    message += "oldDollars = " + str(oldDollars) + "\n"
    message += "newCrypto = " + str(newCrypto) + "\n"
    log.info(message)
    sendMessage(config, message)
  return tradeRealPrice

def sellCrypto(config):
  log = config["log"]
  binanceClient = config["binanceClient"]
  sendMessage = config["sendMessage"]
  currentCrypto = getCurrencyBalance(config, 'BTC')
  log.info("currentCrypto = " + str(currentCrypto))
  log.info("Try to launch a SELL Crypto order")

  order = None
  i = 0
  while order is None:
    i += 1
    try:
      currentPrice = getCurrentCoinPrice(config, 'BTCUSDT')
      if "." in str(currentCrypto):
        # Remove too many decimals
        quantityWanted = float(str(currentCrypto).split(".")[0] + "." + str(currentCrypto).split(".")[1][:6])
      else:
        quantityWanted = currentCrypto
      log.info("quantity = " + str(quantityWanted))
      if config["dry_run"] == "false":
        order = binanceClient.order_market_sell(symbol="BTCUSDT", quantity=(quantityWanted))
      else:
        order = "dummy"
        message = "[INFO] Running in dry_run mode. No SELL Crypto order sent"
        log.info(message)
        sendMessage(config, message)
    except BinanceAPIException as e:
      message = "[ERROR API] when placing SELL crypto order: " + str(e)
      log.info(message)
      sendMessage(config, message)
      time.sleep(3)
    except Exception as e:
      message = "[ERROR] when placing SELL crypto order: " + str(e)
      log.info(message)
      sendMessage(config, message)
      time.sleep(3)

    if i == 10 or i == 100 or i == 500:
      message = "[ERROR] Couldn't place SELL crypto order " + str(i) + " retries"
      log.info(message)
      sendMessage(config, message)

  if config["dry_run"] == "false":
    log.info("SELL crypto order placed:")
    log.info(order)

    # Binance server can take some time to save the order
    log.info("Waiting for Binance")
    time.sleep(3)
    order_status = wait_for_order(config, "BTCUSD", order[u'orderId'])

    oldCrypto = currentCrypto
    newCrypto = getCurrencyBalance(config, 'BTC')
    while newCrypto >= oldCrypto:
        newCrypto = getCurrencyBalance(config, 'BTC')
        time.sleep(5)

    tradeRealPrice = getTradeRealPrice(config, order_status)
  else:
    tradeRealPrice = -11

  oldCrypto = currentCrypto
  newDollars = getCurrencyBalance(config, 'USDT')

  if config["dry_run"] == "false":
    message = "[SELL Crypto successful]\n"
    message += "Summary\n"
    message += "tradeRealPrice = " + str(tradeRealPrice) + "\n"
    message += "newDollars = " + str(newDollars) + "\n"
    message += "oldCrypto = " + str(oldCrypto) + "\n"
    log.info(message)
    sendMessage(config, message)
  return tradeRealPrice