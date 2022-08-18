FROM python:3.9-bullseye

RUN mkdir -p /app/yearn-exporter
WORKDIR /app/yearn-exporter

ADD requirements.txt  ./
RUN pip3 install -r requirements.txt

# This is for the accountant module
RUN brownie pm install OpenZeppelin/openzeppelin-contracts@3.2.0

ADD . /app/yearn-exporter

ENTRYPOINT ["./entrypoint.sh"]
