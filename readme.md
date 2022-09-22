# Yearn Exporter

Collects realtime on-chain numeric data about all Yearn products and exposes it in multiple formats. Currently it's able to export data from the following networks:
ethereum, fantom, arbitrum, gnosis and optimism.

Hosted version is available at https://yearn.vision.

# Installation

You will need:

- Erigon for querying historical data
- Victoria-metrics to pull the metrics, persist them and make them queryable
- Grafana if you want to set up custom dashboards and alerts
- Etherscan API key
- docker and docker-compose (not mandatory but easier usage, see below)

## Usage

### Prometheus exporter

```bash
# full info
brownie run exporter
# realtime tvl only
brownie run exporter tvl
```

### Postgres exporter

```bash
# export historical tvl
brownie run historical_tvl
# complementary api server
uvicorn yearn.api:app --port 8000 --reload
```

### On-demand stats

```bash
# tvl summary
brownie run tvl
# info about live v2 strategies
brownie run print_strategies
```

## Docker setup

The dockerized exporter is controlled via multiple docker commands which are invoked via multiple Makefile recipes.
It's possible to specify three different params that control which exporters are started on which network.
The available env variables to control the startup sequence of containers are the following:

- `$PROJECT`: one of `ethereum`, `fantom`, `arbitrum`, `optimism`, `gnosis`
- `$SERVICE`: one of `exporter`, `apy`
- `$COMMANDS`: a list of strings delimited with whitespace pointing to brownie scripts in `./scripts/` e.g. `exporters/partners exporters/vaults`

This is a flexible approach to start multiple containers on multiple networks which can be used for a given network or given exporters of a certain type and a combination of both.

### Usage examples:

- build the docker image:
  `make build`

- start _all_ exporters on _all_ supported networks, NOTE: this will require at least `num_exporters x num_networks` available cpu cores on your host.
  `make up`

- stop all exporters:
  `make down`

- start only the vaults exporter for ethereum:
  `PROJECT=ethereum SERVICE=exporter COMMANDS=exporters/vaults make up`

- start only the treasury exporters for all supported networks:
  `make treasury`

- start all available exporters on arbitrum:
  `PROJECT=arbitrum make up`

- show the logs of all exporters on arbitrum:
  `FILTER=arbitrum make logs`

- stop all containers matching a string in their name, e.g. fantom:
  `FILTER=fantom make down`

### Grafana Dashboard & Exporters

```bash
# Grafana 
export GF_SECURITY_ADMIN_USER=<YOUR_ADMIN_USER> # change this if you want to have a different admin user name, default is admin
export GF_SECURITY_ADMIN_PASSWORD=<YOUR_ADMIN_PASSWORD> # change this if you want to have a different admin password, default is admin
# Ethereum
export WEB3_PROVIDER=<YOUR_WEB3_PROVIDER> # needs to be set, a custom url to an eth archive node to be used as the web3 provider
export EXPLORER=<YOUR_ETH_EXPLORER> # optional, defaults to: https://api.etherscan.io/api
export ETHERSCAN_TOKEN=<YOUR_ETHERSCAN_TOKEN> # this needs to be set
# Fantom
export FTM_WEB3_PROVIDER=<YOUR_FTM_WEB3_PROVIDER> # needs to be set, a custom url to an ftm archive node to be used as the web3 provider
export FTM_EXPLORER=<YOUR_FTM_EXPLORER> # optional, defaults to: https://api.ftmscan.com/api
export FTMSCAN_TOKEN=<YOUR_FTMSCAN_TOKEN> # this needs to be set
# Arbitrum
export ARBI_WEB3_PROVIDER=<YOUR_ARBI_WEB3_PROVIDER> # needs to be set, a custom url to an arbi archive node to be used as the web3 provider
export ARBI_EXPLORER=<YOUR_ARBI_EXPLORER> # optional, defaults to: https://api.arbiscan.io/api
export ARBISCAN_TOKEN=<YOUR_ARBISCAN_TOKEN> # this needs to be set
# Gnosis
export XDAI_WEB3_PROVIDER=<YOUR_XDAI_WEb3_PROVIDER> # needs to be set, a custom url to an xdai archive node to be used as the web3 provider
export XDAI_EXPLORER=<YOUR_XDAI_EXPLORER> # optional, defaults to: https://blockscout.com/xdai/mainnet/api
export XDAISCAN_TOKEN=<YOUR_XDAISCAN_TOKEN> # this needs to be set
# Optimism
export OPTI_WEB3_PROVIDER=<YOUR_OPTI_WEb3_PROVIDER> # needs to be set, a custom url to an xdai archive node to be used as the web3 provider
export OPTI_EXPLORER=<YOUR_OPTI_EXPLORER> # optional, defaults to: https://api-optimistic.etherscan.io/api
export OPTISCAN_TOKEN=<YOUR_OPTISCAN_TOKEN> # this needs to be set
# Exporter Parameters
export POOL_SIZE=<integer>  #1,2,... Needs to be x such that longest export time for single block / x < resolution; default is 1
export RESOLUTION= # 1d, 1h, 30m, 15m, 5m, 1m, 30s, 15s default 1h. How often blocks are stored
make dashboards
```

After successful startup you can go directly to grafana at `http://localhost:3000`. If you want to change your dashboards you can sign-in at the lower left with `admin:admin`.

### Historical TVL

```bash
export WEB3_PROVIDER=<YOUR_WEB3_PROVIDER> # if this is set, it overrides Infura, and instead a custom url is used as the web3 provider
export ETHERSCAN_TOKEN=<YOUR_ETHERSCAN_TOKEN> # this needs to be set
export EXPLORER=<EXPLORER> # optional, default to: https://api.etherscan.io/api
make tvl
```

After successful startup you can access the tvl rest endpoint at `http://localhost:4000`.

### Setting up GitHub Actions

Create Access Keys for `apy-exporter-service-user` user.

Create a new [environment](https://github.com/numan/yearn-exporter/settings/environments) named `production` and add the newly created `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`.