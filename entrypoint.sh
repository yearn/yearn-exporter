#! /bin/bash
set -e

if [[ $# -eq 0 ]]; then
  echo "please provide a function to run as first arg."
  exit 1
fi

echo "Running brownie for $@ on network $BROWNIE_NETWORK..."
brownie run $@ --network $BROWNIE_NETWORK -r
