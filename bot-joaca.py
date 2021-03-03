

#################### Initializations
peakIndex = 0
numberOfBuyings = 0
# action, currentPrice, currentDollars, cryptoQuantity, gainOrLoss
tradesHistory = []


while currentDatapoint < len(dataPoints):




    if currentPrice < buyingPrice:
      if currentDatapoint - actionDatapoint < cooldownDatapoints * aggregatedBy:
        log.info("WAIT FOR COOLDOWN. No selling.")
        continue
      # SELL
      currentDollars = cryptoQuantity * currentPrice
      log.info("currentDollars = " + str(currentDollars))
      log.info("############################################ SELL (" + str(currentDatapoint) + "). CurrentPrice < BuyingPrice. WE HAVE GAIN/LOSS: " + str(gainOrLoss) + "$.")
      actionDatapoint = currentDatapoint
      doWeHaveCrypto = False
      actionDatapoint = currentDatapoint
      cryptoQuantity = 0
      buyingPrice = 0
      tradesHistory.append(("SELL", currentDatapoint, currentPrice, currentDollars, cryptoQuantity, gainOrLoss))
      continue
  else:
    # We do not have crypto
    # Should we buy?
    if averagelookBackIntervalsDatapointsIndex < 0:
      log.info("Market going down. Keep waiting.")
      continue
    else:
      if averagelookBackIntervalsDatapointsIndex < lastlookBackIntervalsIndexTreshold:
        log.info("Too little increase. Not buying. Keep waiting.")
        continue
      else:
        if currentDatapoint - actionDatapoint < cooldownDatapoints * aggregatedBy:
          log.info("WAIT FOR COOLDOWN. No buying.")
          continue
        # BUY
        log.info("############################################ BUY (" + str(currentDatapoint) + "). Market going up.")
        doWeHaveCrypto = True
        numberOfBuyings += 1
        buyingPrice = currentPrice
        actionDatapoint = currentDatapoint
        maximumPrice = currentPrice
        currentDollars = 0
        tradesHistory.append(("BUY", currentDatapoint, currentPrice, currentDollars, cryptoQuantity, gainOrLoss))
        continue


log.info("######################")
log.info("######################")
log.info("########STATS#########")
log.info("######################")
log.info("######################")
log.info("initialDollars = " + str(initialDollars))

log.info("Trades History:")
log.info("action, currentPrice, currentDollars, cryptoQuantity, gainOrLoss")
for trade in tradesHistory:
  log.info (trade)
log.info("######################")
log.info("Summary:")
log.info("numberOfBuyings = " + str(numberOfBuyings))
log.info("doWeHaveCrypto = " + str(doWeHaveCrypto))
if doWeHaveCrypto == True:
  log.info("buyingPrice = " + str(buyingPrice))
  log.info("cryptoQuantity = " + str(cryptoQuantity))
  log.info("Earnings/Losses = " + str(cryptoQuantity * currentPrice - initialDollars))
else:
  log.info("currentDollars = " + str(currentDollars))
  log.info("Earnings/Losses = " + str(currentDollars - initialDollars))
