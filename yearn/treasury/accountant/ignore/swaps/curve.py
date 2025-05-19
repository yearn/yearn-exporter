from brownie import ZERO_ADDRESS
from y import Contract, Network
from y.constants import CHAINID

from yearn.entities import TreasuryTx
from yearn.multicall2 import fetch_multicall
from yearn.treasury.accountant.classes import Filter, HashMatcher, IterFilter
from yearn.treasury.accountant.constants import treasury


# curve helpers
_is_old_style = lambda tx, pool: hasattr(pool, 'lp_token') and tx.token == pool.lp_token()
_is_new_style = lambda tx, pool: hasattr(pool, 'totalSupply') and tx.token == pool.address

def _token_is_curvey(tx: TreasuryTx) -> bool:
    return 'crv' in tx._symbol.lower() or 'curve' in tx.token.name.lower()

def is_curve_deposit(tx: TreasuryTx) -> bool:
    try:
        if 'AddLiquidity' in tx._events:
            for event in tx._events['AddLiquidity']:
                # LP Token Side
                if tx.from_address == ZERO_ADDRESS and _token_is_curvey(tx):
                    pool = Contract(event.address)
                    if _is_old_style(tx, pool) or _is_new_style(tx, pool):
                        return True

                # Tokens sent
                elif tx.to_address == event.address:
                    print(f"AddLiquidity: {event}")
                    for i, amount in enumerate(event["token_amounts"]):
                        if tx.amount == tx.token.scale_value(amount):
                            pool = Contract(event.address)
                            if tx.token == pool.coins(i):
                                return True

                # What if a 3crv deposit was needed before the real deposit?
                elif tx.from_address.address in treasury.addresses and tx.to_address == "0xA79828DF1850E8a3A3064576f380D90aECDD3359" and event.address == "0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7":
                    print(f"AddLiquidity-3crv: {event}")
                    for i, amount in enumerate(event["token_amounts"]):
                        if tx.amount == tx.token.scale_value(amount):
                            pool = Contract(event.address)
                            if tx.token == pool.coins(i):
                                return True
    except KeyError as e:
        if str(e) != "'components'":
            raise
    
    # TODO: see if we can remove these with latest hueristics
    return tx in HashMatcher([
        "0x567d2ebc1a336185950432b8f8b010e1116936f9e6c061634f5aba65bdb1e188",
        "0x17e2d7a40697204b3e726d40725082fec5f152f65f400df850f13ef4a4f6c827",
    ])


curve_withdrawal_hashes = HashMatcher(
    {
        Network.Mainnet: (
            # tricrypto
            "0x1c8d0faa2c1ffdd8bc6b7546ffff807329baf86b5dbf3b512511cb2da23a0525",
            # ibcrv, token outputs don't match pool coins
            ("0x1de24003b7c19ac0925fea44b73f22745a3533aaa8c45790a2e9f2075c685161", IterFilter('log_index', (22, 27, 32))),
            ("0xd1c52ba3e5f0ade00cc39b3c00ab1c96f8b5ed5eb11be99230e3b0fa06fdac67", Filter('log_index', 84)),
            # musd3crv, gusd3crv, compcrv, usdn3crv pools have neither `lp_token` method nor `totalSupply` method.
            ("0xa888094c10003c6455f852885d932c8fa2849cbadb9fdfe3ecfc96bda6bcf340", IterFilter('log_index', (86, 140, 161, 205))),
            # dola3pool
            ("0xc14c29fd2bf495bd27c8eb862b34a98eb34dec8e533046fc6278eb41b342cfce", IterFilter('log_index',(430, 437))),
            ("0xb760d18e25c47c89303772f8b0fbb267a1f2c8a1db71a08c9846b065d8e707a1", IterFilter('log_index',(163, 170))),
            "0x5d0be661f67d39999b8107e1ecb3eb3e9c8eceefbd7002da0fa1ea865f58324b",
            "0x5956b391625f0121b18118f8e665c6668b36cf5f929fda6348971b57cbee6e55",
            # sbtccrv-paired pool withdrawals to wbtc
            "0xd1fc095887411b1746d27f1d3f296e0d1489aa1e7239b1b71a00045fb8324383",
            "0x77c996183ec2d771511c09abb149ef854d027170ff4cf485703d83ff83153f25",
            "0xd230839693cfaae550824c347fde12f1279fa94e061127c9c93440bd8c10a104",
            ("0xf748e8487797049381ddf8b227e3b8d0125553b20c2b683313ba69ffd4af2f30", IterFilter('log_index', (54, 61, 86, 93, 98, 105, 120, 127))),
            ("0xf3692e5c1af812365fd3397aab5d1590b8312817065236d267dcaf2ad907db08", IterFilter('log_index', (284, 363, 375, 400))),
            ("0x182bafa03b8b74b82bad5ab59b724b2a49e03734ba6a7d0bae8477f7147d3c28", IterFilter('log_index', (152, 224, 243, 263))),
            ("0x47f58debe6560e940a76684e2b1d51c479dde9b9a350a8798b0e25f90b20c5a6", IterFilter('log_index', (164, 171))),
            "0xaff8f7d3317537a5fb74ac250401ff61499addb489c41af2981a618d4885cf1d",
            "0x76164de5dc991a48714b500ae6187fe3d3e3580174d549aefc5317f5940affc1",
            "0x4e1f5e51b310118e97b54957e1a2f3ae4f3c715f9db6b2f4e69b1230062ade4e",
            "0x6098afcb6836d286d0486454290bdaf98851c023e1bf12f46bcbb65dda28ccfa",
            ("0x718040ca412f8d66a809eaa9d2b51ce24bf950dfd16bc55c8ffc68bb2e722129", IterFilter('log_index', (76, 83))),
            "0xc85c35a708f641e00a12627f315cd0849cc63e4e80fadf24e202e677a2eae820",
            ("0xc51f10aa7e249258f67b6f087e4ee358accb5f95788a62b072efa1a0fc643511", IterFilter('log_index', (168, 177))),
        ),
    }.get(CHAINID, ())
)


