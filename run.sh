#!/usr/bin/env bash
set -e

export DOCKER_DEFAULT_PLATFORM="linux/x86_64"
export GF_SECURITY_ADMIN_USER=admin # change this if you want to have a different admin user name, default is admin
export GF_SECURITY_ADMIN_PASSWORD=admin # change this if you want to have a different admin password, default is admin
export WEB3_PROVIDER=https://eth-mainnet.alchemyapi.io/v2/XLj2FWLNMB4oOfFjbnrkuOCcaBIhipOJ # if this is set, it overrides Infura, and instead a custom url is used as the web3 provider
export ETHERSCAN_TOKEN=SBATAPKE99QBFYZ4BV9YN16HBB9IEEADHV # this needs to be set
make down
make build
make up
