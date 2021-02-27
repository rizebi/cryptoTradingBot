#! /usr/bin/python3
import time

# Timestamp,Open,High,Low,Close,Volume_(BTC),Volume_(Currency),Weighted_Price

#################### Tunable parameters
# The bot will not do anything if it does not have "minimumHistory" datapoints in history
minimumHistory = 5

# Sell if difference between maximum price for current trade - current price > peakIndexTreshold
# This does not respect cooldown! (if treshold is exceeded, will sell even on next datapoint)
peakIndexTreshold = 0.00005

# Buy if difference between current price and 5 datapoints ago is bigger than last5IndexTreshold
# Currently this seems not to matter
last5IndexTreshold = 0.000005
cooldownDatapoints = 2
feesPercentage = 0.001
# Mow many datapoints to aggregate (average)
aggregatedBy = 240

def runBot(inputFile):

  #################### Initializations
  currentDollars = 100
  doWeHaveCrypto = False
  history = []
  peakIndex = 0
  buyingPrice = 0
  maximumPrice = 0
  cryptoQuantity = 0
  totalGain = 0
  numberOfBuyings = 0
  actionDatapoint = 0
  currentDatapoint = 0

  data = open("/Users/eusebiu.rizescu/Data/Code/Crypto/Datasets/" + inputFile, "r")
  data = data.read().split("\n")[0:-1]

  i = 0
  while i < len(data) - aggregatedBy:
    # Aggregate by "aggregatedBy" datapoints
    suma = 0
    j = 0
    while j < aggregatedBy:
      if len(data[i].split(",")) > 1:
        current = data[i].split(",")[1]
      else:
        current = data[i]
      if current.lower() == "nan":
        i += 1
        continue
      suma += float(current)
      j += 1
      i += 1

    price = suma / aggregatedBy
    currentDatapoint += 1

    print("###############################################################################")
    print("currentPrice = " + str(price))
    history.append(price)
    if len(history) < minimumHistory:
      print("Small history. Continue")
      continue
    # Now the logic comes. To buy, to wait, to sell
    currentPrice = history[-1]
    # Calculate change in the last 5 datapoints
    #print("price5Datapoints = " + str(history[-10]))
    #average5DataPointsDiff = currentPrice - history[-5]
    average5DataPoints = sum(history[-5:])/5
    average5DataPointsDiff = currentPrice - average5DataPoints
    #print("average5DataPointsDiff = " + str(average5DataPointsDiff))
    average5DatapointsIndex = average5DataPointsDiff / average5DataPoints
    #print("average5DatapointsIndex = " + str(average5DatapointsIndex))

    # Print stats
    print("doWeHaveCrypto = " + str(doWeHaveCrypto))
    if doWeHaveCrypto == True:
      print("buyingPrice = " + str(buyingPrice))
      print("maximumPrice = " + str(maximumPrice))

    print("totalGain = " + str(totalGain))

    if doWeHaveCrypto == True:
      if currentPrice > maximumPrice:
        maximumPrice = currentPrice
      # Calculate peakIndex
      peakDiffPrice = currentPrice - maximumPrice
      aquisitionDiffPrice = currentPrice - buyingPrice
      peakIndex = peakDiffPrice / maximumPrice

      if peakIndex >= 0:
        gain = aquisitionDiffPrice * cryptoQuantity
        #totalGain += gain
        print("GOOD JOB. WE ARE MAKING MONEY. Gainings for this trade: " + str(gain) + "$.")
        continue
      else:
        # peakIndex < 0
        if peakIndex < (-1) * peakIndexTreshold:
          # We exceeded treshold, get out
          gainOrLoss = aquisitionDiffPrice * cryptoQuantity
          totalGain += gainOrLoss
          print("peakIndex = " + str(peakIndex))
          print("############################################ SELL (" + str(currentDatapoint) + "). Treshold exceeded. WE HAVE GAIN/LOSS: " + str(gainOrLoss) + "$.")
          currentDollars = cryptoQuantity * currentPrice
          currentDollars -= feesPercentage * currentDollars
          doWeHaveCrypto = False
          actionDatapoint = currentDatapoint
          cryptoQuantity = 0
          buyingPrice = 0
          continue
        else:
          # We did not exceeded treshold, maybe we will come back
          print("Treshold not exceeded. KEEP")
          continue
      if currentPrice < buyingPrice:
        if currentDatapoint - actionDatapoint < cooldownDatapoints:
          print("WAIT FOR COOLDOWN")
          continue
        gainOrLoss = aquisitionDiffPrice * cryptoQuantity
        totalGain += gainOrLoss
        print("############################################ SELL (" + str(currentDatapoint) + "). CurrentPrice < BuyingPrice. WE HAVE GAIN/LOSS: " + str(gainOrLoss) + "$.")
        currentDollars = cryptoQuantity * currentPrice
        currentDollars -= feesPercentage * currentDollars
        actionDatapoint = currentDatapoint
        doWeHaveCrypto = False
        actionDatapoint = currentDatapoint
        cryptoQuantity = 0
        buyingPrice = 0
        continue
    else:
      # We do not have crypto
      # Should we buy?
      if average5DatapointsIndex < 0:
        print("Market going down. Keep waiting.")
        continue
      else:
        if average5DatapointsIndex < last5IndexTreshold:
          print("Too little increase. Not buying. Keep waiting.")
          continue
        else:
          if currentDatapoint - actionDatapoint < cooldownDatapoints:
            print("WAIT FOR COOLDOWN")
            continue
          print("############################################ BUY (" + str(currentDatapoint) + "). Market going up.")
          doWeHaveCrypto = True
          numberOfBuyings += 1
          cryptoQuantity = currentDollars / currentPrice
          cryptoQuantity -= feesPercentage * cryptoQuantity
          buyingPrice = currentPrice
          actionDatapoint = currentDatapoint
          maximumPrice = currentPrice
          currentDollars = 0
          continue


  print("######################")
  print("######################")
  print("########STATS#########")
  print("######################")
  print("######################")
  print("totalGain = " + str(totalGain))
  print("numberOfBuyings = " + str(numberOfBuyings))


if __name__ == "__main__":
  runBot("2020.csv")
