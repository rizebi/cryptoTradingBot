FROM python:3.8.8-buster as base

FROM base as builder

RUN apt update; apt install -y rustc

RUN mkdir /install

WORKDIR /install

COPY requirements.txt /requirements.txt

RUN pip install --prefix=/install -r /requirements.txt

FROM base

COPY --from=builder /install /usr/local

COPY . /app

WORKDIR /app

CMD ["python", "crypto_trading.py"]
