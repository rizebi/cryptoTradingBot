# What is this?
This is a Crypto trading bot, with intergration with Binance.
It needs more work and strategy enhancements to produce any profits.
At a very high level, it scrapes the prices every X 10 seconds, store them in a local database, and then tries to anticipate the change in price in order buy/sell/hold.
Unfortunately this is the million dollars idea that cannot be solved without complex maths, and even with that, the profit is not 100% sure.

This was more of an excercise of coding / designing / deploying.

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

# Step-by-Step in Docker on EC2 instance
1) Create new instance, Amazon Linux 2

2) Allow ports 20, 80, 81 to the world. Or better, allow them only to your home IP (and when it changes, update the security of machine accordingly)

3) ssh -i key ec2-user@IP

4) Install dependencies

yum install -y python3 telnet docker git

curl -L https://github.com/docker/compose/releases/download/1.22.0/docker-compose-$(uname -s)-$(uname -m) -o /usr/bin/docker-compose

chmod +x /usr/bin/docker-compose

systemctl enable docker; systemctl start docker

5) Install and configure Git

add ssh key to github

vim /root/.ssh/github.priv

chmod 400 /root/.ssh/github.priv

vim /root/.ssh/config

Host github.com
 User git
 HostName github.com
 IdentityFile ~/.ssh/github.priv

6) Get code

mkdir /docker; cd /docker

git clone git@github.com:rizebi/myprecious.git

ln -sfn /docker/myprecious/Docker/x86/docker-compose.yaml /docker/docker-compose.yaml

7) Add config

vim /docker/myprecious/configuration.cfg

8) cd /docker; docker-compose up -d
