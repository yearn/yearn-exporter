#!/usr/bin/env bash

set -e

WORKDIR="$HOME/yearn-exporter"
COMPOSE="$WORKDIR/docker-compose.yml"
REPOSITORY="https://github.com/yearn/yearn-exporter"

echo "[*] Starting deployment"

echo "[*] Sourcing environment"

if ! [ -f "$HOME/env" ]; then
        echo "[!] env file not found in \$HOME. Exiting..."
        exit 1
fi

source $HOME/env

if ! [ -d "$WORKDIR" ]; then
        echo "[*] Workdir does not exist, cloning now..."
        git clone $REPOSITORY "$WORKDIR"
fi

if ! [ -f "$COMPOSE" ]; then
        echo "[!] Compose file does not exist in repository. Exiting..."
        exit 1
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

echo "[*] Stopping existing service"
docker-compose -f "$COMPOSE" down --remove-orphans

echo "[*] Building and deploying..."
docker-compose -f "$COMPOSE" up --build -d

echo "[*] Finished!" 