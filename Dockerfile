FROM python:3.10.12-slim as builder
RUN apt-get update && apt-get install -y gcc git python3-tk
RUN mkdir -p /app/yearn-exporter
WORKDIR /app/yearn-exporter
RUN pip3 install poetry
ADD pyproject.toml ./
ADD poetry.lock  ./
RUN poetry install
# 0.5.1 is faster than 0.5.0 due to parsimonius 0.10 but won't install with brownie at the moment
RUN poetry run pip3 install "eth-abi>=5.1,<6"
ADD . /app/yearn-exporter

ENTRYPOINT ["./entrypoint.sh"]
