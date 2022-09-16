#! /bin/bash
set -e

NETWORK=${NETWORK:-mainnet} # default to Ethereum mainnet
EXPLORER=${EXPLORER:-$DEFAULT_EXPLORER}

if [[ $NETWORK == "mainnet" ]]; then
  CHAIN_ID=1
  # some legacy cleanup
  if [[ ! -z "$WEB3_PROVIDER" ]]; then
    if [[ $(brownie networks list | grep mainnet-custom) ]]; then
      brownie networks delete mainnet-custom
    fi
  fi

elif [[ $NETWORK == "xdai-main" ]]; then
  CHAIN_ID=100

elif [[ $NETWORK == "ftm-main" ]]; then
  CHAIN_ID=250

elif [[ $NETWORK == "arbitrum-main" ]]; then
  CHAIN_ID=42161

elif [[ $NETWORK == "optimism-main" ]]; then
  CHAIN_ID=10
fi

# modify the network
if [[ ! -z "$WEB3_PROVIDER" ]]; then
  brownie networks modify $NETWORK host=$WEB3_PROVIDER chainid=$CHAIN_ID explorer=$EXPLORER
fi

if [[ $# -eq 0 ]]; then
  echo "please provide a function to run as first arg."
  exit 1
fi

echo "Running brownie for $@ on network $NETWORK..."
brownie run $@ --network $NETWORK -r
