#! /usr/bin/python3
# Timestamp,Open,High,Low,Close,Volume_(BTC),Volume_(Currency),Weighted_Price

complete = open("./Datasets/complete.csv", "r")
complete = complete.read()


dayToGet = "157783674"
dayAfterToGet = "160937262"
name = "202000"

complete = complete.split(dayToGet, 1)[1].split(dayAfterToGet, 1)[0]

day = open("./Datasets/" + name + ".csv", "a")
day.write(dayToGet + complete)
day.close()
