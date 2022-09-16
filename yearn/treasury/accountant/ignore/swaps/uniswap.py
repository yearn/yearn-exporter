
from brownie import ZERO_ADDRESS, chain
from yearn.constants import WRAPPED_GAS_COIN
from yearn.entities import TreasuryTx
from yearn.multicall2 import fetch_multicall
from yearn.treasury.accountant.classes import HashMatcher
from yearn.treasury.accountant.constants import treasury
from yearn.treasury.accountant.ignore.swaps.skip_tokens import SKIP_TOKENS
from yearn.utils import contract


ROUTERS = [
    "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
]

def is_uniswap_deposit(tx: TreasuryTx) -> bool:
    if tx.to_address and "Mint" in tx._events and "Transfer" in tx._events:
        for mint in tx._events["Mint"]:
            event_args = {"sender", "amount0", "amount1"}
            if not all(arg in mint for arg in event_args):
                continue

            # LP token
            if tx.from_address.address == ZERO_ADDRESS and (
                tx.token.address.address == mint.address or
                # KP3R/WETH Uni v3 LP -- used while depositing to kLP-KP3R/WETH
                mint.address == "0x11B7a6bc0259ed6Cf9DB8F499988F9eCc7167bf5"
            ):
                tokens = [
                    contract(tx.token.address.address).token0(),
                    contract(tx.token.address.address).token1(),
                ]
                if all(
                    any(token == transfer.address and transfer.values()[0] == tx.to_address.address and transfer.values()[1] == mint.address for transfer in tx._events["Transfer"])
                    for token in tokens
                ):
                    return True
                
                # Maybe native asset was used instead of wrapped.
                if tokens[0] == WRAPPED_GAS_COIN:
                    if any(tokens[1] == transfer.address and transfer.values()[0] == tx.to_address.address == mint['sender'] and transfer.values()[1] == mint.address for transfer in tx._events["Transfer"]):
                        for int_tx in chain.get_transaction(tx.hash).internal_transfers:
                            if int_tx['from'] == tx.to_address.address == mint['sender'] and int_tx['to'] in ROUTERS:
                                for transfer in tx._events['Transfer']:
                                    if transfer[0] == WRAPPED_GAS_COIN == transfer.address and transfer[1] == tx.token.address.address and transfer[2] == int_tx['value']:
                                        return True
                
                elif tokens[1] == WRAPPED_GAS_COIN:
                    if any(tokens[0] == transfer.address and transfer.values()[0] == tx.to_address.address == mint['sender'] and transfer.values()[1] == mint.address for transfer in tx._events["Transfer"]):
                        for int_tx in chain.get_transaction(tx.hash).internal_transfers:
                            if int_tx['from'] == tx.to_address.address == mint['sender'] and int_tx['to'] in ROUTERS:
                                for transfer in tx._events['Transfer']:
                                    if transfer[0] == WRAPPED_GAS_COIN == transfer.address and transfer[1] == tx.token.address.address and transfer[2] == int_tx['value']:
                                        return True

                else:
                    print(tokens)

            # Component tokens
            elif tx.to_address.address == mint.address:
                return True
    
    return False

