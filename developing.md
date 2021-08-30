# Hierarchy

The exporters follow a hierarchical structure.

Yearn ← Registries ← Vaults ← Strategies

It should be possible to instantiate them at any level, be it a Registry of v2 vaults or an individual Vault. Instantiating lower level objects from higher level rather than directly might provide additional capabilities such as Registry introspection (e.g. a Vault can look up if it's endorsed if created from Registry) and batch querying (e.g. a Registry can describe all of its contents faster and more efficiently).

## Yearn

A MetaRegistry which contains all Registries.

- `registries` a dict containing all the child Registries
- `describe(self, block=None)` recursively describe its contents
- `total_value_at(self, block=None)` get dollar amounts of total value locked in its children

## Registry

A Registry describes a suite of products. It must implement these functions:

- `vaults` list of active Vaults it contains
- `describe(self, block=None)` recursively describe its contents
- `total_value_at(self, block=None)` get dollar amounts of total value locked in its children

It should implement this function:

- `active_vaults_at(self, block=None)` list of active Vaults it had contained at a certain block height

Registries should watch new deployments and update their contents accordingly.

## Vault

A Vault must implement these functions:

- `describe(self, block=None)` read all numeric data about itself.

# Prices

You should only ever use `yearn.prices.magic` to look up prices. It will automatically detect Yearn Vaults, Uniswap or Balancer LP tokens, IronBank or Compound markets, Curve LP tokens and will recursively peel as many layers as it takes to get to the basic tokens. Don't forget to specify block number when dealing with historical data.

# Multicall and Parallel

You should always use `yearn.multicall` whenever possible to reduce the burden of the node.

You should further use `joblib.Parallel` to run tasks simultaneously, but be aware of rate limits and memory usage.

# Caching

Yearn exporter comes with an event caching middleware powered by `joblib.Memory`. This allows to query logs once and significantly reduces hot startup time. Feel free to use this type of disk caching for other things if you are certain they can't change.

# Testing

Do not instantiate contracts on module load, this breaks tests, which only create a connection after the tests have been collected.
