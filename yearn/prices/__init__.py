
from brownie import chain, Contract
from yearn.networks import Network
from yearn.utils import contract

# this ensures you have the proper abi for non-verified 0x154eA0E896695824C87985a52230674C2BE7731b on fantom, required for treasury exporter
if chain.id == Network.Fantom:
    good_abi = contract('0xbcab7d083Cf6a01e0DdA9ed7F8a02b47d125e682').abi
    Contract.from_abi('Vyper_contract','0x154eA0E896695824C87985a52230674C2BE7731b',good_abi)
