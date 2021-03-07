# docker build -f Docker/Dockerfile -t ebieusebiu/crypto .

FROM python:3.8.8-buster

RUN apt -y update

COPY ./Docker/requirements.txt /requirements.txt

RUN CRYPTOGRAPHY_DONT_BUILD_RUST=1 python3 -m pip install -r /requirements.txt

COPY . /app

WORKDIR /app

CMD ["python", "bot.py"]
