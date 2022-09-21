#! /bin/bash
set -e

if [[ -z "${PROJECT}" ]]; then
  echo "please provide a project name via \$PROJECT."
  exit 1
fi
if [[ -z "${SERVICE}" ]]; then
  echo "please provide a service to run via \$SERVICE."
  exit 1
fi


if [[ $PROJECT == "ethereum" ]]; then
  export NETWORK=mainnet
	export WEB3_PROVIDER=$WEB3_PROVIDER
  export EXPLORER=$EXPLORER
  export DEFAULT_EXPLORER=https://api.etherscan.io/api

elif [[ $PROJECT == "fantom" ]]; then
	export NETWORK=ftm-main
	export WEB3_PROVIDER=$FTM_WEB3_PROVIDER
  export EXPLORER=$FTM_EXPLORER
  export DEFAULT_EXPLORER=https://api.ftmscan.com/api

elif [[ $PROJECT == "gnosis" ]]; then
	export NETWORK=xdai-main
	export WEB3_PROVIDER=$XDAI_WEB3_PROVIDER
  export EXPLORER=$XDAI_EXPLORER
  export DEFAULT_EXPLORER=https://blockscout.com/xdai/mainnet/api

elif [[ $PROJECT == "arbitrum" ]]; then
	export NETWORK=arbitrum-main
	export WEB3_PROVIDER=$ARBI_WEB3_PROVIDER
  export EXPLORER=$ARBI_EXPLORER
  export DEFAULT_EXPLORER=https://api.arbiscan.io/api

elif [[ $PROJECT == "optimism" ]]; then
	export NETWORK=optimism-main
	export WEB3_PROVIDER=$OPTI_WEB3_PROVIDER
  export EXPLORER=$OPTI_EXPLORER
  export DEFAULT_EXPLORER=https://api-optimistic.etherscan.io/api

else
  echo "unsupported project $PROJECT specified!"
  exit 1
fi

docker-compose --file services/dashboard/docker-compose.yml --project-directory . -p $PROJECT up --build $SERVICE --detach
