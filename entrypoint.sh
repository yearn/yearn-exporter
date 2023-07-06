#! /bin/bash
set -e

if [[ $# -eq 0 ]]; then
  echo "please provide a function to run as first arg."
  exit 1
fi

echo "Running brownie for $@ on network $BROWNIE_NETWORK..."

# Normal Mods
brownie run $@ --network $BROWNIE_NETWORK -r

# Memray Live Mode
#memray run --trace-python-allocators --live-remote --live-port=9999 /usr/local/bin/brownie run $@ --network $BROWNIE_NETWORK -r

# Memray Export Mode
#memray run --trace-python-allocators --output /app/yearn-exporter/memray/$BROWNIE_NETWORK/$@.bin --force /usr/local/bin/brownie run $@ --network $BROWNIE_NETWORK -r