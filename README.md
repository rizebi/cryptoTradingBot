# Base idea
Currently, the bot works on volatile markets. The more volatile the market is, the better.

# When to buy?
If there seems to be an increase in the price, buy.

Parameters:
- aggregated_by = 30
- buy_lookback_intervals = 4
- buy_lookback_intervals_index_treshold = 0.00005 (this coul be irrelevant. 0 the best for running time)

Algorithm:
 - averagePriceLast30Minutes = last 30 prices / 30
 - averagePriceLast120Minutes = last 120 prices / 120 (120 = aggregated_by * buy_lookback_intervals)
 - if (averagePriceLast30Minutes - averagePriceLast120Minutes) / averagePriceLast120Minutes > buy_lookback_intervals_index_treshold
    - BUY
 - else
    - WAIT, market going down

# When to sell?
If we see a declination of price, sell.

If we have crypto, we will calculate the maximum price since the buying. Also, normalize the maximum (take the nearest 30 points near him and make average).

Parameters:
- peak_index_treshold=0.0005
- peak_index_treshold_ignore_cooldown=0.009
- cooldown_minutes_sell_peak=120

Algorithm:
- peakIndex = (averagePriceLast30Minutes - maximumNormalized) / maximumNormalized
- if peakIndex > 0
  - STAY. We are making money
- else
  - if peakIndex < peak_index_treshold_ignore_cooldown
    - SELL, big treshold exceeded
  - if peakIndex < peak_index_treshold
    - if (made the buy in the last 120 minute)
      - WAIT for cooldown. Maybe false alarm
    - else
      - SELL. Peak treshold exceeded
  - else
    - WAIT. Treshold not exceeded.

# Architecture
![alt text](https://github.com/rizebi/myprecious/blob/master/Diagram.png?raw=true)


Check the Diagram.png file if not displayed correctly. The minimum parts are:
- scraper
  - it scrapes each minute for price data
- database
- bot
  - it makes the trades

# Construct configuration.cfg
- Start from .configration-sample.cfg. The best parameters found until now are there

- Add Binance api_key and api_secret_key

- Add Telegram bot_chat_id and bot_token:
    - How to create Telegram bot:
        - Create bot (tutorial on the web, basically download app, search for user: BotFather, and use command /newbot), and keep the TOKEN
        - Send a message to the bot
        - Add bot in a group
        - Send message to group
        - https://api.telegram.org/bot<TOKEN>/getUpdates
        - Get the chatID ("id" value of "chat" object)

# Deployment

###On host
- Ensure python packages are present:
  - CRYPTOGRAPHY_DONT_BUILD_RUST=1 python3 -m pip install -r requirements.txt
- Launch scraper
- Launch bot

###In docker

The docker image is the same for all components: ebieusebiu/crypto
The image is for arm (raspberry). If the host is ARM, just run:
  - docker-compose up -d
  
Otherwise, build the image:
  - docker build -f Docker/Dockerfile -t my-image .
  - update docker-compose.yaml with the new image
  - docker-compose up -d