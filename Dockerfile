FROM python:3.9.6-slim-buster

WORKDIR /usr/app

EXPOSE 5000

COPY requirements.txt .

RUN pip install -U pip
RUN pip install -r requirements.txt

COPY ./nvsvocprez ./nvsvocprez

