#! /bin/bash
set -e

if [[ -z "${COMMANDS}" ]]; then
  echo "please provide a list of commands to run via \$COMMANDS."
  exit 1
fi

export SENTRY_RELEASE=$(git rev-parse --short HEAD)

IFS=',' read -r -a commands <<< "$COMMANDS"
for CMD in "${commands[@]}"; do
  NAME=$(echo $CMD | sed -e 's/[_/ ]/-/g')
  # TODO handle multiple containers with the same name more gracefully
  CONTAINER_NAME=${PROJECT_PREFIX}-${NAME}-1
  docker rm -f $CONTAINER_NAME 2> /dev/null || true
  docker-compose \
    --file services/dashboard/docker-compose.yml \
    --project-directory . \
    -p $PROJECT_PREFIX run \
    --name $CONTAINER_NAME \
    --detach \
    exporter $CMD
  # hack to manually patch the container docker config so the container is restarted
  # if the docker-compose run failed
  docker container update --restart on-failure $CONTAINER_NAME
done
