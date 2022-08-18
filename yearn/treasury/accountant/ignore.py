from brownie.exceptions import RPCRequestError
from brownie import ZERO_ADDRESS, chain
from yearn.prices import constants
from yearn.entities import TreasuryTx
from yearn.networks import Network
from yearn.treasury.accountant.classes import HashMatcher, TopLevelTxGroup, IterFilter
from yearn.treasury.accountant.fees import treasury, v1, v2
from yearn.utils import contract

IGNORE_LABEL = "Ignore"

ignore = TopLevelTxGroup(IGNORE_LABEL)

vaults = (v1.vaults + v2.vaults) if v1 else v2.vaults

def is_vault_deposit(tx: TreasuryTx) -> bool:

    # vault side
    if any(tx.token.address.address == vault.vault.address for vault in vaults):
        events = chain.get_transaction(tx.hash).events
        if 'Transfer' not in events:
            return False
        
        for event in events["Transfer"]:
            sender, receiver, value = event.values()
            if event.address == tx.token.address.address and sender == ZERO_ADDRESS and receiver in treasury.addresses:
                underlying = tx.token.address.address
                for _event in events["Transfer"]:
                    _sender, _receiver, _value = _event.values()
                    if _event.address == underlying and _sender == tx.to_address.address and event.pos < _event.pos and _receiver == tx.token.address.address:
                        return True

    # token side
    for vault in vaults:
        if tx.token.address.address == vault.token.address:
            events = chain.get_transaction(tx.hash).events
            if "Transfer" not in events:
                return False

            for event in events["Transfer"]:
                sender, receiver, value = event.values()
                if event.address == tx.token.address.address and sender in treasury.addresses and receiver == vault.vault.address:
                    for _event in events["Transfer"]:
                        _sender, _receiver, _value = _event.values()
                        if _event.address == vault.vault.address and _sender == ZERO_ADDRESS and _receiver in treasury.addresses and _event.pos < event.pos:
                            return True

def is_vault_withdrawal(tx: TreasuryTx) -> bool:
    if not tx.to_address or tx.to_address.address not in treasury.addresses + [ZERO_ADDRESS]:
        return False

    # vault side
    if any(tx.token.address.address == vault.vault.address for vault in vaults):
        events = chain.get_transaction(tx.hash).events
        if 'Transfer' not in events:
            return False

        for event in events['Transfer']:
            sender, receiver, value = event.values()
            if event.address == tx.token.address.address and receiver == ZERO_ADDRESS:
                underlying = contract(tx.token.address.address).token()
                for _event in events['Transfer']:
                    _sender, _receiver, _value = _event.values()
                    print(_event.__dir__())
                    if _event.address == underlying and _receiver == tx.from_address.address and event.pos < _event.pos and _sender == tx.token.address.address:
                        return True
    # token side
    for vault in vaults:
        if tx.token.address.address == vault.token.address:
            events = chain.get_transaction(tx.hash).events
            if "Transfer" not in events:
                continue

            for event in events["Transfer"]:
                sender, receiver, value = event.values()
                if event.address == tx.token.address.address and sender == vault.vault.address:
                    for _event in events["Transfer"]:
                        _sender, _receiver, _value = _event.values()
                        if _event.address == vault.vault.address and _receiver == ZERO_ADDRESS and _sender in treasury.addresses and _event.pos < event.pos:
                            return True

def is_curve_deposit(tx: TreasuryTx) -> bool:
    if tx.from_address.address != ZERO_ADDRESS:
        return False

def is_curve_withdrawal(tx: TreasuryTx) -> bool:
    if not tx.to_address or tx.to_address.address != ZERO_ADDRESS:
        return False
    if 'crv' not in tx.token.symbol.lower() or 'curve' not in tx.token.name.lower():
        return False
    events = chain.get_transaction(tx.hash).events
    if 'RemoveLiquidityOne' not in events:
        return False
    for event in events['RemoveLiquidityOne']:
        if round(float(tx.amount),15) == round(event['token_amount'],15) and contract(event.address).lp_token() == tx.token.address.address:
            return True

def is_internal_transfer(tx: TreasuryTx) -> bool:
    return tx.to_address and tx.to_address.address in treasury.addresses and tx.from_address.address in treasury.addresses

