#! /bin/bash
set -e

if [[ -z "${NETWORK}" ]]; then
  echo "please provide a network via \$NETWORK."
fi

if [[ $NETWORK == "ethereum" ]]; then
  export BROWNIE_NETWORK=mainnet
  export WEB3_PROVIDER=$WEB3_PROVIDER
  export EXPLORER=$EXPLORER
  export DEFAULT_EXPLORER=https://api.etherscan.io/api

elif [[ $NETWORK == "fantom" ]]; then
  echo "**** FANTOM ***"
  export BROWNIE_NETWORK=ftm-main
  export WEB3_PROVIDER=$FTM_WEB3_PROVIDER
  export EXPLORER=$FTM_EXPLORER
  export DEFAULT_EXPLORER=https://api.ftmscan.com/api

elif [[ $NETWORK == "gnosis" ]]; then
  export BROWNIE_NETWORK=xdai-mainnet
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
fi
