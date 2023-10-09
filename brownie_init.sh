#!/bin/bash
set -e

BROWNIE_NETWORK=${BROWNIE_NETWORK:-mainnet} # default to Ethereum mainnet
EXPLORER=${EXPLORER:-$DEFAULT_EXPLORER}

# add Base to brownie's network list
if ! brownie networks list | grep Base > /dev/null; then
  brownie networks add Base base-main host=https://base.meowrpc.com chainid=8453 explorer=https://api.basescan.org/api || true
fi

# modify the network
if [[ ! -z "$WEB3_PROVIDER" ]]; then
  brownie networks modify $BROWNIE_NETWORK host=$WEB3_PROVIDER explorer=$EXPLORER
fi
