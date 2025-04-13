
from decimal import Decimal

from brownie import ZERO_ADDRESS, chain
from y import Network, Contract
from y.constants import CHAINID

from yearn.constants import WRAPPED_GAS_COIN
from yearn.entities import TreasuryTx
from yearn.multicall2 import fetch_multicall
from yearn.treasury.accountant.classes import HashMatcher
from yearn.treasury.accountant.constants import treasury
from yearn.treasury.accountant.ignore.swaps.skip_tokens import SKIP_TOKENS

ROUTERS = [
    "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
]

def is_uniswap_deposit(tx: TreasuryTx) -> bool:
    if tx.to_address and "Mint" in tx._events and "Transfer" in tx._events:
        for mint in tx._events["Mint"]:
            event_args = {"sender", "amount0", "amount1"}
            if any(arg not in mint for arg in event_args):
                continue

            # LP token
            if tx.from_address == ZERO_ADDRESS and (
                tx.token == mint.address or
                # KP3R/WETH Uni v3 LP -- used while depositing to kLP-KP3R/WETH
                mint.address == "0x11B7a6bc0259ed6Cf9DB8F499988F9eCc7167bf5"
            ):
                lp = tx.token.contract
                tokens = [lp.token0(), lp.token1()]
                if all(
                    any(token == transfer.address and tx.to_address == transfer.values()[0] and transfer.values()[1] == mint.address for transfer in tx._events["Transfer"])
                    for token in tokens
                ):
                    return True

                # Maybe native asset was used instead of wrapped.
                if tokens[0] == WRAPPED_GAS_COIN:
                    if any(tokens[1] == transfer.address and tx.to_address == transfer.values()[0] == mint['sender'] and transfer.values()[1] == mint.address for transfer in tx._events["Transfer"]):
                        for int_tx in chain.get_transaction(tx.hash).internal_transfers:
                            if tx.to_address == int_tx['from'] == mint['sender'] and int_tx['to'] in ROUTERS:
                                for transfer in tx._events['Transfer']:
                                    if transfer[0] == WRAPPED_GAS_COIN == transfer.address and tx.token == transfer[1] and transfer[2] == int_tx['value']:
                                        return True

                elif tokens[1] == WRAPPED_GAS_COIN:
                    if any(tokens[0] == transfer.address and tx.to_address == transfer.values()[0] == mint['sender'] and transfer.values()[1] == mint.address for transfer in tx._events["Transfer"]):
                        for int_tx in chain.get_transaction(tx.hash).internal_transfers:
                            if tx.to_address == int_tx['from'] == mint['sender'] and int_tx['to'] in ROUTERS:
                                for transfer in tx._events['Transfer']:
                                    if transfer[0] == WRAPPED_GAS_COIN == transfer.address and tx.token == transfer[1] and transfer[2] == int_tx['value']:
                                        return True

                else:
                    print(f"tokens: {tokens}")

            # Component tokens
            elif tx.to_address == mint.address:
                return True

    return tx in HashMatcher({
        Network.Mainnet: [
            "0x3a000d3aa5d0d83a3ff359de261bfcecdc62cd13500b8ab517802742ac918627",  # uni v3
        ],
    }.get(CHAINID, []))

