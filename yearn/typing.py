from typing import List, Union

from brownie import Contract
from brownie.convert.datatypes import EthAddress, HexBytes
from eth_typing import AnyAddress, BlockNumber

Address = Union[str,HexBytes,AnyAddress,EthAddress]
AddressOrContract = Union[Address,Contract]

Block = Union[int,BlockNumber]

Topic = Union[str,HexBytes,None]
Topics = List[Union[Topic,List[Topic]]]
