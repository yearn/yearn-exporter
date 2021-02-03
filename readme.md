# yearn exporter

collects on-chain numeric data about yearn vault and exposes it in prometheus format.

point prometheus at this exporter persist the data and make it queryable.

set up grafana for custom dashboards and alerts.


## usage
### exporter
```
brownie run yearn exporter_v1 --network mainnet
brownie run yearn exporter_v2 --network mainnet
```
### Stats
```
brownie run yearn develop_v1 --network mainnet
brownie run yearn develop_v2 --network mainnet
brownie run yearn tvl --network mainnet
```
## supported vaults

the goal of the project is to collect advanced metrics about vaults and strategies.
