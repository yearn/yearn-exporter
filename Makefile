.PHONY: all up
SHELL := /bin/bash

flags := --remove-orphans --detach
ifdef FLAGS
	flags += $(FLAGS)
endif

#######################################
# specify all supported networks here #
#######################################
supported_networks := ethereum fantom arbitrum optimism base

###############################################
# specify all supported exporter scripts here #
###############################################
exporter_scripts := exporters/vaults,exporters/treasury,exporters/treasury_transactions,exporters/sms,exporters/transactions,exporters/wallets,exporters/partners

# docker-compose commands
compose_command := docker-compose --file services/dashboard/docker-compose.yml --project-directory .
tvl_command 		:= docker-compose --file services/tvl/docker-compose.yml --project-directory .
test_command 		:= docker-compose --file services/dashboard/docker-compose.test.yml --project-directory .

# TODO integrate tvl exporters into BASE recipes below
# tvl recipes
tvl-up:
	$(tvl_command) up $(flags)
tvl: tvl-up

tvl-down:
	$(tvl_command) down

tvl-build:
	$(tvl_command) build $(BUILD_FLAGS)


##########################################
# BASE recipes for running all exporters #
##########################################

# postgres, grafana, victoria
infra:
	docker-compose --file services/dashboard/docker-compose.infra.yml --project-directory . -p yearn-exporter-infra up --detach

# exporter specifc scripts
.ONESHELL:
single-network: infra setup-network
	source set_network_envs.sh
	COMMANDS="$(commands)" NAME_SUFFIX="$(name_suffix)" DEBUG=$(DEBUG) ./run.sh

.ONESHELL:
all-networks: infra
	for network in $(supported_networks); do
		network=$$network commands="$(commands)" name_suffix="$(name_suffix)" DEBUG=$(DEBUG) make single-network
	done

.PHONY: down
down:
	$(eval filter = $(if $(filter),yearn-exporter-$(filter),$(if $(network),$(network),yearn-exporter-worker)))
	echo "stopping containers for filter: $(filter)"
	docker ps -a -q --filter="name=$(filter)" | xargs -L 1 docker rm -f 2> /dev/null || true
	echo "running containers:"
	docker ps

.PHONY: build
build:
	docker build -t ghcr.io/yearn/yearn-exporter .
logs:
	$(eval filter = $(if $(filter),yearn-exporter-$(filter),$(if $(network),$(network),yearn-exporter-worker)))
	$(eval since = $(if $(since),$(since),300s))
	docker ps -a -q --filter="name=$(filter)"| xargs -L 1 -P $$(docker ps --filter="name=$(filter)" | wc -l) docker logs --since $(since) -ft

.ONESHELL:
.SILENT:
up:
	$(eval commands = $(if $(commands),$(commands),$(exporter_scripts)))
	source set_network_envs.sh
##################################################
# default scripts which should always be started #
##################################################
	if [ "$(network)" == "" ]; then
		make all-networks commands="$(commands)" name_suffix="$(name_suffix)"
	else
		make single-network network=$(network) commands="$(commands)" name_suffix="$(name_suffix)"
	fi

#######################################################################
# additional scripts which should be started under specifc conditions #
#######################################################################
	if [ "$$NETWORK" == "ethereum" ] || [ "$$NETWORK" == "" ]; then
		if [ "$(commands)" == "exporters/veyfi" ] || [ "$(commands)" == $(exporter_scripts) ] || [ "$(commands)" == "" ]; then
			make single-network network=ethereum commands="exporters/veyfi"
		fi
		if [ "$(commands)" == "exporters/yeth" ] || [ "$(commands)" == $(exporter_scripts) ] || [ "$(commands)" == "" ]; then
			make single-network network=ethereum commands="exporters/yeth"
		fi
	fi

# cleanup containers which are temporarily unused or too buggy, ugly workaround until there is a better way to control this:
	make down filter=yearn-exporter-worker-fantom-exporters-treasury-transactions
	make down filter=yearn-exporter-worker-arbitrum-exporters-treasury-transactions
	make down filter=yearn-exporter-worker-optimism-exporters-treasury-transactions
	make down filter=yearn-exporter-worker-base-exporters-treasury-transactions

# LOGGING
	$(eval with_logs = $(if $(with_logs),$(with_logs),true))
	$(eval filter = $(if $(filter),yearn-exporter-$(filter),yearn-exporter-worker))
	if [ "$(with_logs)" == "true" ]; then
		if [ "$$NETWORK" != "" ]; then
			make logs filter=$$NETWORK
		else
			make logs filter=$(filter)
		fi
	fi

.ONESHELL:
setup-network:
	source set_network_envs.sh
	$(compose_command) -p $$PROJECT_PREFIX run --entrypoint "./brownie_init.sh" exporter

.ONESHELL:
console: build setup-network
	source set_network_envs.sh
	docker build -f Dockerfile.dev -t ghcr.io/yearn/yearn-exporter .
	$(compose_command) -p $$PROJECT_PREFIX run --rm --entrypoint "brownie console --network $$BROWNIE_NETWORK" exporter

shell: setup-network
	source set_network_envs.sh
	$(compose_command) -p $$PROJECT_PREFIX run --rm --entrypoint bash exporter

