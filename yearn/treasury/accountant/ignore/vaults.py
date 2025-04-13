
from decimal import Decimal

from brownie import ZERO_ADDRESS, chain
from y import Network

from yearn.iearn import Registry
from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import Filter, HashMatcher, IterFilter
from yearn.treasury.accountant.constants import treasury, v1
from yearn.treasury.accountant.revenue.fees import v2_vaults

vaults = (v1.vaults + v2_vaults) if v1 else v2_vaults
if chain.id == Network.Mainnet:
    iearn = Registry().vaults

def is_vault_deposit(tx: TreasuryTx) -> bool:
    if is_v1_or_v2_vault_deposit(tx):
        return True
    
    # TODO these go thru zaps and do not get caught by the logic above. figure out how to capture these
    zap_hashes = {
        Network.Mainnet: [
            "0x39616fdfc8851e10e17d955f55beea5c3dd4eed7c066a8ecbed8e50b496012ff",
            "0x248e896eb732dfe40a0fa49131717bb7d2c1721743a2945ab9680787abcf9c50",
            "0x2ce0240a08c8cc8d35b018995862711eb660a24d294b1aa674fbc467af4e621b",
        ],
    }.get(chain.id, [])
    
    # TODO Figure out hueristics for ETH deposit to yvWETH
    # TODO build hueristics for v3 vaults - I did this, now just make sure these sort on a fresh pull
    #if tx in HashMatcher({
    #    Network.Mainnet: [
    #        "0x6efac7fb65f187d9aa48d3ae42f3d3a2acdeed3e0b1ded2bb6967cf08c6548a4",
    #        "0xf37fe9e92366f215f97eb223571c0070f8a5195274658496fbc214083be43dbf",
    #        "0x0532f4fbc9b8b105b240f7a37084af6749d30ae03c540191bfb69019c036290c",
    #        ["0x7918a4121636fa06075a08dc1ab499f6e9b6a84f373499d68fc81e5e5cbd0878", Filter('log_index', 109)],
    #        ["0x7b156846ad28b651791dca800b17048afb1bd332078d0cd6507041048d859367", IterFilter('log_index', [473, 474])],
    #        ["0xd7e7abe600aad4a3181a3a410bef2539389579d2ed28f3e75dbbf3a7d8613688", IterFilter('log_index', [532, 533])],
    #        ["0x6c2debddbc13ca7ec2ae434e8f245c59b4286ce95048b57acf96d0e9253f4e8d", IterFilter('log_index', [285, 286])],
    #    ],
    #}.get(chain.id, [])):
    #    return True

    return tx in HashMatcher(zap_hashes) or is_v3_vault_deposit(tx)
    
def is_v1_or_v2_vault_deposit(tx: TreasuryTx) -> bool:
    """ This code doesn't validate amounts but so far that's not been a problem. """
    # vault side
    for vault in vaults:
        if tx.token == vault.vault.address:
            if "Transfer" not in tx._events:
                return False
                
            for event in tx._events["Transfer"]:
                if tx.token == event.address:
                    sender, receiver, value = event.values()
                    if sender == ZERO_ADDRESS and receiver in treasury.addresses:
                        for _event in tx._events["Transfer"]:
                            _sender, _receiver, _value = _event.values()
                            if _event.address == vault.token.address and tx.to_address == _sender and tx.token == _receiver:
                                # v1
                                if _event.pos < event.pos:
                                    return True
                                # v2
                                if event.pos < _event.pos:
                                    return True

    # token side
    for vault in vaults:
        if tx.token == vault.token.address:
            try:
                if "Transfer" not in tx._events:
                    return False
            except KeyError as e:
                # This happens sometimes from a busted abi, shouldnt impact us
                if str(e) == "'components'":
                    return False
                raise

            for event in tx._events["Transfer"]:
                if tx.token == event.address:
                    sender, receiver, value = event.values()
                    if sender in treasury.addresses and receiver == vault.vault.address:
                        for _event in tx._events["Transfer"]:
                            _sender, _receiver, _value = _event.values()
                            if _event.address == vault.vault.address and _sender == ZERO_ADDRESS and _receiver in treasury.addresses:
                                # v1?
                                if event.pos < _event.pos:
                                    return True
                                # v2
                                if _event.pos < event.pos:
                                    return True
    return False

_v3_deposit_keys = 'sender', 'owner', 'assets', 'shares'

def is_v3_vault_deposit(tx: TreasuryTx) -> bool:
    try:
        if "Deposit" not in tx._events:
            return False
    except KeyError as e:
        # This happens sometimes due to a busted abi, shouldnt impact us
        if str(e) == "'components'":
            return False
        raise

    if deposits := [event for event in tx._events['Deposit'] if all(key in event for key in _v3_deposit_keys)]:
        # Vault side
        if tx.from_address == ZERO_ADDRESS:
            for deposit in deposits:
                if tx.token != deposit.address:
                    continue
                if tx.to_address != deposit['owner']:
                    print('wrong owner')
                    continue
                elif tx.amount == Decimal(deposit['shares']) / tx.token.scale:
                    return True
                print('wrong amount')
            print('no matching deposit')
        
        # Token side
        else:
            for deposit in deposits:
                if tx.to_address != deposit.address:
                    continue
                if tx.from_address != deposit['sender']:
                    print('sender doesnt match')
                    continue
                if tx.amount == Decimal(deposit['assets']) / tx.token.scale:
                    return True
                print('amount doesnt match')
    return False

