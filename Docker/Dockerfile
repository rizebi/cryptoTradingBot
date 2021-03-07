FROM python:3.8.8-buster as base

FROM base as builder

RUN apt update

COPY requirements.txt /requirements.txt

RUN pip install --prefix=/install -r /requirements.txt

FROM base

COPY ../ /app

WORKDIR /app

CMD ["python", "bot.py"]
