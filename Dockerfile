FROM python:3.8-buster

ENV LANG=C.UTF-8 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=true

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN mkdir -p /app/yearn-exporter \
    && mkdir -p /app/logs \
    && chmod 755 /app \
    && pip3 install eth-brownie prometheus_client dataclasses cachetools --no-cache-dir
    

COPY . /app/yearn-exporter
WORKDIR /app/yearn-exporter

ENTRYPOINT ["./entrypoint.sh"]
