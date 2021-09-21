#!/usr/bin/env bash

set -e

WORKDIR="$HOME/yearn-exporter"
REPOSITORY="https://github.com/yearn/yearn-exporter"

echo "[*] Starting deployment"

echo "[*] Sourcing environment"

if ! [ -f "$HOME/.env" ]; then
        echo "[!] .env file not found in \$HOME. Exiting..."
        exit 1
fi

source $HOME/.env

if ! [ -d "$WORKDIR" ]; then
        echo "[*] Workdir does not exist, cloning now..."
        git clone $REPOSITORY "$WORKDIR"
fi

echo "[*] Checking repo state"
git -C "$WORKDIR" fetch

UPSTREAM=${1:-'@{u}'}
LOCAL=$(git -C "$WORKDIR" rev-parse @)
REMOTE=$(git -C "$WORKDIR" rev-parse "$UPSTREAM")
BASE=$(git -C "$WORKDIR"  merge-base @ "$UPSTREAM")

if [ "$LOCAL" = "$REMOTE" ]; then
        echo "[*] Up-to-date, no changes needed. Continuing..."
elif [ "$LOCAL" = "$BASE" ]; then
        echo "[*] Need to pull. Continuing..."
        git -C "$WORKDIR" pull
elif [ "$REMOTE" = "$BASE" ]; then
        echo "[!] Local changes detected. Manual maintenance needed. Exiting..."
       exit 1
else
        echo "[!] Branches are diverged. Manual maintenance needed. Exiting..."
        exit 1
fi

cd $WORKDIR
docker pull ghcr.io/yearn/yearn-exporter
echo "[*] Redeploying..."
make restart

LOGIN_RESPONSE=$(curl -X POST \
        -d '{"user":"admin","password":"admin"}' \
        -H 'Content-Type: application/json' \
        https://yearn.vision/login \
        -o /dev/null \
        -sw '%{http_code}')

if [ "$LOGIN_RESPONSE" = "200" ]; then
        echo "[*] ! SER ! Grafana admin password is not good. Please change the admin password manually with the grafana UI."
        echo "[*] Stopping existing service"
        make down
        exit 1
fi

echo "[*] Finished!"