def is_iearn_withdrawal(tx: TreasuryTx) -> bool:
    # Vault side
    if tx.to_address == ZERO_ADDRESS:
        return any(tx.token == earn.vault.address for earn in iearn)
    # Token side
    return any(tx.from_address == earn.vault.address and tx.token == earn.token for earn in iearn)
    
def is_vault_withdrawal(tx: TreasuryTx) -> bool:
    # This is a strange tx that won't sort the usual way and isn't worth determining sorting hueristics for.
    if tx in HashMatcher({
        Network.Mainnet: (
            "0xfa8652a888039183770ae766b855160c5e962b2963745ba0b67334dae9605348",
            ("0x6b3ede4a134198ab6139d019be3c303755aaa5c0502ba6e469adb934471fe23f", IterFilter('log_index', (291, 292))),
            ("0x6a1996554455945f9ba5f58b831c86f9afaeb1a5c36b9166099a7d3ac0106803", Filter('log_index', 388)),
            ("0xe94b63c325861d615a773e8baba7521293c739927e23d0227405714a88e6f567", Filter('log_index', 496)),
            ("0xebe8d138728be8f0b7fdce7614a6be4c161f38bd2b63221b55071b6ddc52d280", Filter('log_index', 520)),
            ("0xd0fa31ccf6bf7577a533366955bb528d6d17c928bba1ff13ab273487a27d9602", Filter('log_index', 253)),
            ("0xae7d281b8a093da60d39179452d230de2f1da4355df3aea629d969782708da5d", Filter('log_index', 283)),
            ("0x3efe08a7dc37ad120d61eb52d7ffcec5e2699f62ee1bd9bd55ece3dfb7ec4441", IterFilter('log_index', (385, 393))),
            ("0xd55f6cedd7a08d91f99e8ceb384ffd0892f3dbee450879af33d54dda5bd18915", IterFilter('log_index', (26, 75))),
        ),
    }.get(chain.id, ())):
        return True

    if tx.to_address not in list(treasury.addresses) + [ZERO_ADDRESS]:
        return False
        
    try:
        if 'Transfer' not in tx._events:
            return False
    except KeyError as e:
        if str(e) == "'components'":
            return False
        raise

    # vault side
    if any(tx.token == vault.vault.address for vault in vaults):
        for event in tx._events['Transfer']:
            if tx.token == event.address:
                sender, receiver, value = event.values()
                if tx.to_address == ZERO_ADDRESS == receiver and sender in treasury.addresses and tx.from_address == sender:
                    underlying = tx.token.contract.token()
                    for _event in tx._events['Transfer']:
                        _sender, _receiver, _value = _event.values()
                        if _event.address == underlying and tx.from_address == _receiver and event.pos < _event.pos and tx.token == _sender:
                            return True
    # token side
    for vault in vaults:
        if tx.token == vault.token.address:
            for event in tx._events["Transfer"]:
                if tx.token == event.address:
                    sender, receiver, value = event.values()
                    if tx.from_address == vault.vault.address == sender and tx.to_address == receiver:
                        for _event in tx._events["Transfer"]:
                            _sender, _receiver, _value = _event.values()
                            if _event.address == vault.vault.address and _receiver == ZERO_ADDRESS and _sender in treasury.addresses and tx.to_address == _sender and _event.pos < event.pos:
                                return True
    return False

def is_dolla_fed_withdrawal(tx: TreasuryTx) -> bool:
    if tx._from_nickname == 'Token: Curve DOLA Pool yVault - Unlisted' and tx.to_address.address in treasury.addresses and tx._symbol == "DOLA3POOL3CRV-f":
        return True
    elif tx.from_address.address in treasury.addresses and tx.to_address == ZERO_ADDRESS and tx._symbol == "yvCurve-DOLA-U":
        return True
    return False

def is_dola_frax_withdrawal(tx: TreasuryTx) -> bool:
    if tx._symbol == "yvCurve-DOLA-FRAXBP-U" and tx._from_nickname == "Yearn yChad Multisig" and tx._to_nickname == "Zero Address":
        return True
    elif tx._symbol == "DOLAFRAXBP3CRV-f" and tx._from_nickname == "Token: Curve DOLA-FRAXBP Pool yVault - Unlisted" and tx._to_nickname == "Yearn yChad Multisig":
        return True
    return tx in HashMatcher([
        ["0x59a3a3b9e724835958eab6d0956a3acf697191182c41403c96d39976047d7240", Filter('log_index', 232)]
    ])