def is_uniswap_withdrawal(tx: TreasuryTx) -> bool:
    if tx.to_address and "Burn" in tx._events and "Transfer" in tx._events:
        for burn in tx._events["Burn"]:
            event_args = {"sender", "amount0", "amount1","to"}
            if not all(arg in burn for arg in event_args):
                continue

            # LP token
            if tx.from_address.address in treasury.addresses and tx.from_address.address == burn['to'] and tx.token.address.address == burn.address == tx.to_address.address:
                tokens = [
                    contract(tx.token.address.address).token0(),
                    contract(tx.token.address.address).token1(),
                ]
                if all(
                    any(token == transfer.address and transfer.values()[0] == tx.token.address.address == tx.to_address.address and transfer.values()[1] == tx.from_address.address == burn['to'] for transfer in tx._events["Transfer"])
                    for token in tokens
                ):
                    return True
                
                # Maybe native asset was used instead of wrapped.
                if tokens[0] == WRAPPED_GAS_COIN:
                    if any(tokens[1] == transfer.address and transfer.values()[0] == tx.token.address.address == tx.to_address.address and transfer.values()[1] == tx.from_address.address == burn['to'] for transfer in tx._events["Transfer"]):
                        for int_tx in chain.get_transaction(tx.hash).internal_transfers:
                            if int_tx['from'] in ROUTERS and int_tx['to'] == tx.from_address.address:
                                for transfer in tx._events['Transfer']:
                                    if transfer[0] == tx.token.address.address and transfer[1] == transfer.address == WRAPPED_GAS_COIN and transfer[2] == int_tx['value']:
                                        return True

                elif tokens[1] == WRAPPED_GAS_COIN:
                    if any(tokens[0] == transfer.address and transfer.values()[0] == tx.token.address.address == tx.to_address.address and transfer.values()[1] == tx.from_address.address == burn['to'] for transfer in tx._events["Transfer"]):
                        for int_tx in chain.get_transaction(tx.hash).internal_transfers:
                            if int_tx['from'] in ROUTERS and int_tx['to'] == tx.from_address.address:
                                for transfer in tx._events['Transfer']:
                                    if transfer[0] == tx.token.address.address and transfer[1] == transfer.address == WRAPPED_GAS_COIN and transfer[2] == int_tx['value']:
                                        return True

                else:
                    print(tokens)

            # Component tokens
            elif tx.from_address.address == burn.address:
                return True
    return tx in HashMatcher([
        "0xf0723677162cdf8105c0f752a8c03c53803cb9dd9a6649f3b9bc5d26822d531f",
    ])

def is_uniswap_swap(tx: TreasuryTx) -> bool:
    # The LP for dumping solidSEX is not verified :( devs blz do something
    # Sell side
    if tx.from_address.address in treasury.addresses and tx._to_nickname == "Non-Verified Contract: 0xa66901D1965F5410dEeB4d0Bb43f7c1B628Cb20b" and tx._symbol == "SOLIDsex":
        return True
    # Buy side
    elif tx._from_nickname == "Non-Verified Contract: 0xa66901D1965F5410dEeB4d0Bb43f7c1B628Cb20b" and tx.to_address and tx.to_address.address in treasury.addresses and tx._symbol == "WFTM":
        return True
    
    # All other swaps
    elif "Swap" in tx._events: # and  and tx.to_address and tx.to_address.address in treasury.addresses:
        for swap in tx._events["Swap"]:
            # Sell side
            if tx.from_address.address in treasury.addresses and tx.to_address and tx.to_address.address == swap.address:
                pool = contract(swap.address)
                token0, token1 = fetch_multicall([pool,'token0'],[pool,'token1'])
                if token0 in SKIP_TOKENS or token1 in SKIP_TOKENS:
                    # This will be recorded elsewhere
                    continue
                if tx.token.address.address == token0:
                    if round(swap['amount0In'] / tx.token.scale, 15) == round(float(tx.amount), 15):
                        return True
                elif tx.token.address.address == token1:
                    if round(swap['amount1In'] / tx.token.scale, 15) == round(float(tx.amount), 15):
                        return True

            # Buy side
            elif tx.from_address.address == swap.address and tx.to_address and tx.to_address.address in treasury.addresses:
                pool = contract(swap.address)
                token0, token1 = fetch_multicall([pool,'token0'],[pool,'token1'])
                if token0 in SKIP_TOKENS or token1 in SKIP_TOKENS:
                    # This will be recorded elsewhere
                    continue
                if tx.token.address.address == token0:
                    if round(swap['amount0Out'] / tx.token.scale, 15) == round(float(tx.amount), 15):
                        return True
                elif tx.token.address.address == token1:
                    if round(swap['amount1Out'] / tx.token.scale, 15) == round(float(tx.amount), 15):
                        return True
