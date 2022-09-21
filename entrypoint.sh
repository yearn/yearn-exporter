#! /bin/bash
set -e

NETWORK=${NETWORK:-mainnet} # default to Ethereum mainnet
EXPLORER=${EXPLORER:-$DEFAULT_EXPLORER}

# modify the network
if [[ ! -z "$WEB3_PROVIDER" ]]; then
  brownie networks modify $NETWORK host=$WEB3_PROVIDER explorer=$EXPLORER
fi

if [[ $# -eq 0 ]]; then
  echo "please provide a function to run as first arg."
  exit 1
fi

echo "Running brownie for $@ on network $NETWORK..."
brownie run $@ --network $NETWORK -r
