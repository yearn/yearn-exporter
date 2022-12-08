FROM python:3.9.15-slim as builder
RUN apt-get update && \
    apt-get install -y gcc git
ADD requirements.txt  ./
RUN mkdir -p /install
RUN pip3 install --prefix=/install -r requirements.txt

FROM python:3.9.15-slim
COPY --from=builder /install /usr/local
RUN mkdir -p /app/yearn-exporter
WORKDIR /app/yearn-exporter
ADD . /app/yearn-exporter

ENTRYPOINT ["./entrypoint.sh"]
