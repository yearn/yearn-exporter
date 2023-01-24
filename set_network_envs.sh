#! /bin/bash
set -e

if [[ -z "$network" ]]; then
  echo "WARN: No network specified, running on default network ethereum."
  export NETWORK=ethereum
  export BROWNIE_NETWORK=mainnet
  export WEB3_PROVIDER=$WEB3_PROVIDER
  export EXPLORER=$EXPLORER
  export DEFAULT_EXPLORER=https://api.etherscan.io/api

elif [[ "$network" =~ ^ethereum$|^eth$|^ETH$|^mainnet$ ]]; then
  export NETWORK=ethereum
  export BROWNIE_NETWORK=mainnet
  export WEB3_PROVIDER=$WEB3_PROVIDER
  export EXPLORER=$EXPLORER
  export DEFAULT_EXPLORER=https://api.etherscan.io/api

elif [[ "$network" =~ ^ftm$|^FTM$|^fantom$ ]]; then
  export NETWORK=fantom
  export BROWNIE_NETWORK=ftm-main
  export WEB3_PROVIDER=$FTM_WEB3_PROVIDER
  export EXPLORER=$FTM_EXPLORER
  export DEFAULT_EXPLORER=https://api.ftmscan.com/api

elif [[ "$network" =~ ^gno$|^GNO$|^gnosis$ ]]; then
  export NETWORK=gnosis
  export BROWNIE_NETWORK=xdai-main
  export WEB3_PROVIDER=$XDAI_WEB3_PROVIDER
  export EXPLORER=$XDAI_EXPLORER
  export DEFAULT_EXPLORER=https://blockscout.com/xdai/mainnet/api

elif [[ "$network" =~ ^arrb$|^ARRB$|^arbi$|^arbitrum$ ]]; then
  export NETWORK=arbitrum
  export BROWNIE_NETWORK=arbitrum-main
  export WEB3_PROVIDER=$ARBI_WEB3_PROVIDER
  export EXPLORER=$ARBI_EXPLORER
  export DEFAULT_EXPLORER=https://api.arbiscan.io/api

elif [[ "$network" =~ ^op$|^OPTI$|^opti$|^optimism$ ]]; then
  export NETWORK=optimism
  export BROWNIE_NETWORK=optimism-main
  export WEB3_PROVIDER=$OPTI_WEB3_PROVIDER
  export EXPLORER=$OPTI_EXPLORER
  export DEFAULT_EXPLORER=https://api-optimistic.etherscan.io/api

else
  echo "Error! Unsupported network $network specified!"
  exit 1
fi

export PROJECT_PREFIX=yearn-exporter-worker-$NETWORK
