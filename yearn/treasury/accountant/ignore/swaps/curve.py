
from brownie import ZERO_ADDRESS, chain
from y import Contract, Network

from yearn.entities import TreasuryTx
from yearn.multicall2 import fetch_multicall
from yearn.treasury.accountant.classes import Filter, HashMatcher, IterFilter
from yearn.treasury.accountant.constants import treasury


def is_curve_deposit(tx: TreasuryTx) -> bool:
    if 'AddLiquidity' in tx._events:
        for event in tx._events['AddLiquidity']:
            pool = Contract(event.address)
            # LP Token Side
            if tx.from_address.address == ZERO_ADDRESS and ('crv' in tx._symbol.lower() or 'curve' in tx.token.name.lower()) and tx.to_address and tx.to_address.address in treasury.addresses and ((hasattr(pool, 'lp_token') and pool.lp_token() == tx.token.address.address) or (hasattr(pool, 'totalSupply') and pool.address == tx.token.address.address)):
                return True

            # Tokens sent
            elif tx.from_address.address in treasury.addresses and tx.to_address and tx.to_address.address == event.address:
                print(event)
                for i, amount in enumerate(event["token_amounts"]):
                    if tx.token.address.address == pool.coins(i) and round(float(tx.amount), 15) == round(amount/tx.token.scale, 15):
                        return True

            # What if a 3crv deposit was needed before the real deposit?
            elif tx.from_address.address in treasury.addresses and tx.to_address and tx.to_address.address == "0xA79828DF1850E8a3A3064576f380D90aECDD3359" and event.address == "0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7":
                print(event)
                for i, amount in enumerate(event["token_amounts"]):
                    if tx.token.address.address == pool.coins(i) and round(float(tx.amount), 15) == round(amount/tx.token.scale, 15):
                        return True
    
    return tx in HashMatcher([
        "0x567d2ebc1a336185950432b8f8b010e1116936f9e6c061634f5aba65bdb1e188",
        "0x17e2d7a40697204b3e726d40725082fec5f152f65f400df850f13ef4a4f6c827",
    ])

def is_curve_withdrawal(tx: TreasuryTx) -> bool:
    if 'RemoveLiquidityOne' in tx._events:
        for event in tx._events['RemoveLiquidityOne']:
            # LP Token Side
            if tx.to_address and tx.to_address.address == ZERO_ADDRESS and ('crv' in tx._symbol.lower() or 'curve' in tx.token.name.lower()) and round(float(tx.amount), 15) == round(event['token_amount'] / tx.token.scale, 15):
                return True
            
            # Tokens rec'd
            elif tx.from_address.address == event.address and tx.to_address and tx.to_address.address in treasury.addresses and round(float(tx.amount), 15) == round(event['coin_amount'] / tx.token.scale, 15):
                return True
    
    if 'RemoveLiquidity' in tx._events:
        for event in tx._events['RemoveLiquidity']:
            pool = Contract(event.address)
            # LP Token side
            if tx.to_address and tx.to_address.address == ZERO_ADDRESS and ('crv' in tx._symbol.lower() or 'curve' in tx.token.name.lower()) and ((hasattr(pool, 'lp_token') and pool.lp_token() == tx.token.address.address) or (hasattr(pool, 'totalSupply') and pool.address == tx.token.address.address)):
                return True
                
            # Tokens rec'd
            elif tx.from_address.address == event.address and tx.to_address and tx.to_address.address in treasury.addresses:
                for i, amount in enumerate(event['token_amounts']):
                    if tx.token.address.address == pool.coins(i) and round(amount/tx.token.scale, 15) == round(float(tx.amount), 15):
                        return True
                    if hasattr(pool, 'underlying_coins') and tx.token.address.address == pool.underlying_coins(i) and round(amount/tx.token.scale, 15) == round(float(tx.amount), 15):
                        return True
    
    # TODO establish hueristics for automagically sorting these
    hashes = {
        Network.Mainnet: [
            # tricrypto
            "0x1c8d0faa2c1ffdd8bc6b7546ffff807329baf86b5dbf3b512511cb2da23a0525",
            # ibcrv, token outputs don't match pool coins
            ["0x1de24003b7c19ac0925fea44b73f22745a3533aaa8c45790a2e9f2075c685161", IterFilter('log_index', [22,27,32])],
            ["0xd1c52ba3e5f0ade00cc39b3c00ab1c96f8b5ed5eb11be99230e3b0fa06fdac67", Filter('log_index', 84)],
            # musd3crv, gusd3crv, compcrv, usdn3crv pools have neither `lp_token` method nor `totalSupply` method.
            ["0xa888094c10003c6455f852885d932c8fa2849cbadb9fdfe3ecfc96bda6bcf340", IterFilter('log_index', [86,140,161,205])],
            # dola3pool
            ["0xc14c29fd2bf495bd27c8eb862b34a98eb34dec8e533046fc6278eb41b342cfce", IterFilter('log_index',[430,437])],
            ["0xb760d18e25c47c89303772f8b0fbb267a1f2c8a1db71a08c9846b065d8e707a1", IterFilter('log_index',[163,170])],
            "0x5d0be661f67d39999b8107e1ecb3eb3e9c8eceefbd7002da0fa1ea865f58324b",
        ],
    }.get(chain.id, [])
    return tx in HashMatcher(hashes)

def is_curve_swap(tx: TreasuryTx) -> bool:
    if "TokenExchange" in tx._events:
        for event in tx._events["TokenExchange"]:
            if all(arg in event for arg in {"buyer","sold_id","tokens_sold","bought_id","tokens_bought"}):
                pool = Contract(event.address)
                buy_token, sell_token = fetch_multicall([pool, 'coins', event['bought_id']], [pool, 'coins', event['sold_id']])
                # Sell side
                if tx.from_address.address == event['buyer'] and tx.to_address and tx.to_address.address == event.address and tx.token.address.address == sell_token and round(float(tx.amount), 15) == round(event['tokens_sold']/tx.token.scale, 15):
                    return True
                # Buy side
                elif tx.from_address.address == event.address and tx.to_address and tx.to_address.address == event['buyer'] and tx.token.address.address == buy_token and round(float(tx.amount), 15) == round(event['tokens_bought']/tx.token.scale, 15):
                    return True
    
    return tx in HashMatcher([
        ["0xc14c29fd2bf495bd27c8eb862b34a98eb34dec8e533046fc6278eb41b342cfce", IterFilter('log_index', [439,443])],
    ])

