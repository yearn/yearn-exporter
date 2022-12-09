SHELL := /bin/bash

NETWORK ?= ethereum
export
BROWNIE_NETWORK ?= mainnet
export

.ONESHELL:
get-network-name:
ifneq ($(shell echo $(network) | egrep "^ethereum$$|^eth$$|^ETH$$|^mainnet$$"),)
	$(eval NETWORK = ethereum)
	$(eval BROWNIE_NETWORK = mainnet)
else ifneq ($(shell echo $(network) | egrep "^ftm$$|^FTM$$|^fantom$$"),)
	$(eval NETWORK = fantom)
	$(eval BROWNIE_NETWORK = ftm-main)
else ifneq ($(shell echo $(network) | egrep "^arrb$$|^ARRB$$|arbi$$|^arbitrum$$"),)
	$(eval NETWORK = arbitrum)
	$(eval BROWNIE_NETWORK = arbitrum-main)
else ifneq ($(shell echo $(network) | egrep "^op$$|^OPTI$$|^opti$$|^optimism$$"),)
	$(eval NETWORK = optimism)
	$(eval BROWNIE_NETWORK = optimism-main)
else ifneq ($(shell echo $(network) | egrep "^gno$$|^GNO$$|^gnosis$$"),)
	$(eval NETWORK = gnosis)
	$(eval BROWNIE_NETWORK = xdai-main)
else ifeq ($(network),)
		@echo "No valid network specified. You can specify a network by passing network=<NETWORK>. Supported networks: '$(supported_networks)'"
		$(eval undefine NETWORK)
		$(eval undefine BROWNIE_NETWORK)
endif
	if [[ $${NETWORK} != "" ]]; then
		@echo "Running on network '$(NETWORK)'"
	fi

flags := --remove-orphans --detach
ifdef FLAGS
	flags += $(FLAGS)
endif

#######################################
# specify all supported networks here #
#######################################
supported_networks := ethereum fantom arbitrum optimism gnosis

###############################################
# specify all supported exporter scripts here #
###############################################
exporter_scripts := exporters/vaults,exporters/treasury,exporters/treasury_transactions,exporters/sms,exporters/transactions,exporters/wallets,exporters/partners

# docker-compose commands
dashboards_command := docker-compose --file services/dashboard/docker-compose.yml --project-directory .
tvl_command 		   := docker-compose --file services/tvl/docker-compose.yml --project-directory .
test_command 		   := docker-compose --file services/dashboard/docker-compose.test.yml --project-directory .

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
	docker-compose --file services/dashboard/docker-compose.infra.yml --project-directory . -p infra up --detach

# exporter specifc scripts
single-network: infra
	$(dashboards_command) build
	NETWORK=$(network) COMMANDS="$(commands)" DEBUG=$(DEBUG) ./run.sh

.ONESHELL:
all-networks: infra
	for network in $(supported_networks); do
		network=$$network commands="$(commands)" DEBUG=$(DEBUG) make single-network
	done

down: get-network-name
	$(eval filter = $(if $(filter),$(filter),$(if $(NETWORK),$(NETWORK),exporter)))
	echo "stopping containers for filter: $(filter)"
	docker ps -a -q --filter="name=$(filter)" | xargs -L 1 docker rm -f 2> /dev/null || true
	$(eval filter = $(if $(NETWORK),$(NETWORK),worker))
	echo "stopping containers for filter: $(filter)"
	docker ps -a -q --filter="name=$(filter)" | xargs -L 1 docker rm -f 2> /dev/null || true
	echo "running containers:"
	docker ps

.PHONY: build
build:
	$(dashboards_command) build $(BUILD_FLAGS)

logs: get-network-name
	$(eval filter = $(if $(filter),$(filter),$(if $(NETWORK),$(NETWORK),exporter)))
	$(eval since = $(if $(since),$(since),30s))
	echo $(filter)
	docker ps -a -q --filter="name=$(filter)"| xargs -L 1 -P $$(docker ps --filter="name=$(filter)" | wc -l) docker logs --since $(since) -ft


.ONESHELL:
.SILENT:
up: get-network-name
	$(eval commands = $(if $(commands),$(commands),$(exporter_scripts)))
	$(eval with_logs = $(if $(with_logs),$(with_logs),true))
	$(eval filter = $(if $(filter),$(filter),$(if $(NETWORK),$(NETWORK),exporter)))
	if [ "$(NETWORK)" != "" ]; then
		if [ "$(with_logs)" == "true" ]; then
			make single-network network=$(NETWORK) commands="$(commands)" logs filter="$(filter)"
		else
			make single-network network=$(NETWORK) commands="$(commands)"
		fi
	else
		if [ "$(with_logs)" == "true" ]; then
			make all-networks commands="$(commands)" logs filter="$(filter)"
		else
			make all-networks commands="$(commands)"
		fi
	fi

console: get-network-name
	$(eval BROWNIE_NETWORK = $(if $(BROWNIE_NETWORK),$(BROWNIE_NETWORK),mainnet))
	docker build -f Dockerfile -f Dockerfile.dev -t ghcr.io/yearn/yearn-exporter .
	docker-compose --file services/dashboard/docker-compose.yml --project-directory . run --rm --entrypoint "brownie console --network $(BROWNIE_NETWORK)" exporter

shell: get-network-name
	docker-compose --file services/dashboard/docker-compose.yml --project-directory . run --rm --entrypoint bash exporter

.ONESHELL:
debug-apy: get-network-name
	docker build -f Dockerfile -f Dockerfile.dev -t ghcr.io/yearn/yearn-exporter .
	DEBUG=true docker-compose --file services/dashboard/docker-compose.yml --project-directory . run --rm --entrypoint "brownie run --network $(BROWNIE_NETWORK) debug_apy with_exception_handling -I" exporter

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
	$(eval filter = $(if $(filter),$(filter),$(if $(NETWORK),$(NETWORK),exporter)))
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
apy:
	make up commands="s3 with_monitoring" filter=s3

# revenue scripts
revenues:
	make up network=eth commands=revenues with_logs=false

# partners scripts
partners-eth:
	make up network=eth commands="exporters/partners"

partners-ftm:
	make up network=ftm commands="exporters/partners"

partners-summary-eth:
	make up network=eth commands="partners_summary"

partners-summary-ftm:
	make up network=ftm commands="partners_summary"
