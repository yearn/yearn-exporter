from yearn.constants import CURVE_SWAP_POOLS, POOL_INFO_CONTRACT, SINGLE_SIDED_TOKENS
from tabulate import tabulate
from brownie import Contract, ZERO_ADDRESS


def total_pool_balance(pool_composition_coins):
    total = 0
    for pool_composition in pool_composition_coins:
        raw_balance = pool_composition["balance"]
        decimals = pool_composition["decimals"]
        balance = raw_balance / (10 ** decimals)
        total += balance

    return total


def coin_composition(total, coin_info):
    raw_balance = coin_info["balance"]
    decimals = coin_info["decimals"]
    balance = raw_balance / (10 ** decimals)
    ratio = balance * 100 / total
    return ratio


def amount_of_token_for_1m_dollar(
    coin_info, pool_contract, index, pool_composition_coins, lp_token_decimals, eth_usd, btc_usd, eur_usd
):
    length = len(pool_composition_coins)
    coins_array = []
    i = 0
    virtual_price = pool_contract.get_virtual_price()
    isEUR = "EUR" in coin_info["token"]
    isBTC = "BTC" in coin_info["token"]
    isETH = "ETH" in coin_info["token"] or "StaFi" in coin_info["token"] or "Liquid staked Ether" in coin_info["token"]
    btc_million_usd = 1000000 / (btc_usd / 10 ** 8)
    eth_million_usd = 1000000 / (eth_usd / 10 ** 8)
    cyusd = 1000000 / (0.01)
    if coin_info["price_usdc"] == "0" or isBTC:
        coin_info["price_usdc"] = 10 ** 6
        if isETH:
            coin_info["price_usdc"] = btc_usd
        elif isBTC:
            coin_info["price_usdc"] = eth_usd
        elif isEUR:
            coin_info["price_usdc"] = eur_usd
        print(coin_info["token"], "price is 0")
    token_qty = (1000000 * 10 ** 6) / ((coin_info["price_usdc"]))
    for i in range(length):
        if i != index:
            coins_array.append(0)
        else:
            if "IronBank" in coin_info["pool_name"]:
                coins_array.append(token_qty * 10 ** coin_info["decimals"])
            elif isBTC == False and isETH == False:
                print("DECIMALS", coin_info["decimals"])
                coins_array.append(token_qty * 10 ** coin_info["decimals"])
            elif isETH:
                coins_array.append(token_qty * 10 ** coin_info["decimals"])
            elif isBTC:
                coins_array.append(token_qty * 10 ** coin_info["decimals"])

    print(coins_array)
    token_amount = pool_contract.calc_token_amount(coins_array, 1)
    token_amount_withdraw = pool_contract.calc_token_amount(coins_array, 0)
    best_virtual_price = 10 ** lp_token_decimals / virtual_price
    coin_info["get_virtual_price"] = best_virtual_price
    coin_info["calc_token_amount_deposit"] = token_amount / ((10 ** 6) * (10 ** lp_token_decimals))  # lp_token_decimals
    if "IronBank" in coin_info["pool_name"]:
        coin_info["calc_token_amount_deposit"] = token_amount / (
            (cyusd) * (10 ** lp_token_decimals)
        )  # lp_token_decimals
        coin_info["calc_token_amount_withdraw"] = token_amount_withdraw / (
            (cyusd) * (10 ** lp_token_decimals)
        )  # lp_token_decimals
    elif isBTC == False and isETH == False:
        coin_info["calc_token_amount_deposit"] = token_amount / (
            (10 ** 6) * (10 ** lp_token_decimals)
        )  # lp_token_decimals
        coin_info["calc_token_amount_withdraw"] = token_amount_withdraw / (
            (10 ** 6) * (10 ** lp_token_decimals)
        )  # lp_token_decimals
    elif isETH:
        coin_info["calc_token_amount_deposit"] = token_amount / (
            (eth_million_usd) * (10 ** lp_token_decimals)
        )  # lp_token_decimals
        coin_info["calc_token_amount_withdraw"] = token_amount_withdraw / (
            (eth_million_usd) * (10 ** lp_token_decimals)
        )  # lp_token_decimals
    elif isBTC:
        coin_info["calc_token_amount_deposit"] = token_amount / (
            (btc_million_usd) * (10 ** lp_token_decimals)
        )  # lp_token_decimals
        coin_info["calc_token_amount_withdraw"] = token_amount_withdraw / (
            (btc_million_usd) * (10 ** lp_token_decimals)
        )  # lp_token_decimals

    coin_info["deposit_slippage"] = (
        (coin_info["calc_token_amount_deposit"] - best_virtual_price) / best_virtual_price
    ) * 100
    coin_info["withdraw_slippage"] = (
        (coin_info["calc_token_amount_withdraw"] - best_virtual_price) / best_virtual_price
    ) * 100
    if "IronBank" in coin_info["pool_name"]:
        coin_info["deposit_slippage"] = (
            coin_info["calc_token_amount_deposit"] - best_virtual_price
        ) / best_virtual_price
        coin_info["withdraw_slippage"] = (
            coin_info["calc_token_amount_withdraw"] - best_virtual_price
        ) / best_virtual_price

    # coin_info["withdraw_slippage"] = coin_info["deposit_slippage"]
    return coin_info


