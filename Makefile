flags := --remove-orphans --detach
ifdef FLAGS
	flags += $(FLAGS)
endif

# define a default filter
filter := $(if $(FILTER),$(FILTER),exporter)

#######################################
# specify all supported networks here #
#######################################
networks := ethereum fantom arbitrum optimism gnosis

###############################################
# specify all supported exporter scripts here #
###############################################
exporter_scripts := exporters/vaults exporters/treasury exporters/treasury_transactions exporters/sms exporters/transactions exporters/wallets exporters/partners

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
	PROJECT=$(PROJECT) SERVICE=$(SERVICE) COMMANDS="$(COMMANDS)" ./run.sh

.ONESHELL:
all-networks: infra
	for project in $(networks); do
		PROJECT=$$project SERVICE=$(SERVICE) COMMANDS="$(COMMANDS)" make single-network
	done

down:
	docker ps -a -q --filter="name=$(filter)" | xargs -L 1 docker rm -f 2> /dev/null || true

.PHONY: build
build:
	$(dashboards_command) build $(BUILD_FLAGS)

logs:
	docker ps -a -q --filter="name=$(filter)"| xargs -L 1 -P $$(docker ps --filter="name=$(filter)" | wc -l) docker logs --since 30s -ft

.ONESHELL:
up:
	$(eval SERVICE = $(if $(SERVICE),$(SERVICE),exporter))
	$(eval COMMANDS = $(if $(COMMANDS),$(COMMANDS),$(exporter_scripts)))
	if [ "$(PROJECT)" != "" ]; then
		SERVICE=$(SERVICE) COMMANDS="$(COMMANDS)" make single-network logs
	else
		SERVICE=$(SERVICE) COMMANDS="$(COMMANDS)" make all-networks logs
	fi

# some convenience aliases
exporters: SERVICE=exporter
exporters: COMMANDS=$(exporter_scripts)
exporters: up

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
clean_volumes: down
	docker volume ls -q --filter="name=$(filter)" | xargs -L 1 docker volume rm 2> /dev/null || true
clean-exporter-volumes: clean_volumes
dashboards-clean-volumes: clean-exporter-volumes

tvl-clean-volumes:
	$(tvl_command) down -v

clean_cache: FILTER=cache
clean-cache: clean_volumes
dashboards-clean-cache: clean_cache


############################
# Network-specific recipes #
############################

# Ethereum
ethereum: PROJECT=ethereum
ethereum: FILTER=ethereum
ethereum: exporters logs

# Ethereum aliases
eth: ethereum
mainnet: ethereum

# Fantom
fantom: PROJECT=fantom
fantom: FILTER=fantom
fantom: exporters logs

# Arbitrum Chain
arbitrum: PROJECT=arbitrum
arbitrum: FILTER=arbitrum
arbitrum: exporters logs

# Optimism Chain
optimism: PROJECT=optimism
optimism: FILTER=optimism
optimism: exporters logs

# Gnosis Chain
gnosis: PROJECT=gnosis
gnosis: FILTER=gnosis
gnosis: exporters logs

############################
# Exporter-specifc recipes #
############################

# Treasury Exporters
treasury: SERVICE=exporter
treasury: FILTER=treasury
treasury: COMMANDS="exporters/treasury"
treasury: up

logs-treasury: FILTER=treasury
logs-treasury: logs

# Treasury TX Exporters
treasury-tx: SERVICE=exporter
treasury-tx: COMMANDS="exporters/treasury_transactions"
treasury-tx: FILTER=treasury_transactions
treasury-tx: up

logs-treasury-tx: FILTER=treasury_transactions
logs-treasury-tx: logs

# apy scripts
apy: SERVICE=apy
apy: COMMANDS=s3
apy: up
