# Yearn Exporter

Collects realtime on-chain numeric data about all Yearn products and exposes it in multiple formats.

Hosted version is available at https://yearn.vision.

# Installation

You will need:

- TurboGeth for querying historical data
- Prometheus to pull the metrics, persist them and make them queryable
- Grafana if you want to set up custom dashboards and alerts
- Etherscan API key 
- _Optional:_ Google Cloud's Big Query credentials

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

### Grafana dashboard

```bash
export GF_SECURITY_ADMIN_USER=<YOUR_ADMIN_USER> # change this if you want to have a different admin user name, default is admin
export GF_SECURITY_ADMIN_PASSWORD=<YOUR_ADMIN_PASSWORD> # change this if you want to have a different admin password, default is admin
export WEB3_INFURA_PROJECT_ID=<YOUR_PROJECT_ID> # this needs to be set
export WEB3_PROVIDER=<YOUR_WEB3_PROVIDER> # if this is set, it overrides Infura, and instead a custom url is used as the web3 provider
export ETHERSCAN_TOKEN=<YOUR_ETHERSCAN_TOKEN> # this needs to be set
export SLEEP_SECONDS=<YOUR_SLEEP_SECONDS> # if this is set, the exporters will wait the given amount of time between subsequent invocations to your web3 provider.

docker-compose up --detach
```

After successful startup you can go directly to grafana at `http://localhost:3000`. If you want to change your dashboards you can sign-in at the lower left with `admin:admin`.

### Historical TVL

```bash
export WEB3_INFURA_PROJECT_ID=<YOUR_PROJECT_ID> # this needs to be set
export WEB3_PROVIDER=<YOUR_WEB3_PROVIDER> # if this is set, it overrides Infura, and instead a custom url is used as the web3 provider
export ETHERSCAN_TOKEN=<YOUR_ETHERSCAN_TOKEN> # this needs to be set

docker-compose --file services/tvl/docker-compose.yml --project-directory . up --build --detach
```

After successful startup you can access the tvl rest endpoint at `http://localhost:4000`.
