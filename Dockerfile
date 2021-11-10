FROM python:3.8-buster

RUN mkdir -p /app/yearn-exporter
WORKDIR /app/yearn-exporter

RUN apt-get update
RUN apt-get install -y build-essential odbc-postgresql python3-dev unixodbc-dev

ADD requirements.txt  ./
RUN pip3 install -r requirements.txt

ADD . /app/yearn-exporter

ENTRYPOINT ["./entrypoint.sh"]
