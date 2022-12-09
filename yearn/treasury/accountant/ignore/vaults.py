
import asyncio

from brownie import ZERO_ADDRESS, chain
from multicall.utils import await_awaitable
from y.networks import Network

from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import HashMatcher
from yearn.treasury.accountant.constants import treasury, v1, v2
from yearn.utils import contract

vaults = await_awaitable(v2.vaults)
if v1:
    vaults += v1.vaults

def is_vault_deposit(tx: TreasuryTx) -> bool:
    """ This code doesn't validate amounts but so far that's not been a problem. """

    # vault side
    for vault in vaults:
        if tx.token.address.address == vault.vault.address:
            if "Transfer" not in tx._events:
                return False
                
            for event in tx._events["Transfer"]:
                sender, receiver, value = event.values()
                if event.address == tx.token.address.address and sender == ZERO_ADDRESS and receiver in treasury.addresses:
                    for _event in tx._events["Transfer"]:
                        _sender, _receiver, _value = _event.values()
                        if _event.address == vault.token.address and _sender == tx.to_address.address and _receiver == tx.token.address.address:
                            # v1
                            if _event.pos < event.pos:
                                return True
                            # v2
                            if event.pos < _event.pos:
                                return True

    # token side
    for vault in vaults:
        if tx.token.address.address == vault.token.address:
            if "Transfer" not in tx._events:
                return False

            for event in tx._events["Transfer"]:
                sender, receiver, value = event.values()
                if event.address == tx.token.address.address and sender in treasury.addresses and receiver == vault.vault.address:
                    for _event in tx._events["Transfer"]:
                        _sender, _receiver, _value = _event.values()
                        if _event.address == vault.vault.address and _sender == ZERO_ADDRESS and _receiver in treasury.addresses:
                            # v1?
                            if event.pos < _event.pos:
                                return True
                            # v2
                            if _event.pos < event.pos:
                                return True

    # DEV these go thru zaps and do not get caught by the logic above. figure out how to capture these
    hashes = {
        Network.Mainnet: [
            "0x39616fdfc8851e10e17d955f55beea5c3dd4eed7c066a8ecbed8e50b496012ff",
            "0x248e896eb732dfe40a0fa49131717bb7d2c1721743a2945ab9680787abcf9c50",
            "0x2ce0240a08c8cc8d35b018995862711eb660a24d294b1aa674fbc467af4e621b",
        ],
    }.get(chain.id, [])

    if tx in HashMatcher(hashes):
        return True
    
    # TODO Figure out hueristics for ETH deposit to yvWETH
    return tx in HashMatcher({
        Network.Mainnet: [
            "0x6efac7fb65f187d9aa48d3ae42f3d3a2acdeed3e0b1ded2bb6967cf08c6548a4",
            "0xf37fe9e92366f215f97eb223571c0070f8a5195274658496fbc214083be43dbf",
        ],
    }.get(chain.id, []))

def is_vault_withdrawal(tx: TreasuryTx) -> bool:

    # This is a strange tx that won't sort the usual way and isn't worth determining sorting hueristics for.
    if tx in HashMatcher({
        Network.Mainnet: [
            "0xfa8652a888039183770ae766b855160c5e962b2963745ba0b67334dae9605348",
        ],
    }.get(chain.id, [])):
        return True

    if not tx.to_address or tx.to_address.address not in list(treasury.addresses) + [ZERO_ADDRESS]:
        return False

    # vault side
    if any(tx.token.address.address == vault.vault.address for vault in vaults):
        if 'Transfer' in tx._events:
            for event in tx._events['Transfer']:
                sender, receiver, value = event.values()
                if event.address == tx.token.address.address and receiver == ZERO_ADDRESS == tx.to_address.address and sender in treasury.addresses and sender == tx.from_address.address:
                    underlying = contract(tx.token.address.address).token()
                    for _event in tx._events['Transfer']:
                        _sender, _receiver, _value = _event.values()
                        if _event.address == underlying and _receiver == tx.from_address.address and event.pos < _event.pos and _sender == tx.token.address.address:
                            return True
    # token side
    for vault in vaults:
        if tx.token.address.address == vault.token.address and "Transfer" in tx._events:
            for event in tx._events["Transfer"]:
                sender, receiver, value = event.values()
                if event.address == tx.token.address.address and sender == vault.vault.address == tx.from_address.address and receiver == tx.to_address.address:
                    for _event in tx._events["Transfer"]:
                        _sender, _receiver, _value = _event.values()
                        if _event.address == vault.vault.address and _receiver == ZERO_ADDRESS and _sender in treasury.addresses and _sender == tx.to_address.address and _event.pos < event.pos:
                            return True

def is_dolla_fed_withdrawal(tx: TreasuryTx) -> bool:
    if tx._from_nickname == 'Token: Curve DOLA Pool yVault - Unlisted' and tx.to_address.address in treasury.addresses and tx._symbol == "DOLA3POOL3CRV-f":
        return True
    elif tx.from_address.address in treasury.addresses and tx.to_address and tx.to_address.address == ZERO_ADDRESS and tx._symbol == "yvCurve-DOLA-U":
        return True
