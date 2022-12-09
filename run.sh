#! /bin/bash
set -e

if [[ -z "${NETWORK}" ]]; then
  echo "please provide a network via \$NETWORK."
  exit 1
fi
if [[ -z "${COMMANDS}" ]]; then
  echo "please provide a list of commands to run via \$COMMANDS."
  exit 1
fi
if [[ -z "${POOL_SIZE}" ]]; then
  POOL_SIZE=2
fi

if [[ $NETWORK == "ethereum" ]]; then
  export BROWNIE_NETWORK=mainnet
  export WEB3_PROVIDER=$WEB3_PROVIDER
  export EXPLORER=$EXPLORER
  export DEFAULT_EXPLORER=https://api.etherscan.io/api

elif [[ $NETWORK == "fantom" ]]; then
  export BROWNIE_NETWORK=ftm-main
  export WEB3_PROVIDER=$FTM_WEB3_PROVIDER
  export EXPLORER=$FTM_EXPLORER
  export DEFAULT_EXPLORER=https://api.ftmscan.com/api

elif [[ $NETWORK == "gnosis" ]]; then
  export BROWNIE_NETWORK=xdai-main
  export WEB3_PROVIDER=$XDAI_WEB3_PROVIDER
  export EXPLORER=$XDAI_EXPLORER
  export DEFAULT_EXPLORER=https://blockscout.com/xdai/mainnet/api

elif [[ $NETWORK == "arbitrum" ]]; then
  export BROWNIE_NETWORK=arbitrum-main
  export WEB3_PROVIDER=$ARBI_WEB3_PROVIDER
  export EXPLORER=$ARBI_EXPLORER
  export DEFAULT_EXPLORER=https://api.arbiscan.io/api

elif [[ $NETWORK == "optimism" ]]; then
  export BROWNIE_NETWORK=optimism-main
  export WEB3_PROVIDER=$OPTI_WEB3_PROVIDER
  export EXPLORER=$OPTI_EXPLORER
  export DEFAULT_EXPLORER=https://api-optimistic.etherscan.io/api

else
  echo "unsupported network $NETWORK specified!"
  exit 1
fi

export SENTRY_RELEASE=$(git rev-parse --short HEAD)

IFS=',' read -r -a commands <<< "$COMMANDS"

### Ensure workers are running for `BROWNIE_NETWORK`
REPLICA=$((0))
while [ $REPLICA -lt $POOL_SIZE ];
do
CONTAINER_NAME=${NETWORK}_worker_$REPLICA
docker rm -f $CONTAINER_NAME 2> /dev/null || true

export REPLICA=${REPLICA}
docker-compose \
  --file services/dashboard/docker-compose.yml \
  --project-directory . -p $NETWORK run \
  --name $CONTAINER_NAME \
  --detach \
  workers

REPLICA=$((REPLICA+1))
done

#TODO add --detach
for CMD in "${commands[@]}"; do
  NAME=$(echo $CMD | sed -e 's/[/ ]/_/g')
  # TODO handle multiple containers with the same name more gracefully
  CONTAINER_NAME=${NETWORK}_${NAME}_1
  docker rm -f $CONTAINER_NAME 2> /dev/null || true
  docker-compose \
    --file services/dashboard/docker-compose.yml \
    --project-directory . \
    -p $NETWORK run \
    --name $CONTAINER_NAME \
    --detach \
    exporter $CMD
  # hack to manually patch the container docker config so the container is restarted
  # if the docker-compose run failed
  docker container update --restart on-failure $CONTAINER_NAME
done
