# yearn exporter

collects on-chain numeric data about Yearn Vaults and exposes it in prometheus format.

point prometheus at this exporter persist the data and make it queryable.

set up grafana for custom dashboards and alerts.


## usage
### exporter
```
brownie run yearn exporter_v1 --network mainnet
brownie run yearn exporter_v2 --network mainnet
brownie run yearn exporter_experimental --network mainnet
```

### Stats
```
brownie run yearn develop_v1 --network mainnet
brownie run yearn develop_v2 --network mainnet
brownie run yearn develop_experimental --network mainnet
brownie run yearn tvl --network mainnet
```

## Docker setup
```
export GF_SECURITY_ADMIN_USER=<YOUR_ADMIN_USER> # change this if you want to have a different admin user name, default is admin
export GF_SECURITY_ADMIN_PASSWORD=<YOUR_ADMIN_PASSWORD> # change this if you want to have a different admin password, default is admin
export WEB3_INFURA_PROJECT_ID=<YOUR_PROJECT_ID> # this needs to be set
export ALCHEMY_URL=<YOUR_ALCHEMY_URL> # if this is set, it overrides Infura, and instead alchemy is used as the web3 provider
export ETHERSCAN_TOKEN=<YOUR_ETHERSCAN_TOKEN> # this needs to be set
export SLEEP_SECONDS=<YOUR_SLEEP_SECONDS> # if this is set, the exporters will wait the given amount of time between subsequent invocations to your web3 provider.

docker-compose up -d
```

After successful startup you can go directly to grafana at `http://localhost:3000`. If you want to change your dashboards you can sign-in at the lower left with `admin:admin`.

## supported vaults

the goal of the project is to collect advanced metrics about vaults and strategies.