def is_kp3r(tx: TreasuryTx) -> bool:
    contract_names = [
        'Keep3rEscrow',
        'OracleBondedKeeper',
        'Keep3rLiquidityManager',
    ]

    hashes = [
        '0x3efaafc34054dbc50871abef5e90a040688fbddc51ec4c8c45691fb2f21fd495'
    ]

    try:
        return (
            (
                tx.to_address and tx.to_address.token and tx.to_address.token.symbol == 'KP3R'
            )
            or (
                tx.to_address and tx.to_address.is_contract
                and contract(tx.to_address.address)._build['contractName'] in contract_names
            )
            or (
                tx.from_address.is_contract
                and contract(tx.from_address.address)._build['contractName'] in contract_names
            )
            or HashMatcher(hashes).contains(tx)
        )
    except ValueError as e:
        if not str(e).endswith('has not been verified') and "Contract source code not verified" not in str(e):
            raise
        return False

def is_gnosis_execution(tx: TreasuryTx) -> bool:
    if (
        tx.amount == 0
        and tx.to_address
        and tx.to_address.address in treasury.addresses
        ):
        try:
            con = contract(tx.to_address.address)
        except ValueError as e:
            if "contract source code not verified" in str(e).lower() or str(e).endswith('has not been verified'):
                return False
            raise

        if con._build['contractName'] != "GnosisSafeProxy":
            return False
        
        _tx = chain.get_transaction(tx.hash)
        if _tx.status == 0: # Reverted
            return True
        try:
            events = chain.get_transaction(tx.hash).events
        except RPCRequestError:
            return False
        if "ExecutionSuccess" in events:
            return True

def has_amount_zero(tx: TreasuryTx) -> bool:
    return tx.amount == 0

def is_reaper_withdrawal(tx: TreasuryTx) -> bool:
    '''
    # vault side
    if tx.from_address.address in treasury.addresses and tx.to_address and tx.to_address.address == ZERO_ADDRESS and tx.token.symbol.startswith('rv'):
        events = chain.get_transaction(tx.hash).events
        if 'Transfer' not in events:
            return False
            for event in events['Transfer']:
                sender, receiver, value = event.values()
                if event.address == tx.token.address.address and receiver == ZERO_ADDRESS:
                    underlying = contract(tx.token.address.address).token()
                    for _event in events['Transfer']:
                        _sender, _receiver, _value = _event.values()
                        if _event.address == underlying and _receiver == tx.from_address.address and event.pos < _event.pos and _sender == tx.token.address.address:
                            return True
    # token side
    if tx.from_address.token and "Robovault" in tx.from_address.token.symbol:
        try:
            vault = contract(tx.from_address.address)
        except ValueError as e:
            if "not verified" in str(e).lower():
                return False
            raise
        if vault.token() == tx.token.address.address:
            return True
    ...

    '''
    hashes = [
        ["0x84b64365e647e8c9c44b12819e8b7af02d5595933853c3da3eb43fc6f8ef3112",IterFilter('log_index',[8,12,16,74,78,82,86,73,7,11,77,81,15,85])],
        ["0xf68dee68d36eac87430f5238a520ae209650ddeea4b09ebe29af1b00623f1148",IterFilter('log_index',[19,27,7,26,11,23,15,22,14,2,6,10,18,3])]
    ]

    if HashMatcher(hashes).contains(tx):
        return True
    

def is_weth(tx: TreasuryTx) -> bool:
    # Withdrawal
    if tx.from_address.address == ZERO_ADDRESS and tx.to_address and tx.to_address.address in treasury.addresses and tx.token.address.address == constants.weth:
        return True
    if tx.from_address.address in treasury.addresses and tx.to_address and tx.to_address.address == constants.weth and tx.token.address.address == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
        return True
    if tx.from_address.address in treasury.addresses and tx.to_address and tx.to_address.address == ZERO_ADDRESS and tx.token.address.address == constants.weth:
        return True
    if tx.from_address.address == constants.weth and tx.to_address and tx.to_address.address in treasury.addresses and tx.token.address.address == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
        return True

