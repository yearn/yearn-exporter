#! /bin/bash
set -e

BROWNIE_NETWORK=${BROWNIE_NETWORK:-mainnet} # default to Ethereum mainnet
EXPLORER=${EXPLORER:-$DEFAULT_EXPLORER}
MEMORY_PER_WORKER=${MEMORY_PER_WORKER:-8GB}

# modify the network
if [[ ! -z "$WEB3_PROVIDER" ]]; then
  brownie networks modify $BROWNIE_NETWORK host=$WEB3_PROVIDER explorer=$EXPLORER
fi

echo "Starting worker on network $BROWNIE_NETWORK..."
echo "explorer: $EXPLORER"
echo "provider: $WEB3_PROVIDER"
echo "pool size: $POOL_SIZE"
echo "memory per worker: $MEMORY_PER_WORKER"
echo "replica: $REPLICA"
echo "host: dask-worker"
#echo "port: 420"
#dask-worker tcp://scheduler:8786 --name $BROWNIE_NETWORK --nworkers $POOL_SIZE --nthreads 2 --memory-limit $MEMORY_PER_WORKER --resources "$BROWNIE_NETWORK=9999999999999999" --preload /app/yearn-exporter/yearn/dask/preload.py
dask worker tcp://scheduler:8786 --host 0.0.0.0 --name $BROWNIE_NETWORK-$REPLICA --nworkers 1 --nthreads 4 --memory-limit $MEMORY_PER_WORKER --resources "$BROWNIE_NETWORK=9999999999999999" --preload /app/yearn-exporter/yearn/dask/preload.py