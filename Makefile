flags := --remove-orphans --detach
ifdef FLAGS
	flags += $(FLAGS)
endif

dashboards_command := docker-compose --file services/dashboard/docker-compose.yml --project-directory .
tvl_command := docker-compose --file services/tvl/docker-compose.yml --project-directory .

dashboards-up:
	$(dashboards_command) up $(flags)

dashboards-down:
	$(dashboards_command) down

dashboards-build:
	$(dashboards_command) build --no-cache

dashboards-clean-volumes:
	$(dashboards_command) down -v

dashboards-clean-cache:
	docker volume rm yearn-exporter_cache

tvl-up:
	$(tvl_command) up $(flags)

tvl-down:
	$(tvl_command) down

tvl-build:
	$(tvl_command) build --no-cache

tvl-clean-volumes:
	$(tvl_command) down -v

clean-volumes: dashboards-clean-volumes tvl-clean-volumes

dashboards: dashboards-up
tvl: tvl-up

up: dashboards-up
build: dashboards-build
down: dashboards-down

clean-cache: dashboards-clean-cache
clean-volumes: dashboards-clean-volumes

rebuild: down build up
scratch: clean-volumes build up

logs:
	$(dashboards_command) logs -f -t