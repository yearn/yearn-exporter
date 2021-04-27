FROM python:3.8-buster

RUN mkdir -p /app/yearn-exporter
WORKDIR /app/yearn-exporter

ADD requirements.txt  ./
RUN pip3 install -r requirements.txt

ADD . /app/yearn-exporter

ENTRYPOINT ["./entrypoint.sh"]
