FROM python:3.8-buster

RUN pip3 install eth-brownie prometheus_client dataclasses cachetools
RUN mkdir -p /app/yearn-exporter
ADD . /app/yearn-exporter
WORKDIR /app/yearn-exporter

ENTRYPOINT ["./entrypoint.sh"]
