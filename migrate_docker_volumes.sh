#! /bin/bash
set -e

container_regex="_brownie|_cache|_grafana_data|_postgres_data|_victoria_metrics_data"
volumes=($(docker volume ls | grep -E $container_regex | grep -v yearn-exporter | awk '{print $2}' | xargs))
for from in "${volumes[@]}"; do
  to="yearn-exporter_$from"
  docker volume rm $to &> /dev/null || true
  docker volume create $to
  docker run --rm --name clonevolume -it -v $from:/from -v $to:/to alpine sh -c "cd /from ; cp -a . /to"
  echo "Successfully migrated docker volume: $from -> $to"
done