def is_uniswap_withdrawal(tx: TreasuryTx) -> bool:
    if tx.to_address and "Burn" in tx._events and "Transfer" in tx._events:
        for burn in tx._events["Burn"]:
            event_args = {"sender", "amount0", "amount1","to"}
            if any(arg not in burn for arg in event_args):
                continue

            # LP token
            if tx.from_address.address in treasury.addresses and tx.from_address == burn['to'] and tx.token == tx.to_address == burn.address:
                lp = tx.token.contract
                tokens = [lp.token0(), lp.token1()]
                if tx.token == tx.to_address and all(
                    any(
                        token == transfer.address 
                        and tx.to_address == transfer.values()[0]
                        and tx.from_address == transfer.values()[1] == burn['to'] 
                        for transfer in tx._events["Transfer"]
                    )
                    for token in tokens
                ):
                    return True

                # Maybe native asset was used instead of wrapped.
                if tokens[0] == WRAPPED_GAS_COIN:
                    if any(
                        tokens[1] == transfer.address 
                        and tx.token == tx.to_address == transfer.values()[0]
                        and tx.from_address == transfer.values()[1] == burn['to'] 
                        for transfer in tx._events["Transfer"]
                    ):
                        for int_tx in chain.get_transaction(tx.hash).internal_transfers:
                            if int_tx['from'] in ROUTERS and tx.from_address == int_tx['to']:
                                for transfer in tx._events['Transfer']:
                                    if tx.token == transfer[0] and transfer[1] == transfer.address == WRAPPED_GAS_COIN and transfer[2] == int_tx['value']:
                                        return True

                elif tokens[1] == WRAPPED_GAS_COIN:
                    if any(
                        tokens[0] == transfer.address 
                        and tx.token == tx.to_address == transfer.values()[0]
                        and tx.from_address == transfer.values()[1] == burn['to'] 
                        for transfer in tx._events["Transfer"]
                    ):
                        for int_tx in chain.get_transaction(tx.hash).internal_transfers:
                            if int_tx['from'] in ROUTERS and tx.from_address == int_tx['to']:
                                for transfer in tx._events['Transfer']:
                                    if transfer[0] == tx.token and transfer[1] == transfer.address == WRAPPED_GAS_COIN and transfer[2] == int_tx['value']:
                                        return True

                else:
                    print(f"tokens: {tokens}")

            # Component tokens
            elif tx.from_address == burn.address:
                return True
    return tx in HashMatcher({
        Network.Mainnet: [
            "0xf0723677162cdf8105c0f752a8c03c53803cb9dd9a6649f3b9bc5d26822d531f",
            "0xaf1b7f138fb8bf3f5e13a680cb4a9b7983ec71a75836111c03dee6ae530db176",  # v3
        ],
    }.get(CHAINID, []))

def is_uniswap_swap(tx: TreasuryTx) -> bool:
    # The LP for dumping solidSEX is not verified :( devs blz do something
    # Sell side
    if tx.from_address.address in treasury.addresses and tx._to_nickname == "Non-Verified Contract: 0xa66901D1965F5410dEeB4d0Bb43f7c1B628Cb20b" and tx._symbol == "SOLIDsex":
        return True
    # Buy side
    elif tx._from_nickname == "Non-Verified Contract: 0xa66901D1965F5410dEeB4d0Bb43f7c1B628Cb20b" and tx.to_address.address in treasury.addresses and tx._symbol == "WFTM":
        return True
    
    elif tx in HashMatcher(
        {
            Network.Mainnet: [
                "0x490245ef6e3c60127491415afdea23c13f4ca1a8c04de4fb3a498e7f7574b724", # uni v3
            ],
        }.get(CHAINID, [])
    ):
        return True
    
    # All other swaps
    elif "Swap" in tx._events:
        for swap in tx._events["Swap"]:
            # Sell side
            if tx.from_address.address in treasury.addresses and tx.to_address == swap.address:
                pool = Contract(swap.address)
                token0, token1 = fetch_multicall([pool,'token0'],[pool,'token1'])
                if token0 in SKIP_TOKENS or token1 in SKIP_TOKENS:
                    # This will be recorded elsewhere
                    continue
                    
                # The below code only works for v2 swaps, let's skip v3 swaps
                if 'sqrtPriceX96' in swap:
                    continue
                    
                if tx.token == token0:
                    if Decimal(swap['amount0In']) / tx.token.scale == tx.amount:
                        return True
                elif tx.token == token1:
                    if Decimal(swap['amount1In']) / tx.token.scale == tx.amount:
                        return True

            # Buy side
            elif tx.from_address == swap.address and tx.to_address.address in treasury.addresses:
                pool = Contract(swap.address)
                token0, token1 = fetch_multicall([pool,'token0'],[pool,'token1'])
                if token0 in SKIP_TOKENS or token1 in SKIP_TOKENS:
                    # This will be recorded elsewhere
                    continue
                if tx.token == token0:
                    if Decimal(swap['amount0Out']) / tx.token.scale == tx.amount:
                        return True
                elif tx.token == token1:
                    if Decimal(swap['amount1Out']) / tx.token.scale == tx.amount:
                        return True
    return False
