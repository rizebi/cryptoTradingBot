#! /usr/bin/python3
import time

# Timestamp,Open,High,Low,Close,Volume_(BTC),Volume_(Currency),Weighted_Price

#################### Tunable parameters
# Sell if difference between maximum price for current trade - current price > peakIndexTreshold
# This does not respect cooldown! (if treshold is exceeded, will sell even on next datapoint)
peakIndexTreshold = 0.00005

# Buy if difference between current price and lookBackIntevals datapoints ago is bigger than lastLookBackIntevalsIndexTreshold
# Currently this seems not to matter
lastLookBackIntevalsIndexTreshold = 0.000005
cooldownDatapoints = 2
feesPercentage = 0.001

# Mow many datapoints to aggregate (average)
aggregatedBy = 240
# The bot will buy if  the current price is above average for lookBackIntevals
# These are big intervals. Aggregated ones
lookBackIntevals = 5

def runBot(inputFile):

  #################### Initializations
  initialDollars = 100
  currentDollars = initialDollars
  doWeHaveCrypto = False
  history = []
  peakIndex = 0
  buyingPrice = 0
  maximumPrice = 0
  cryptoQuantity = 0
  totalFeesPaid = 0
  numberOfBuyings = 0
  actionDatapoint = 0
  currentDatapoint = 0
  # action, currentPrice, currentDollars, cryptoQuantity, gainOrLoss
  tradesHistory = []

  # Read data
  data = open("/Users/eusebiu.rizescu/Data/Code/Crypto/Datasets/" + inputFile, "r")
  data = data.read().split("\n")[0:-1]

  # Sanitize data
  dataPoints = []
  for element in data:
    if "nan" in element.lower():
      continue
    if len(element.split(",")) > 1:
      dataPoints.append(float(element.split(",")[1]))
    else:
      dataPoints.append(float(element))

  while currentDatapoint < len(dataPoints):
    print("[Datapoint " + str(currentDatapoint) + "] ######################################################")
    history = []
    if currentDatapoint < lookBackIntevals * aggregatedBy - 1:
      print("Too few data to aggregate")
      currentDatapoint += 1
      continue
    i = currentDatapoint - (lookBackIntevals * aggregatedBy) + 1
    while i <= currentDatapoint:
      suma = 0
      j = 0
      while j < aggregatedBy:
        suma += dataPoints[i]
        i += 1
        j += 1
      history.append(suma/aggregatedBy)
    currentDatapoint += 1
    # Now the logic comes. To buy, to wait, to sell
    currentPrice = history[-1]
    print("currentPrice = " + str(currentPrice))

    # Calculate change in the last lookBackIntevals datapoints
    #print("priceLookBackIntevalsDatapoints = " + str(history[-10]))
    #averageLookBackIntevalsDataPointsDiff = currentPrice - history[(-1) * LookBackIntevals]
    averageLookBackIntevalsDataPoints = sum(history[(-1) * lookBackIntevals:])/lookBackIntevals
    averageLookBackIntevalsDataPointsDiff = currentPrice - averageLookBackIntevalsDataPoints
    #print("averageLookBackIntevalsDataPointsDiff = " + str(averageLookBackIntevalsDataPointsDiff))
    averageLookBackIntevalsDatapointsIndex = averageLookBackIntevalsDataPointsDiff / averageLookBackIntevalsDataPoints
    #print("averageLookBackIntevalsDatapointsIndex = " + str(averageLookBackIntevalsDatapointsIndex))

    # Print stats
    print("doWeHaveCrypto = " + str(doWeHaveCrypto))
    if doWeHaveCrypto == True:
      print("buyingPrice = " + str(buyingPrice))
      print("maximumPrice = " + str(maximumPrice))

    if doWeHaveCrypto == True:
      if currentPrice > maximumPrice:
        maximumPrice = currentPrice
      # Calculate peakIndex
      peakDiffPrice = currentPrice - maximumPrice
      aquisitionDiffPrice = currentPrice - buyingPrice
      peakIndex = peakDiffPrice / maximumPrice

      if peakIndex >= 0:
        gain = aquisitionDiffPrice * cryptoQuantity
        print("GOOD JOB. WE ARE MAKING MONEY. Gainings for this trade (no fees calculated): " + str(gain) + "$.")
        continue
      else:
        # peakIndex < 0
        if peakIndex < (-1) * peakIndexTreshold:
          # We exceeded treshold, get out
          # SELL
          currentDollars = cryptoQuantity * currentPrice
          # FEES
          currentFee = feesPercentage * currentDollars
          totalFeesPaid += feesPercentage * currentDollars
          print("currentFee = " + str(currentFee))
          print("currentDollars BEFORE FEES = " + str(currentDollars))
          currentDollars -= feesPercentage * currentDollars
          print("currentDollars AFTER FEES = " + str(currentDollars))
          gainOrLoss = (currentPrice - buyingPrice) * cryptoQuantity
          gainOrLoss -= currentFee
          print("gainOrLoss = " + str(gainOrLoss))
          print("currentDollars = " + str(currentDollars))
          print("############################################ SELL (" + str(currentDatapoint) + "). Treshold exceeded. WE HAVE GAIN/LOSS: " + str(gainOrLoss) + "$.")
          doWeHaveCrypto = False
          actionDatapoint = currentDatapoint
          cryptoQuantity = 0
          buyingPrice = 0
          tradesHistory.append(("SELL", currentDatapoint, currentPrice, currentDollars, cryptoQuantity, gainOrLoss))
          continue
        else:
          # We did not exceeded treshold, maybe we will come back
          print("Treshold not exceeded. KEEP")
          continue
      if currentPrice < buyingPrice:
        if currentDatapoint - actionDatapoint < cooldownDatapoints * aggregatedBy:
          print("WAIT FOR COOLDOWN. No selling.")
          continue
        # SELL
        currentDollars = cryptoQuantity * currentPrice
        # FEES
        currentFee = feesPercentage * currentDollars
        totalFeesPaid += feesPercentage * currentDollars
        print("currentFee = " + str(currentFee))
        print("currentDollars BEFORE FEES = " + str(currentDollars))
        currentDollars -= feesPercentage * currentDollars
        print("currentDollars AFTER FEES = " + str(currentDollars))
        gainOrLoss = (currentPrice - buyingPrice) * cryptoQuantity
        gainOrLoss -= currentFee
        print("gainOrLoss = " + str(gainOrLoss))
        print("currentDollars = " + str(currentDollars))
        print("############################################ SELL (" + str(currentDatapoint) + "). CurrentPrice < BuyingPrice. WE HAVE GAIN/LOSS: " + str(gainOrLoss) + "$.")
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
      if averageLookBackIntevalsDatapointsIndex < 0:
        print("Market going down. Keep waiting.")
        continue
      else:
        if averageLookBackIntevalsDatapointsIndex < lastLookBackIntevalsIndexTreshold:
          print("Too little increase. Not buying. Keep waiting.")
          continue
        else:
          if currentDatapoint - actionDatapoint < cooldownDatapoints * aggregatedBy:
            print("WAIT FOR COOLDOWN. No buying.")
            continue
          # BUY
          # FEES
          currentFee = feesPercentage * currentDollars
          totalFeesPaid += feesPercentage * currentDollars
          print("currentFee = " + str(currentFee))
          print("currentDollars BEFORE FEES = " + str(currentDollars))
          currentDollars -= feesPercentage * currentDollars
          print("currentDollars AFTER FEES = " + str(currentDollars))
          gainOrLoss = (-1) * currentFee
          cryptoQuantity = currentDollars / currentPrice
          print("cryptoQuantity = " + str(cryptoQuantity))
          print("############################################ BUY (" + str(currentDatapoint) + "). Market going up.")
          doWeHaveCrypto = True
          numberOfBuyings += 1
          buyingPrice = currentPrice
          actionDatapoint = currentDatapoint
          maximumPrice = currentPrice
          currentDollars = 0
          tradesHistory.append(("BUY", currentDatapoint, currentPrice, currentDollars, cryptoQuantity, gainOrLoss))
          continue


  print("######################")
  print("######################")
  print("########STATS#########")
  print("######################")
  print("######################")
  print("initialDollars = " + str(initialDollars))

  print("Trades History:")
  print("action, currentPrice, currentDollars, cryptoQuantity, gainOrLoss")
  totalGainOrLoss = 0
  for trade in tradesHistory:
    totalGainOrLoss += trade[5]
    print (trade)
  print("######################")
  print("Summary:")
  print("totalGainOrLoss = " + str(totalGainOrLoss))
  print("totalFeesPaid = " + str(totalFeesPaid))
  print("numberOfBuyings = " + str(numberOfBuyings))
  print("doWeHaveCrypto = " + str(doWeHaveCrypto))
  if doWeHaveCrypto == True:
    print("buyingPrice = " + str(buyingPrice))
    print("cryptoQuantity = " + str(cryptoQuantity))
    print("Earnings/Losses = " + str(cryptoQuantity * currentPrice - initialDollars))
  else:
    print("currentDollars = " + str(currentDollars))
    print("Earnings/Losses = " + str(currentDollars - initialDollars))


if __name__ == "__main__":
  runBot("binance_inverted.csv")
