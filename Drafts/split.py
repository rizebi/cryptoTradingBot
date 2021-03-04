#! /usr/bin/python3
# Timestamp,Open,High,Low,Close,Volume_(BTC),Volume_(Currency),Weighted_Price

complete = open("./Datasets/complete.csv", "r")
complete = complete.read()


dayToGet = "15147648"
dayAfterToGet = "15463008"
name = "2018"

complete = complete.split(dayToGet, 1)[1].split(dayAfterToGet, 1)[0]

day = open("./Datasets/" + name + ".csv", "a")
day.write(dayToGet + complete)
day.close()
