FROM python:3.10.12-slim as builder
RUN apt-get update && \
    apt-get install -y gcc git
ADD requirements.txt  ./
RUN mkdir -p /install
RUN pip3 install --prefix=/install -r requirements.txt
# 0.5.1 is faster than 0.5.0 due to parsimonius 0.10 but won't install with brownie at the moment
RUN pip3 install --prefix=/install "eth-abi>=5.1,<6"

FROM python:3.10.12-slim
COPY --from=builder /install /usr/local
RUN apt-get update
RUN apt-get install python3-tk -y
RUN mkdir -p /app/yearn-exporter
WORKDIR /app/yearn-exporter
ADD . /app/yearn-exporter

ENTRYPOINT ["./entrypoint.sh"]