.ONESHELL:
debug-apy: build setup-network
	source set_network_envs.sh
	docker build -f Dockerfile.dev -t ghcr.io/yearn/yearn-exporter .
	DEBUG=true $(compose_command) -p $$PROJECT_PREFIX run --rm --entrypoint "brownie run --network $$BROWNIE_NETWORK debug_apy with_exception_handling -I" exporter

list-networks:
	@echo "supported networks: $(supported_networks)"

list-commands:
	@echo "supported exporter commands: $(exporter_scripts)"

# some convenience aliases
exporters:
	make up commands="$(exporter_scripts)"

exporters-up: exporters
exporters-down: down
logs-exporters: logs
exporters-logs: logs-exporters
dashboards: up
dashboards-up: up
dashboards-down: down
dashboards-build: build
logs-all: logs

# Maintenance
rebuild: down build up
all: rebuild
scratch: clean-volumes build up
clean-volumes: down
	$(eval filter = $(if $(filter),yearn-exporter-$(filter),$(if $(network),$(network),yearn-exporter-worker)))
	docker volume ls -q --filter="name=$(filter)" | xargs -L 1 docker volume rm 2> /dev/null || true
clean-exporter-volumes: clean-volumes
dashboards-clean-volumes: clean-exporter-volumes

tvl-clean-volumes:
	$(tvl_ command) down -v

clean-cache:
	make clean-volumes filter=cache
dashboards-clean-cache: clean-cache


############################
# Network-specific recipes #
############################

# Ethereum
ethereum:
	make up logs network=ethereum

# Ethereum aliases
eth: ethereum
mainnet: ethereum

# Fantom
fantom:
	make up logs network=fantom

# Arbitrum Chain
arbitrum:
	make up logs network=arbitrum

# Optimism Chain
optimism:
	make up logs network=optimism

# Gnosis Chain
gnosis:
	make up logs network=gnosis

# Base Chain
base:
	make up logs network=base

############################
# Exporter-specifc recipes #
############################

# Vault Exporters
vaults:
	make up filter=vaults commands="exporters/vaults"
logs-vaults:
	make logs filter=vaults commands="exporters/vaults"

# Treasury Exporters
treasury:
	make up filter=treasury commands="exporters/treasury"
logs-treasury:
	make logs filter=treasury

# Treasury TX Exporters
treasury-tx:
	make up filter=treasury_transactions commands="exporters/treasury_transactions"
logs-treasury-tx:
	make logs filter=treasury_transactions

# Wallet Stats Exporters
wallets:
	make up filter=wallets commands="exporters/wallets"
logs-wallets:
	make logs filter=wallets commands="exporters/wallets"

# Partners Exporters
partners:
	make up filter=partners commands="exporters/partners"

logs-partners:
	make logs filter=partners commands="exporters/partners"

# Strategist Multisig Exporters
sms:
	make up filter=sms commands="exporters/sms"
logs-sms:
	make logs filter=sms commands="exporters/sms"

# Transactions Exporters
transactions:
	make up filter=transactions commands="exporters/transactions"
logs-transactions:
	make logs filter=transactions commands="exporters/transactions"

# apy scripts
apy-monitoring:
	make up commands="s3 with_monitoring" filter=s3

apy-experimental-monitoring:
	make up commands="s3 with_monitoring" name_suffix=experimental filter=s3

apy:
	make up commands="s3" filter=s3

apy-experimental:
	make up commands="s3" name_suffix=experimental filter=s3

curve-apy-previews:
	make up commands=curve_apy_previews network=eth with_logs=false

curve-apy-previews-monitoring:
	make up commands="curve_apy_previews with_monitoring" network=eth

apy-yeth-monitoring:
	make up commands="yeth with_monitoring" network=eth

apy-yeth:
	make up commands="yeth" network=eth filter=yeth
	
aerodrome-apy-previews:
	make up commands="drome_apy_previews" network=base

aerodrome-apy-previews-monitoring:
	make up commands="drome_apy_previews with_monitoring" network=base

velodrome-apy-previews:
	make up commands="drome_apy_previews" network=optimism

velodrome-apy-previews-monitoring:
	make up commands="drome_apy_previews with_monitoring" network=optimism

# revenue scripts
revenues:
	make up network=eth commands=revenues with_logs=false

revenues-monitoring:
	make up network=eth commands="revenues with_monitoring" with_logs=false

# partners scripts
partners-eth:
	make up network=eth commands="exporters/partners"

partners-ftm:
	make up network=ftm commands="exporters/partners"

partners-summary-eth:
	make up network=eth commands="partners_summary"

partners-summary-ftm:
	make up network=ftm commands="partners_summary"

# veyfi scripts
veyfi:
	make up network=ethereum commands="exporters/veyfi" logs

# yeth
yeth:
	make up network=ethereum commands="exporters/yeth" logs

# utils
fetch-memray:
	mkdir reports/memray -p
	sudo cp -r /var/lib/docker/volumes/yearn-exporter-worker-ethereum_memray/_data/ reports/memray/ethereum
	sudo cp -r /var/lib/docker/volumes/yearn-exporter-worker-fantom_memray/_data/   reports/memray/fantom
	sudo cp -r /var/lib/docker/volumes/yearn-exporter-worker-arbitrum_memray/_data/ reports/memray/arbitrum
	sudo cp -r /var/lib/docker/volumes/yearn-exporter-worker-optimism_memray/_data/ reports/memray/optimism
	sudo cp -r /var/lib/docker/volumes/yearn-exporter-worker-gnosis_memray/_data/   reports/memray/gnosis
