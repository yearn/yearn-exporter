If you want to add a new chain to the exporter, there are some things you'll need to do:

You must add the following constants:

- in ./yearn/constants.py:
- [ ] Treasury address (if Yearn has a treasury contract deployed)
- [ ] Strategist Multisig address (if Yearn has a SMS deployed)

- in ./yearn/prices/constants.py:
- [ ] add weth address to `tokens_by_network`
- [ ] add usdc address to `tokens_by_network`
- [ ] add dai address to `tokens_by_network`

- in ./scripts/historical-exporter.py:
- [ ] configure `end` to equal the date + hour of deployment for the first Yearn product on the chain.
- [ ] configure `data_query`. See `mapping` in ./yearn/outputs/victoria/output_helper.py to figure out the metric to specify based on what type of product was the first deployed on the chain.

- in ./scripts/historical-treasury-exporter.py:
- [ ] configure `end` to equal the date + hour of deployment for the Yearn Treasury on the chain.
- [ ] configure `data_query` using the existing networks as an example

- in ./scripts/historical-sms-exporter.py:
- [ ] configure `end` to equal the date + hour of deployment for the Strategist Multisig on the chain.
- [ ] configure `data_query` using the existing networks as an example


You also need to set up containers for each exporter on the new chain. This is a little more complicated but you can use existing containers as an example:
- [ ] define common envs for the chain
- [ ] add one new service entry for forwards exporter
- [ ] add one new service entry for historical exporter
- [ ] add one new service entry for treasury exporter
- [ ] add one new service entry for historical treasury exporter
- [ ] add one new service entry for sms exporter
- [ ] add one new service entry for historical sms exporter
- [ ] add one new service entry for wallet exporter
- [ ] add one new service entry for transactions exporter
- [ ] adapt entrypoint.sh


There still may be some things I'm missing, so its important to test to make sure everything works!

Once you've handled everything above, type `make all && make logs-all` into your terminal at the project root. The exporters will start running in docker and any exceptions will show in your terminal. If there are no exceptions, and everything appears to be running smoothly, it's time to submit your PR!