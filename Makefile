flags := --remove-orphans --detach
ifdef FLAGS
	flags += $(FLAGS)
endif

# docker-compose commands
dashboards_command 	:= docker-compose --file services/dashboard/docker-compose.yml --project-directory .
tvl_command 		:= docker-compose --file services/tvl/docker-compose.yml --project-directory .
test_command 		:= docker-compose --file services/dashboard/docker-compose.test.yml --project-directory .

# treasury exporter convenience vars
ethereum_treasury_containers := treasury-exporter 			treasury-transactions-exporter
fantom_treasury_containers   := ftm-treasury-exporter 		ftm-treasury-transactions-exporter
arbitrum_treasury_containers := arbi-treasury-exporter 		arbi-treasury-transactions-exporter
gnosis_treasury_containers 	 := gnosis-treasury-exporter 	gnosis-treasury-transactions-exporter
optimism_treasury_contrainers:= opti-treasury-exporter 		opti-treasury-transactions-exporter

# less spammy output convenience vars
ethereum_containers_lite := eth-exporter  	sms-exporter 	 		transactions-exporter 			$(ethereum_treasury_containers)
fantom_containers_lite   := ftm-exporter 	ftm-sms-exporter 		ftm-transactions-exporter 		$(fantom_treasury_containers)
arbitrum_containers_lite := arbi-exporter 	arbi-sms-exporter 		arbi-transactions-exporter 		$(arbitrum_treasury_containers)
gnosis_containers_lite   := gnosis-exporter gnosis-sms-exporter 	gnosis-transactions-exporter 	$(gnosis_treasury_containers)
optimism_containers_lite := opti-exporter 	opti-sms-exporter 		opti-transactions-exporter 		$(optimism_treasury_contrainers)

# container vars
ethereum_containers := $(ethereum_containers_lite) 	wallet-exporter 		partners-exporter
fantom_containers 	:= $(fantom_containers_lite) 	ftm-wallet-exporter 	ftm-partners-exporter
arbitrum_containers := $(arbitrum_containers_lite) 	arbi-wallet-exporter	arbi-partners-exporter
gnosis_containers 	:= $(gnosis_containers_lite) 	gnosis-wallet-exporter	gnosis-partners-exporter
optimism_containers := $(optimism_containers_lite) 	opti-wallet-exporter	opti-partners-exporter

treasury_containers := 	$(ethereum_treasury_containers) $(fantom_treasury_containers) 	$(arbitrum_treasury_containers) $(gnosis_treasury_containers) 	$(optimism_treasury_contrainers)
treasury_tx_containers := treasury-transactions-exporter ftm-treasury-transactions-exporter arbi-treasury-transactions-exporter gnosis-treasury-transactions-exporter opti-treasury-transactions-exporter
all_containers := 		$(ethereum_containers) 			$(fantom_containers) 			$(arbitrum_containers) 			$(gnosis_containers) 			$(optimism_containers)

# Basic Makefile commands
dashboards: dashboards-up
tvl: tvl-up

logs:
	$(dashboards_command) logs -f -t $(ethereum_containers_lite) $(fantom_containers_lite) $(arbitrum_containers_lite) $(gnosis_containers_lite) $(optimism_containers_lite)

logs-all:
	$(dashboards_command) logs -f -t $(ethereum_containers) $(fantom_containers) $(arbitrum_containers) $(gnosis_containers) $(optimism_containers)
	
all:
	$(dashboards_command) down && $(dashboards_command) build --no-cache && $(dashboards_command) up $(flags)

# More advanced control
dashboards-up:
	$(dashboards_command) up $(flags)

dashboards-down:
	$(dashboards_command) down

dashboards-build:
	$(dashboards_command) build $(BUILD_FLAGS)

tvl-up:
	$(tvl_command) up $(flags)

tvl-down:
	$(tvl_command) down

tvl-build:
	$(tvl_command) build $(BUILD_FLAGS)

up: dashboards-up
build: dashboards-build
down: dashboards-down

# Maintenance
rebuild: down build up
scratch: clean-volumes build up

dashboards-clean-volumes:
	$(dashboards_command) down -v
	
tvl-clean-volumes:
	$(tvl_command) down -v

clean-cache: dashboards-clean-cache

postgres:
	$(dashboards_command) up -d --build postgres


# Mainnet:
mainnet:
	$(dashboards_command) up -d --build $(ethereum_containers) && make logs-mainnet

logs-mainnet:
	$(dashboards_command) logs -ft $(ethereum_containers_lite)

stop-mainnet:
	$(dashboards_command) stop $(ethereum_containers) && $(dashboards_command) rm $(ethereum_containers)

eth:
	make mainnet

logs-eth:
	make logs-mainnet

stop-eth:
	make stop-mainnet


# Fantom:
fantom:
	$(dashboards_command) up -d --build $(fantom_containers) && make logs-fantom

logs-fantom:
	$(dashboards_command) logs -ft $(fantom_containers_lite)

stop-fantom:
	$(dashboards_command) down $(fantom_containers) && $(dashboards_command) rm $(fantom_containers)


# Gnosis chain:
gnosis:
	$(dashboards_command) up -d --build $(gnosis_containers) && make logs-gnosis

logs-gnosis:
	$(dashboards_command) logs -ft $(gnosis_containers_lite)

stop-gnosis:
	$(dashboards_command) stop $(gnosis_containers) && $(dashboards_command) rm $(gnosis_containers)


# Arbitrum Chain
arbitrum:
	$(dashboards_command) up -d --build $(arbitrum_containers) && make logs-arbitrum

logs-arbitrum:
	$(dashboards_command) logs -ft $(arbitrum_containers_lite)

stop-arbitrum:
	$(dashboards_command) stop $(arbitrum_containers) && $(dashboards_command) rm $(arbitrum_containers)


# Optimism Chain
optimism:
	$(dashboards_command) up -d --build $(optimism_containers) && make logs-optimism

logs-optimism:
	$(dashboards_command) logs -ft $(optimism_containers_lite)

stop-optimism:
	$(dashboards_command) down $(optimism_containers) && $(all_command) rm $(optimism_containers)


# Treasury Exporters
treasury:
	$(dashboards_command) up -d --build $(treasury_containers) && make logs-treasury

# Treasury TX Exporters
treasury-tx:
	$(dashboards_command) up -d --build $(treasury_tx_containers) && make logs-treasury-tx

logs-treasury:
	$(dashboards_command) logs -ft $(treasury_containers)

logs-treasury-tx:
	$(dashboards_command) logs -ft $(treasury_tx_containers)
