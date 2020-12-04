# yearn exporter

collects on-chain numeric data about yearn vault and exposes it in prometheus format.

point prometheus at this exporter persist the data and make it queryable.

set up grafana for custom dashboards and alerts.
set as windows enviroment variable `ETHERSCAN_TOKEN=YOURAPIKEY`

## usage

```
brownie run yearn exporter --network mainnet
brownie run yearn exporter_v2 --network mainnet 
```

## supported vaults

the goal of the project is to collect advanced metrics about vaults and strategies.
if a strategy type is not marked here, only basic metrics are exposed.

- [x] StrategyCurve*VoterProxy
- [ ] StrategyVaultUSDC
- [ ] StrategyDForceUSDC
- [ ] StrategyCurveYCRVVoter
- [ ] StrategyTUSDCurve
- [ ] StrategyDAICurve
- [ ] StrategyDForceUSDT
- [ ] StrategyCreamYFI
- [ ] StrategyCurveSBTC
- [ ] StrategyMKRVaultDAIDelegate
- [ ] CurveYCRVVoter
