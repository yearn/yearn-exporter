FROM python:3.10.12-slim as builder
RUN apt-get update && \
    apt-get install -y gcc git
ADD requirements.txt  ./
RUN mkdir -p /install
# NOTE: We have to do this to force pyyaml to install
RUN pip3 install --prefix=/install "Cython<3.0" "pyyaml==5.4.1" --no-build-isolation
RUN pip3 install --prefix=/install -r requirements.txt

FROM python:3.10.12-slim
COPY --from=builder /install /usr/local
RUN apt-get update
RUN apt-get install python3-tk -y
RUN mkdir -p /app/yearn-exporter
WORKDIR /app/yearn-exporter
ADD . /app/yearn-exporter

ENTRYPOINT ["./entrypoint.sh"]
