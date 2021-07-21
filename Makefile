flags := --remove-orphans --detach
ifdef FLAGS
	flags += $(FLAGS)
endif

dashboards_command := docker-compose --file services/dashboard/docker-compose.yml --project-directory .
tvl_command := docker-compose --file services/tvl/docker-compose.yml --project-directory .

# general
build-docker:
	docker build -t ghcr.io/yearn/yearn-exporter . --no-cache

# dashboards
up:
	$(dashboards_command) up $(flags)

down:
	$(dashboards_command) down

clean-volumes:
	$(dashboards_command) down -v

clean-cache: down
	docker volume rm yearn-exporter_cache

dashboards: up

rebuild: down build-docker up

restart: down up

fresh: clean-volumes build-docker up

# tvl
tvl-up:
	$(tvl_command) up $(flags)

tvl-down:
	$(tvl_command) down

tvl-clean-volumes:
	$(tvl_command) down -v

tvl: tvl-up
