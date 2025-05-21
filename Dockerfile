FROM python:3.10.12-slim AS builder
RUN apt-get update && apt-get install -y gcc git python3-tk
RUN mkdir -p /app/yearn-exporter
WORKDIR /app/yearn-exporter
RUN pip3 install poetry
ADD pyproject.toml ./
ADD poetry.lock  ./
RUN poetry install
# TEMPORARY UNTIL NEW BROWNIE
RUN poetry run python -m pip install git+https://github.com/iamdefinitelyahuman/eth-event@03729118ee3f01118dd3f8d6e4614bb003eca67c
# 0.5.1 is faster than 0.5.0 due to parsimonius 0.10 but won't install with brownie at the moment
#RUN poetry run pip3 install "eth-abi>=5.1,<6"
ADD . /app/yearn-exporter

ENTRYPOINT ["./entrypoint.sh"]
