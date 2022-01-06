#! /bin/bash
set -e

NETWORK=${NETWORK:-mainnet} # default to Ethereum mainnet

if [[ $NETWORK == "mainnet" ]]; then
  CHAIN_ID=1
  EXPLORER=${EXPLORER:-https://api.etherscan.io/api}

  if [[ ! -z "$WEB3_PROVIDER" ]]; then
    if [[ $(brownie networks list | grep mainnet-custom) ]]; then
      brownie networks delete mainnet-custom
    fi
    brownie networks modify mainnet host=$WEB3_PROVIDER chainid=$CHAIN_ID explorer=$EXPLORER
  fi

elif [[ $NETWORK == "ftm-main" ]]; then
  CHAIN_ID=250
  EXPLORER=${EXPLORER:-https://api.ftmscan.com/api}

  if [[ ! -z "$WEB3_PROVIDER" ]]; then
    brownie networks modify ftm-main host=$WEB3_PROVIDER chainid=$CHAIN_ID explorer=$EXPLORER
  fi
fi

if [[ $# -eq 0 ]]; then
  echo "please provide a function to run as first arg."
  exit 1
fi

echo "Running brownie for $@ on network $NETWORK..."
brownie run $@ --network $NETWORK -r