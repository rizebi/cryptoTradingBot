#################### Tunable parameters
Sell if difference between maximum price for current trade - current price > peakIndexTreshold
This does not respect cooldown! (if treshold is exceeded, will sell even on next datapoint)

peakIndexTreshold = 0.00005

Buy if difference between current price and lookBackIntervals datapoints ago is bigger than lastlookBackIntervalsIndexTreshold
Currently this seems not to matter

lastlookBackIntervalsIndexTreshold = 0.000005

cooldownDatapoints = 2

feesPercentage = 0.001

How many datapoints to aggregate (average)
aggregatedBy = 240
The bot will buy if  the current price is above average for lookBackIntervals
These are big intervals. Aggregated ones

lookBackIntervals = 5
