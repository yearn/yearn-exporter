#! /bin/bash
set -e

read -p "This will migrate all docker volumes to the new naming scheme. Do you want to proceed? (y/n) " yn

case $yn in
  y ) echo starting migration...;;
  n ) echo exiting;
    exit 0;;
  * ) echo invalid response;
    exit 1;;
esac

rename_volumes () {
  regex=$1
  prefix=$2
  volumes=($(docker volume ls | grep -E $regex | awk '{print $2}' | xargs))
  for from in "${volumes[@]}"; do
    to="$prefix-$from"
    docker volume rm $to &> /dev/null || true
    docker volume create $to
    docker run --rm --name clonevolume -it -v $from:/from -v $to:/to amd64/alpine sh -c "cd /from ; cp -a . /to"
    docker volume rm $from &> /dev/null || true
    echo "Successfully migrated docker volume: $from -> $to"
  done
}

infra_regex="_grafana_data|_postgres_data|_victoria_metrics_data"
rename_volumes $infra_regex "yearn-exporter"

worker_regex="_brownie|_cache"
rename_volumes $worker_regex "yearn-exporter-worker"

docker volume ls
