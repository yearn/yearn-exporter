from typing import List, Literal, Union

from brownie import Contract
from brownie.convert.datatypes import EthAddress, HexBytes
from eth_typing import AnyAddress, BlockNumber

VaultVersion = Literal['v1','v2']

AddressString = str
Address = Union[str,HexBytes,AnyAddress,EthAddress]
AddressOrContract = Union[Address,Contract]

Block = Union[int,BlockNumber]

Topic = Union[str,HexBytes,None]
Topics = List[Union[Topic,List[Topic]]]
