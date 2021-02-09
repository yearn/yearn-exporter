#! /bin/bash
set -e

NETWORK="mainnet" # default to Mainnet (Infura)
EXPLORER="https://api.etherscan.io/api"

if [[ ! -z "${ALCHEMY_URL}" ]]; then
  if [[ ! $(brownie networks list | grep mainnet-alchemy) ]]; then
    brownie networks add Ethereum mainnet-alchemy host=$ALCHEMY_URL chainid=1 explorer=$EXPLORER
  fi
  NETWORK="mainnet-alchemy"
fi

if [[ -z $1 ]]; then
  echo "please provide a function to run as first arg."
  exit 1
fi

echo "Running brownie for $1 on network $NETWORK..."
brownie run yearn $1 --network $NETWORK