def main():
    pool_info = Contract(POOL_INFO_CONTRACT)
    btc_usd_chainlink = Contract("0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c")
    btc_usd = btc_usd_chainlink.latestAnswer()
    eth_usd_chainlink = Contract("0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419")
    eth_usd = eth_usd_chainlink.latestAnswer()
    eur_usd_chainlink = Contract("0xb49f677943BC038e9857d61E7d053CaA2C1734C1")
    eur_usd = eur_usd_chainlink.latestAnswer()
    addresses_provider = Contract("0x9be19Ee7Bc4099D62737a7255f5c227fBcd6dB93")
    oracle = Contract(addresses_provider.addressById("ORACLE"))

    # provider = Contract('0x0000000022D53366457F9d5E68Ec105046FC4383')
    # registry_address = provider.get_registry()
    # registry = Contract(registry_address)
    # count_pools = registry.pool_count()
    for pool in CURVE_SWAP_POOLS:
        if pool["has_single_sided_deposit"] != "false":
            print("HAS POOL", pool)
            address = pool["address"]
            pool_contract = Contract(address)
            lp_token_decimals = 18
            try:
                lp_token = Contract(pool_contract.lp_token())
                lp_token_decimals = lp_token.decimals()
            except AttributeError:
                print("no lp_token, assuming 18 decimals")

            pool_name = pool["name"]
            coins = pool_info.get_pool_coins(address).dict()
            # dict = pool_info.get_pool_info(address).dict()
            pool_composition_coins = []

            for idx, coin in enumerate(coins["coins"]):
                if coin != ZERO_ADDRESS:
                    balance = pool_contract.balances(idx)
                    print("checking coin", coin)
                    if coin == '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE':
                        name = "ETH"
                        decimals = 18
                    else:
                        coin_contract = Contract(coin)
                        print("getting coin name", coin)
                        name = coin_contract.name()  # SINGLE_SIDED_TOKENS[coin]
                        print("coin name is ", name)
                        coin_contract = Contract(coin)
                        decimals = coin_contract.decimals()
                    coin_price_in_usdc = oracle.getPriceUsdcRecommended(coin)
                    coin_info = {
                        "pool_name": pool_name,
                        "address": coin,
                        "balance": balance,  # dict["balances"][idx],
                        # "underlying_balance": dict["underlying_balances"][idx],
                        "decimals": decimals,
                        # "underlying_decimals": coins["underlying_decimals"][idx],
                        "token": name,
                        "price_usdc": coin_price_in_usdc
                        # "underlying_coin": coins["underlying_coins"][idx],
                        # "wrapped_coin": coins["coins"][idx],
                    }

                    pool_composition_coins.append(coin_info)

            total = total_pool_balance(pool_composition_coins)
            cols = {
                "pool_name": "pool",
                "address": "token address",
                "amount": "amount",
                "token": "token",
                "ratio": "composition",
                "deposit_slippage": "deposit_slippage",
                "withdraw_slippage": "withdraw_slippage",
            }
            pool_composition_coins_with_ratios = []

            for idx, coin_info in enumerate(pool_composition_coins):
                ratio = coin_composition(total, coin_info)
                coin_info["ratio"] = ratio
                coin_info = amount_of_token_for_1m_dollar(
                    coin_info, pool_contract, idx, pool_composition_coins, lp_token_decimals, eth_usd, btc_usd, eur_usd
                )
                pool_composition_coins_with_ratios.append(coin_info)

            print(
                tabulate(
                    pool_composition_coins_with_ratios,
                    headers=cols,
                )
            )
