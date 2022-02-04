FROM --platform=linux/amd64 python:3.9-bullseye

RUN mkdir -p /app/yearn-exporter
WORKDIR /app/yearn-exporter

ADD requirements.txt  ./
RUN pip3 install -r requirements.txt

ADD . /app/yearn-exporter

ENTRYPOINT ["./entrypoint.sh"]
