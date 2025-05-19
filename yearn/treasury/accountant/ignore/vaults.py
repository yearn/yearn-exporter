from brownie import ZERO_ADDRESS
from y import Network
from y.constants import CHAINID

from yearn.iearn import Registry
from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import Filter, HashMatcher, IterFilter
from yearn.treasury.accountant.constants import treasury, v1
from yearn.treasury.accountant.revenue.fees import v2_vaults

vaults = (v1.vaults + v2_vaults) if v1 else v2_vaults
if CHAINID == Network.Mainnet:
    iearn = Registry().vaults

treasury_addresses = treasury.addresses

# TODO these go thru zaps and do not get caught by the logic below. figure out how to capture these
ZAP_HASHES = HashMatcher({
    Network.Mainnet: (
        "0x39616fdfc8851e10e17d955f55beea5c3dd4eed7c066a8ecbed8e50b496012ff",
        "0x248e896eb732dfe40a0fa49131717bb7d2c1721743a2945ab9680787abcf9c50",
        "0x2ce0240a08c8cc8d35b018995862711eb660a24d294b1aa674fbc467af4e621b",
        # this is not thru a zap, its a lp-yCRVv2 deposit I probably dont need ot write hueristics for
        "0x93cf055d82b7e82b3877ab506629de6359fc5385ffb6b8c2fbfe0d61947fab59",
    ),
}.get(CHAINID, ()))

def is_vault_deposit(tx: TreasuryTx) -> bool:
    return is_v1_or_v2_vault_deposit(tx) or tx in ZAP_HASHES or is_v3_vault_deposit(tx)
    
def is_v1_or_v2_vault_deposit(tx: TreasuryTx) -> bool:
    """ This code doesn't validate amounts but so far that's not been a problem. """
    try:
        if "Transfer" not in tx._events:
            return False
    except KeyError as e:
        # This happens sometimes from a busted abi, shouldnt impact us
        if str(e) == "'components'":
            return False
        raise

    transfer_events = tx._events["Transfer"]

    tx_token = tx.token

    # vault side
    for vault in vaults:
        if tx_token == vault.vault.address:
            for event in transfer_events:
                if tx_token == event.address:
                    event_pos = event.pos
                    sender, receiver, value = event.values()
                    if sender == ZERO_ADDRESS and receiver in treasury_addresses:
                        tx_to_address = tx.to_address
                        underlying_address = vault.token.address
                        for _event in transfer_events:
                            _sender, _receiver, _value = _event.values()
                            if _event.address == underlying_address and tx_to_address == _sender and tx_token == _receiver:
                                # v1
                                if _event.pos < event_pos:
                                    return True
                                # v2
                                if event_pos < _event.pos:
                                    return True

    # token side
    for vault in vaults:
        if tx_token == vault.token.address:
            for event in transfer_events:
                if tx_token == event.address:
                    vault_address = vault.vault.address
                    event_pos = event.pos
                    sender, receiver, value = event.values()
                    if sender in treasury_addresses and receiver == vault_address:
                        for _event in transfer_events:
                            _sender, _receiver, _value = _event.values()
                            if _event.address == vault_address and _sender == ZERO_ADDRESS and _receiver in treasury_addresses:
                                # v1?
                                if event_pos < _event.pos:
                                    return True
                                # v2
                                if _event.pos < event_pos:
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
                elif tx.amount == tx.token.scale_value(deposit['shares']):
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
                if tx.amount == tx.token.scale_value(deposit['assets']):
                    return True
                print('amount doesnt match')
    return False

def is_iearn_withdrawal(tx: TreasuryTx) -> bool:
    # Vault side
    if tx.to_address == ZERO_ADDRESS:
        return any(tx.token == earn.vault.address for earn in iearn)
    # Token side
    return any(tx.from_address == earn.vault.address and tx.token == earn.token for earn in iearn)
    
TREASURY_AND_ZERO = {*treasury_addresses, ZERO_ADDRESS}

