from typing import Dict, Optional

from brownie import chain, web3
from brownie.convert.datatypes import EthAddress
from cachetools.func import ttl_cache

from yearn.exceptions import UnsupportedNetwork
from yearn.multicall2 import fetch_multicall
from yearn.networks import Network
from yearn.typing import AddressOrContract
from yearn.utils import Singleton, contract, _resolve_proxy

address_providers = {
    Network.Mainnet: {
        # https://docs.aave.com/developers/v/1.0/deployed-contracts/deployed-contract-instances
        'v1': '0x24a42fD28C976A61Df5D00D0599C34c4f90748c8',
        # https://docs.aave.com/developers/deployed-contracts/deployed-contracts
        'v2': '0xB53C1a33016B2DC2fF3653530bfF1848a515c8c5',
    },
    Network.Fantom: {
        # https://docs.geist.finance/useful-info/deployments-addresses
        'v2': '0x6c793c628Fe2b480c5e6FB7957dDa4b9291F9c9b',
    },
}


class Aave(metaclass=Singleton):
    def __init__(self) -> None:
        if chain.id not in address_providers:
            raise UnsupportedNetwork("aave is not supported on this network")

    def __contains__(self, token: AddressOrContract) -> bool:
        return token in self.markets

    def atoken_underlying(self, atoken: AddressOrContract) -> Optional[EthAddress]:
        return self.markets.get(atoken)

    @property
    @ttl_cache(ttl=3600)
    def markets(self) -> Dict[EthAddress,EthAddress]:
        atoken_to_token = {}
        for version, provider in address_providers[chain.id].items():
            lending_pool, tokens = self.get_tokens(contract(contract(provider).getLendingPool()), version)

            reserves = fetch_multicall(
                *[[lending_pool, 'getReserveData', token] for token in tokens]
            )
            atoken_to_token.update({
                reserve['aTokenAddress']: token
                for token, reserve in zip(tokens, reserves)
            })

        return atoken_to_token


    def get_tokens(self, lending_pool, version):
        fns_by_version = {"v1": "Reserves", "v2": "getReservesList"}
        if version not in fns_by_version:
            raise ValueError(f'unsupported aave version {version}')
        fn = fns_by_version[version]
        if not hasattr(lending_pool, fn):
            lending_pool = _resolve_proxy(str(lending_pool))
        tokens = getattr(lending_pool, fn)()
        return lending_pool, tokens

aave = None
try:
    aave = Aave()
except UnsupportedNetwork:
    pass