def is_curve_withdrawal(tx: TreasuryTx) -> bool:
    return (
        is_curve_withdrawal_one(tx) 
        or is_curve_withdrawal_multi(tx)
        or tx in curve_withdrawal_hashes
    )


def is_curve_withdrawal_one(tx: TreasuryTx) -> bool:
    if 'RemoveLiquidityOne' not in tx._events:
        return False
    for event in tx._events['RemoveLiquidityOne']:
        # LP Token Side
        if tx.to_address == ZERO_ADDRESS and _token_is_curvey(tx) and tx.amount == tx.token.scale_value(event['token_amount']):
            return True
        # Tokens rec'd
        elif tx.from_address == event.address and tx.amount == tx.token.scale_value(event['coin_amount']):
            return True
    return False

def is_curve_withdrawal_multi(tx: TreasuryTx) -> bool:
    if 'RemoveLiquidity' not in tx._events:
        return False
    for event in tx._events['RemoveLiquidity']:
        # LP Token side
        if tx.to_address == ZERO_ADDRESS and _token_is_curvey(tx):
            pool = Contract(event.address)
            if _is_old_style(tx, pool) or _is_new_style(tx, pool):
                return True
            print(f'wtf is this: {tx}')
        # Tokens rec'd
        elif tx.from_address == event.address and tx.to_address.address in treasury.addresses:
            for i, amount in enumerate(event['token_amounts']):
                if tx.amount == tx.token.scale_value(amount):
                    pool = Contract(event.address)
                    check_method = getattr(pool, 'underlying_coins', pool.coins)
                    return tx.token == check_method(i)
    return False
                    
def _exchange_shaped_correctly(exchange_event) -> bool:
    keys = {"buyer","sold_id","tokens_sold","bought_id","tokens_bought"}
    return all(key in exchange_event for key in keys)

def is_curve_swap(tx: TreasuryTx) -> bool:
    if "TokenExchange" in tx._events:
        for exchange in tx._events["TokenExchange"]:
            if not _exchange_shaped_correctly(exchange):
                continue
            pool = Contract(exchange.address)
            buy_token, sell_token = fetch_multicall([pool, 'coins', exchange['bought_id']], [pool, 'coins', exchange['sold_id']])
            # Sell side
            if tx.from_address == exchange['buyer'] and tx.to_address == exchange.address and tx.token == sell_token and tx.amount == tx.token.scale_value(exchange['tokens_sold']):
                return True
            # Buy side
            elif tx.from_address == exchange.address and tx.to_address == exchange['buyer'] and tx.token == buy_token and tx.amount == tx.token.scale_value(exchange['tokens_bought']):
                return True
    
    return tx in HashMatcher([
        ("0xc14c29fd2bf495bd27c8eb862b34a98eb34dec8e533046fc6278eb41b342cfce", IterFilter('log_index', (439, 443))),
        ("0x22f62d0922c430232aa402296055d79a6cf5c36a8b6253a7f1f46f1e1f66e277", IterFilter("log_index", (61, 65))),
    ])