WITHDRAWAL_HASHES = HashMatcher({
    Network.Mainnet: (
        # some of these are v3, TODO build v3 hueristics
        # This is a strange tx that won't sort the usual way and isn't worth determining sorting hueristics for.
        "0xfa8652a888039183770ae766b855160c5e962b2963745ba0b67334dae9605348",
        ("0x6b3ede4a134198ab6139d019be3c303755aaa5c0502ba6e469adb934471fe23f", IterFilter('log_index', (291, 292))),
        ("0x6a1996554455945f9ba5f58b831c86f9afaeb1a5c36b9166099a7d3ac0106803", Filter('log_index', 388)),
        ("0xe94b63c325861d615a773e8baba7521293c739927e23d0227405714a88e6f567", Filter('log_index', 496)),
        ("0xebe8d138728be8f0b7fdce7614a6be4c161f38bd2b63221b55071b6ddc52d280", Filter('log_index', 520)),
        ("0xd0fa31ccf6bf7577a533366955bb528d6d17c928bba1ff13ab273487a27d9602", Filter('log_index', 253)),
        ("0xae7d281b8a093da60d39179452d230de2f1da4355df3aea629d969782708da5d", Filter('log_index', 283)),
        ("0x3efe08a7dc37ad120d61eb52d7ffcec5e2699f62ee1bd9bd55ece3dfb7ec4441", IterFilter('log_index', (385, 393))),
        ("0xd55f6cedd7a08d91f99e8ceb384ffd0892f3dbee450879af33d54dda5bd18915", IterFilter('log_index', (26, 75))),
        ("0x26956f86b3f4e3ff9de2779fb73533f3e1f8ce058493eec312501d0e8053fe7a", Filter("log_index", 162)),
        ("0x831ad751e1be1dbb82cb9e1f5bf0e38e31327b8c58f6ad6b90bcfb396129bb11", Filter("log_index", 416)),
        ("0xf014dc4be2d3b3dad5a1e0e1196a8750683aa54d8d890015d0a7eccd0e41d9b6", IterFilter("log_index", (448, 449))),
        ("0xd35c30664f3241ea2ec3df1c70261086247025eb72c2bc919108dfef9b08a450", Filter("log_index", 52)),
        ("0x85d72c62a8a97a497b62d4895f46a0c90138a96d44f017b914b57a29002c4249", Filter("log_index", 257))
    ),
}.get(CHAINID, ()))

def is_vault_withdrawal(tx: TreasuryTx) -> bool:
    if tx in WITHDRAWAL_HASHES:
        return True

    if tx.to_address not in TREASURY_AND_ZERO:
        return False
        
    try:
        if 'Transfer' not in tx._events:
            return False
    except KeyError as e:
        if str(e) == "'components'":
            return False
        raise

    transfer_events = tx._events["Transfer"]

    # vault side
    if any(tx.token == vault.vault.address for vault in vaults):
        for event in transfer_events:
            if tx.token == event.address:
                sender, receiver, value = event.values()
                if tx.to_address == ZERO_ADDRESS == receiver and sender in treasury_addresses and tx.from_address == sender:
                    underlying = tx.token.contract.token()
                    for _event in transfer_events:
                        _sender, _receiver, _value = _event.values()
                        if _event.address == underlying and tx.from_address == _receiver and event.pos < _event.pos and tx.token == _sender:
                            return True
    # token side
    for vault in vaults:
        if tx.token == vault.token.address:
            vault_address = vault.vault.address
            for event in transfer_events:
                if tx.token == event.address:
                    sender, receiver, value = event.values()
                    if tx.from_address == vault_address == sender and tx.to_address == receiver:
                        for _event in transfer_events:
                            _sender, _receiver, _value = _event.values()
                            if _event.address == vault_address and _receiver == ZERO_ADDRESS and _sender in treasury_addresses and tx.to_address == _sender and _event.pos < event.pos:
                                return True
    return False

def is_dolla_fed_withdrawal(tx: TreasuryTx) -> bool:
    if tx._from_nickname == 'Token: Curve DOLA Pool yVault - Unlisted' and tx.to_address.address in treasury_addresses and tx._symbol == "DOLA3POOL3CRV-f":
        return True
    elif tx.from_address.address in treasury_addresses and tx.to_address == ZERO_ADDRESS and tx._symbol == "yvCurve-DOLA-U":
        return True
    return False


DOLA_FRAX_HASHES = HashMatcher(
    [["0x59a3a3b9e724835958eab6d0956a3acf697191182c41403c96d39976047d7240", Filter('log_index', 232)]],
)

def is_dola_frax_withdrawal(tx: TreasuryTx) -> bool:
    if tx._symbol == "yvCurve-DOLA-FRAXBP-U" and tx._from_nickname == "Yearn yChad Multisig" and tx._to_nickname == "Zero Address":
        return True
    elif tx._symbol == "DOLAFRAXBP3CRV-f" and tx._from_nickname == "Token: Curve DOLA-FRAXBP Pool yVault - Unlisted" and tx._to_nickname == "Yearn yChad Multisig":
        return True
    return tx in DOLA_FRAX_HASHES