bridged_hashes = {
    Network.Fantom: [
        "0xf6b3d70fed6a472dfda1926e1b509a478e29dcb6c481f32358cafb46d4a1c565",
        "0x034a36cc39d6e75f21ea9624602e503eee826a81e4a29639752c66a3f3e29dbc",
        "0x05005f57f125efc4eb3a7c0e8648ccd8b32e202367e8fc79bc6187eb21cbe51e",
        "0x38a480b47739d311cfb3904887b9f8bd5fcafe471e8dafd1bdbfdf9dfa6db9a4",
        "0xfe6055acfc47d3bedb8a96ff0f25b471c79f26ebea737f8484b4437aa902163a",
        "0xd0840f09e24a7bda2dbb69949dab58dbbf92a571ceb4a2e6180d1426ca59af13",
        "0xbdcc07695c64cd73f3d58a87e20c3a4d9e3353eef5bd31fa9d8d8ade6cfa27b7",
        "0x5a57b259fe5a1ecfea980e7302894ab5954f15eddf4cf075883cd0b6f1568f83",
        "0xebb141d6992dda4d50e12f2ccd9072f59606dca7310fbfd54ef08735dba662d9",
        "0x54d0a847c6789232385d15ec3f7fee9ef0956e0907a68fc8e58b26c9c06b28e6",
        "0x9444e895e2b9142282707150793b42aeb9a4f3d2ece12a642300493e60843964",
        "0xb5ce60d1eeeee6c7a8e93b58e4c275874bf183a1a904820d7544eaa9d79595c1",
        "0x295c026c967d6b1cb9a5309489c6c77fbb95febd6ffea2ac67af3ed6de15cc30",
        "0xb602341eae919f291d9da3d36ab4d412e95afcc76b9ffec443fb6a20eb8f6ccf",
        "0x53df09ce4c930ab941e135ba42f1e8b95338f090dc0fdb05ce5f7510f3be5e31",
        "0xcde638ff75129b49542ce082c0f62ae91e3afedc8ef151e7f512dc8478b40bb3",
        "0x684b5810fc450b76177631ce05f8293bc251e09f6d3a7e9cb536ceeb53802bc1",
        "0x7640eea4d3c43017093a7f77a6b2ac17922700f0bcebc3f08251c0f9522e0efa",
        "0xfe276ef6c9f4915c50623c2944c0bef37b99841a0adba251a0c6ecdf348f5e7b",
    ] 
}.get(chain.id, [])

def is_pass_thru(tx: TreasuryTx) -> bool:
    pass_thru_hashes = {
        Network.Mainnet: [],
        Network.Fantom: [
            "0x411d0aff42c3862d06a0b04b5ffd91f4593a9a8b2685d554fe1fbe5dc7e4fc04",
            "0xf36af9589781de0d2744484b1b1c53195d2c20568177a37712825d1b412063e9",
        ],
    }.get(chain.id, [])

    if tx.hash in pass_thru_hashes and str(tx.log_index).lower() != "nan":
        return True
    
    pass_thru_hashes = {
        Network.Fantom: [
            ["0xf36af9589781de0d2744484b1b1c53195d2c20568177a37712825d1b412063e9",IterFilter('log_index', [4,6,11,16,24])],
        ],
    }.get(chain.id, [])

    if tx in HashMatcher(pass_thru_hashes):
        return True
    

#ignore.create_child("Vault Deposit", is_vault_deposit)
ignore.create_child("Vault Withdrawal", is_vault_withdrawal)
ignore.create_child("Add Curve Liquidity", is_curve_deposit)
ignore.create_child("Remove Curve Liquidity", is_curve_withdrawal)
ignore.create_child("Internal Transfer", is_internal_transfer)
ignore.create_child("Bonding KP3R", is_kp3r)
ignore.create_child("Gnosis Safe Execution", is_gnosis_execution)
#ignore.create_child("Zero Amount Transaction", has_amount_zero)
ignore.create_child("Reaper Vault Withdrawl", is_reaper_withdrawal)
ignore.create_child("Bridged to Other Chain", HashMatcher(bridged_hashes).contains)
ignore.create_child("Wrapping/Unwrapping Gas Tokens",is_weth)
ignore.create_child("Pass-Thru to Vaults", is_pass_thru)
