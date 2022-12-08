import logging
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Callable, List, Optional, Union

from brownie import Contract, chain
from brownie.convert.datatypes import EthAddress
from brownie.network.contract import ContractContainer
from cachetools.func import ttl_cache
from y.networks import Network

from yearn.exceptions import UnsupportedNetwork
from yearn.prices.constants import usdc, weth
from yearn.typing import Address, AddressOrContract, Block
from yearn.utils import Singleton, contract

logger = logging.getLogger(__name__)


def get_fantom_ironbank() -> Contract:
    # HACK ironbank on fantom uses a non-standard proxy pattern
    unitroller = contract('0x4250A6D3BD57455d7C6821eECb6206F507576cD2')
    implementation = contract(unitroller.comptrollerImplementation())
    return Contract.from_abi(unitroller._name, str(unitroller), abi=implementation.abi)

def get_fantom_scream() -> Contract:
    # HACK ironbank on fantom uses a non-standard proxy pattern
    unitroller = contract('0x260e596dabe3afc463e75b6cc05d8c46acacfb09')
    implementation = contract(unitroller.comptrollerImplementation())
    return Contract.from_abi(unitroller._name, str(unitroller), abi=implementation.abi)


@dataclass
class CompoundConfig:
    name: str
    address: Union[Address, Callable[[], ContractContainer]]
    oracle_base: Address = usdc


addresses = {
    Network.Mainnet: [
        CompoundConfig(
            name='compound',
            address='0x3d9819210A31b4961b30EF54bE2aeD79B9c9Cd3B',
        ),
        CompoundConfig(
            name='cream',
            address='0x3d5BC3c8d13dcB8bF317092d84783c2697AE9258',
            oracle_base=weth,
        ),
        CompoundConfig(
            name='ironbank',
            address='0xAB1c342C7bf5Ec5F02ADEA1c2270670bCa144CbB',
        ),
    ],
    Network.Fantom: [
        CompoundConfig(
            name='ironbank',
            address=get_fantom_ironbank,
        ),
        CompoundConfig(
            name='scream',
            address=get_fantom_scream,
        )
    ],
    Network.Arbitrum: [
        CompoundConfig(
            name='ironbank',
            address='0xbadaC56c9aca307079e8B8FC699987AAc89813ee',
        ),
    ],
    Network.Optimism: [
        CompoundConfig(
            name='ironbank',
            address='0xE0B57FEEd45e7D908f2d0DaCd26F113Cf26715BF',
        )
    ],
}


@dataclass
class CompoundMarket:
    token: Address
    unitroller: ContractContainer

    @cached_property
    def name(self) -> str:
        return self.ctoken.symbol()

    @cached_property
    def ctoken(self) -> Contract:
        return contract(self.token)

    @cached_property
    def underlying(self) -> Contract:
        # ceth, creth -> weth
        if self.token in ['0x4Ddc2D193948926D02f9B1fE9e1daa0718270ED5', '0xD06527D5e56A3495252A528C4987003b712860eE']:
            return contract('0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2')

        return contract(self.ctoken.underlying())

    @cached_property
    def cdecimals(self) -> int:
        return self.ctoken.decimals()

    @cached_property
    def under_decimals(self) -> int:
        return self.underlying.decimals()

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            return self.token == other
        elif isinstance(other, CompoundMarket):
            return self.token == other.token

        raise TypeError('can only compare to [str, CompoundMarket]')

    def get_exchange_rate(self, block: Optional[Block] = None) -> float:
        exchange_rate = (
            self.ctoken.exchangeRateCurrent.call(block_identifier=block) / 1e18
        )
        return exchange_rate * 10 ** (self.cdecimals - self.under_decimals)

    def get_underlying_price(self, block: Optional[Block] = None) -> float:
        # query the oracle in case it was changed
        oracle = contract(self.unitroller.oracle(block_identifier=block))
        price = oracle.getUnderlyingPrice(
            self.token, block_identifier=block
        ) / 10 ** (36 - self.under_decimals)
        return price


class Compound:
    def __init__(self, name: str, unitroller: Address, oracle_base: Address) -> None:
        self.name = name
        self.unitroller = contract(unitroller) if isinstance(unitroller, str) else unitroller()
        self.oracle_base = oracle_base
        self.markets  # load markets on init

    def __repr__(self) -> str:
        return f'<Compound name={self.name} unitroller={self.unitroller}>'

    @property
    @ttl_cache(ttl=3600)
    def markets(self) -> List[CompoundMarket]:
        all_markets = self.unitroller.getAllMarkets()
        markets = [CompoundMarket(token, self.unitroller) for token in all_markets]
        logger.info(f'loaded {len(markets)} {self.name} markets')
        return markets

    def get_price(self, token: AddressOrContract, block: Optional[Block] = None) -> Union[float,List[Union[float,str]]]:
        market = next(x for x in self.markets if x == token)
        exchange_rate = market.get_exchange_rate(block)
        underlying_price = market.get_underlying_price(block)
        if self.oracle_base == usdc:
            return underlying_price * exchange_rate
        else:
            return [underlying_price * exchange_rate, self.oracle_base]


class CompoundMultiplexer(metaclass=Singleton):
    def __init__(self) -> None:
        if chain.id not in addresses:
            raise UnsupportedNetwork('compound is not supported on this network')
        self.compounds = [
            Compound(conf.name, conf.address, conf.oracle_base)
            for conf in addresses[chain.id]
        ]

    def __contains__(self, token: AddressOrContract) -> bool:
        if isinstance(token, EthAddress):
            # Must convert in order to compare to CompoundMarket.
            token = str(token)
        return any(token in comp.markets for comp in self.compounds)

    def get_price(self, token: AddressOrContract, block: Optional[Block] = None) -> float:
        comp = next(comp for comp in self.compounds if token in comp.markets)
        return comp.get_price(token, block)


compound = None
try:
    compound = CompoundMultiplexer()
except UnsupportedNetwork:
    pass
