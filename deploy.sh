#!/usr/bin/env bash

set -e
YE_HOME=$HOME/yearn-exporter
TAG=${1:-latest}
ENV_FILE=${2:-"$HOME/.env"}
UP_CMD=$3
BASE_URL=$4

if [[ -z "${UP_CMD}" ]]; then
        echo "[!] UP_CMD not specified. Exiting..."
        exit 1
fi

echo "[*] Starting deployment"
echo "[*] Sourcing environment"
if ! [ -f "$ENV_FILE" ]; then
        echo "[!] $ENV_FILE file not found. Exiting..."
        exit 1
fi

rm -fr $YE_HOME || true
git clone https://github.com/yearn/yearn-exporter --single-branch $YE_HOME
cd $YE_HOME

source $ENV_FILE
docker pull "ghcr.io/yearn/yearn-exporter:$TAG"
make down
make $UP_CMD with_logs=false || true

if [[ ! -z "${BASE_URL}" ]]; then
        LOGIN_RESPONSE=$(curl -X POST \
                -d '{"user":"admin","password":"admin"}' \
                -H 'Content-Type: application/json' \
                $BASE_URL/login \
                -o /dev/null \
                -sw '%{http_code}')

        if [ "$LOGIN_RESPONSE" = "200" ]; then
                echo "[*] ! SER ! Grafana admin password is not good. Please change the admin password manually with the grafana UI."
                echo "[*] Stopping existing service"
                make down
                exit 1
        fi
fi

echo "[*] Finished!"
