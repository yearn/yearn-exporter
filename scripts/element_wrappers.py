from web3 import Web3
from brownie import *
from yearn.partners.snapshot import Wrapper
from yearn.utils import contract

def main():

    registry = contract('0x149f615057F905988fFC97994E29c0Cc7DaB5337')
    wrapper_addresses = registry.functions.viewRegistry().call()
    wrappers = []

    for wrapper in wrapper_addresses:
        vault = contract(wrapper).vault()
        wrappers.append(
            Wrapper(
                name=contract(wrapper).name(),
                vault=vault,
                wrapper=wrapper,
            )
        )
    print(wrappers)
