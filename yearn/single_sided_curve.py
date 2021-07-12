from typing import Mapping
from yearn.constants import CURVE_SWAP_POOLS, POOL_INFO_CONTRACT, SINGLE_SIDED_TOKENS
from tabulate import tabulate
from brownie import Contract, ZERO_ADDRESS


class Registry:
    def __init__(self) -> None:
        self.vaults = []

    @staticmethod
    def total_pool_balance(pool_composition_coins):
        total = 0
        for pool_composition in pool_composition_coins:
            raw_balance = pool_composition["balance"]
            decimals = pool_composition["decimals"]
            balance = raw_balance / (10 ** decimals)
            total += balance

        return total

    @staticmethod
    def coin_composition(total, coin_info):
        raw_balance = coin_info["balance"]
        decimals = coin_info["decimals"]
        balance = raw_balance / (10 ** decimals)
        ratio = balance * 100 / total
        return ratio

    @staticmethod
    def amount_of_token_for_1_dollar(coin_info, pool_contract, index, pool_composition_coins, lp_token_decimals):
        length = len(pool_composition_coins)
        coins_array = []
        i = 0
        for i in range(length):
            if i != index:
                coins_array.append(0)
            else:
                coins_array.append(1 * 10 ** coin_info["decimals"])
        virtual_price = pool_contract.get_virtual_price()
        token_amount = pool_contract.calc_token_amount(coins_array, 1)
        token_amount_withdraw = pool_contract.calc_withdraw_one_coin(1 * 10 ** lp_token_decimals, index)
        best_virtual_price = 10 ** lp_token_decimals / virtual_price
        coin_info["get_virtual_price"] = best_virtual_price
        coin_info["calc_token_amount_deposit"] = 10 ** lp_token_decimals / token_amount
        coin_info["calc_withdraw_one_coin"] = 10 ** coin_info["decimals"] / token_amount_withdraw
        return coin_info

    def describe(self, block=None):
        pool_info = Contract(POOL_INFO_CONTRACT)
        pool_composition_coins_with_ratios = []
        for pool in CURVE_SWAP_POOLS:
            if pool["has_single_sided_deposit"] == "true":
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
                dict = pool_info.get_pool_info(address).dict()
                pool_composition_coins = []
                for idx, coin in enumerate(coins["coins"]):
                    if coin != ZERO_ADDRESS:
                        name = SINGLE_SIDED_TOKENS[coin]
                        coin_info = {
                            "pool_name": pool_name,
                            "address": coin,
                            "balance": dict["balances"][idx],
                            "decimals": dict["decimals"][idx],
                            "token": name,
                        }
                        pool_composition_coins.append(coin_info)
                total = self.total_pool_balance(pool_composition_coins)
                cols = {
                    "pool_name": "pool",
                    "address": "token_address",
                    "amount": "amount",
                    "token": "token",
                    "ratio": "composition",
                }

                for idx, coin_info in enumerate(pool_composition_coins):
                    ratio = self.coin_composition(total, coin_info)
                    coin_info["ratio"] = ratio
                    coin_info = self.amount_of_token_for_1_dollar(
                        coin_info, pool_contract, idx, pool_composition_coins, lp_token_decimals
                    )
                    pool_composition_coins_with_ratios.append(coin_info)

        return pool_composition_coins_with_ratios
