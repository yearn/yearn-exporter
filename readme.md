# Yearn Exporter

Collects real-time on-chain numeric data about all Yearn products and exposes it in multiple formats. Currently, it's able to export data from the following networks:
Ethereum, Fantom, Arbitrum, Gnosis, and Optimism.

The hosted version is available at https://yearn.vision.

# Installation

You will need:

- Etherscan API key (and API keys for other networks block explorer that you want to use)
- [Docker](https://www.docker.com/) and [Docker Compose](https://github.com/docker/compose)

## Usage

Run `make up` to start all of the exporters.

### Grafana Dashboard & Exporters

Export the environment variables required in [.env.example](./.env.example) into .env to run the dashboards and exporters:

```bash
# Make sure all .env variables loaded (`source .env`), check with `echo $variable_name_here`
make build && make dashboards
```

After a successful startup, you can go directly to Grafana at `http://localhost:3000`. If you want to change your dashboards you can sign in at the lower left with `admin:admin`.

### Historical TVL

```bash
# Make sure all .env variables loaded (`source .env`), check with `echo $variable_name_here`
make build && make tvl
```

After a successful start up you can access the tvl rest endpoint at `http://localhost:4000`.

### Run All
```bash
# Make sure all .env variables loaded (`source .env`), check with `echo $variable_name_here`
make build && make up
# Optionally you can filter `make up` by `make up network=eth` or network=ftm ect for networks supported in the make file
```

### Setting up GitHub Actions

Create Access Keys for `apy-exporter-service-user` user.

Create a new [environment](https://github.com/numan/yearn-exporter/settings/environments) named `production` and add the newly created `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`.

## Docker setup

The dockerized exporter is controlled via `make up` command which is invoked via multiple Makefile recipes.
It is possible to specify multiple Makefile args that control which exporters are started on which network.
The available args to control the startup sequence of containers are the following:

- `network`: one of `ethereum`, `fantom`, `arbitrum`, `optimism`, see `make list-networks`
- `commands`: a list of strings delimited with comma pointing to brownie scripts in `./scripts/` e.g. `exporters/partners,exporters/vaults`, see `make list-commands`
- `filter`: used for `make logs` and `make down` to match the container name substring.

This is a flexible approach to start multiple containers on multiple networks which can be used for a given network or given exporters of a certain type and a combination of both.

### Usage examples:

- list supported networks:  
  `make list-networks`

- list supported exporter commands:  
  `make list-commands`

- build the docker image:  
  `make build`

- start _all_ exporters on _all_ supported networks (requires at least *num_exporters x num_networks* available cpu cores):  
  `make up`

- stop all exporters:  
  `make down`

- stop all docker infrastructure:   
  `make down filter=infra`

- start only the vaults exporter for ethereum:  
  `make up network=ethereum commands="exporters/vaults"`

- start only the vaults exporter for all supported networks:  
  `make up commands="exporters/vaults"`

- start only the treasury exporters for all supported networks:  
  `make treasury`

- start all available exporters on arbitrum:  
  `make up network=arbitrum`

- show the logs of all exporters on arbitrum:  
  `make logs network=arbitrum`

- stop all containers matching a string in their name, e.g. treasury:  
  `make down filter=treasury`

- start veYFI exporter on ethereum:  
  `make veYFI`

- start APY exporter on ethereum:  
  `make apy network=eth`

- start APY Debug on ethereum for a specific vault:  
  `export DEBUG_ADDRESS=vault_address_here && make debug-apy network=eth`

- start APY preview for curve pools:  
   `make curve-apy-previews`
