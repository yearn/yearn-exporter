#! /bin/bash
set -e

BROWNIE_NETWORK=${BROWNIE_NETWORK:-mainnet} # default to Ethereum mainnet
EXPLORER=${EXPLORER:-$DEFAULT_EXPLORER}

# modify the network
if [[ ! -z "$WEB3_PROVIDER" ]]; then
  brownie networks modify $BROWNIE_NETWORK host=$WEB3_PROVIDER explorer=$EXPLORER
fi

if [[ $# -eq 0 ]]; then
  echo "please provide a function to run as first arg."
  exit 1
fi

echo "Running brownie for $@ on network $BROWNIE_NETWORK..."
brownie run $@ --network $BROWNIE_NETWORK -r
