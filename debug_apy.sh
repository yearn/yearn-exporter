#!/usr/bin/env bash

set -e
YE_HOME=$HOME/yearn-exporter
TAG=${1:-latest}
NETWORK=${2:-ethereum}
ENV_FILE=${3:-"$HOME/.env"}

if ! [ -f "$ENV_FILE" ]; then
        echo "[!] $ENV_FILE file not found. Exiting..."
        exit 1
fi

rm -fr $YE_HOME || true
git clone https://github.com/yearn/yearn-exporter --single-branch $YE_HOME
cd $YE_HOME

source $ENV_FILE
docker pull "ghcr.io/yearn/yearn-exporter:$TAG"
DEBUG=true make apy network=$NETWORK
