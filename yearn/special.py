import math

from time import time
from yearn.common import Tvl
from yearn.apy.common import Apy, ApyFees, ApyPoints

import requests

from brownie.network.contract import Contract
from joblib import Parallel, delayed

from yearn.prices import magic
from yearn.prices.curve import curve
from yearn.utils import contract_creation_block, contract
from yearn.apy import ApySamples
from yearn.exceptions import PriceError

class YveCRVJar:
    def __init__(self):
        self.id = "yvecrv-eth"
        self.name = "pickling SushiSwap LP Token"
        self.vault = contract("0xbD17B1ce622d73bD438b9E658acA5996dc394b0d")
        self.token = contract("0x5Eff6d166D66BacBC1BF52E2C54dD391AE6b1f48")

    @property
    def strategies(self):
        return []

    @property
    def decimals(self):
        return 18

    @property
    def symbol(self):
        return 'pSLP'

    def apy(self, _: ApySamples) -> Apy:
        data = requests.get("https://api.pickle.finance/prod/protocol/pools").json()
        yvboost_eth_pool  = [pool for pool in data if pool["identifier"] == "yvboost-eth"][0]
        apy = yvboost_eth_pool["apy"]  / 100.
        points = ApyPoints(apy, apy, apy)
        return Apy("yvecrv-jar", apy, apy, ApyFees(), points=points)

    def tvl(self, block=None) -> Tvl:
        data = requests.get("https://api.pickle.finance/prod/protocol/value").json()
        tvl = data[self.id]
        return Tvl(tvl=tvl)

class Backscratcher:
    def __init__(self):
        self.name = "yveCRV"
        self.vault = contract("0xc5bDdf9843308380375a611c18B50Fb9341f502A")
        self.token = contract("0xD533a949740bb3306d119CC777fa900bA034cd52")
        self.proxy = contract("0xF147b8125d2ef93FB6965Db97D6746952a133934")

    def describe(self, block=None):
        crv_locked = curve.voting_escrow.balanceOf["address"](self.proxy, block_identifier=block) / 1e18
        crv_price = magic.get_price(curve.crv, block=block)
        return {
            'totalSupply': crv_locked,
            'token price': crv_price,
            'tvl': crv_locked * crv_price,
        }

    def total_value_at(self, block=None):
        crv_locked = curve.voting_escrow.balanceOf["address"](self.proxy, block_identifier=block) / 1e18
        crv_price = magic.get_price(curve.crv, block=block)
        return crv_locked * crv_price

    @property
    def strategies(self):
        return []

    def apy(self, _: ApySamples) -> Apy:
        curve_3_pool = contract("0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7")
        curve_reward_distribution = contract("0xA464e6DCda8AC41e03616F95f4BC98a13b8922Dc")
        curve_voting_escrow = contract("0x5f3b5DfEb7B28CDbD7FAba78963EE202a494e2A2")
        voter = "0xF147b8125d2ef93FB6965Db97D6746952a133934"
        crv_price = magic.get_price("0xD533a949740bb3306d119CC777fa900bA034cd52")
        yvecrv_price = magic.get_price("0xc5bDdf9843308380375a611c18B50Fb9341f502A")
        
        total_vecrv = curve_voting_escrow.totalSupply()
        yearn_vecrv = curve_voting_escrow.balanceOf(voter)
        vault_supply = self.vault.totalSupply()

        week = 7 * 86400
        epoch = math.floor(time() / week) * week - week
        tokens_per_week = curve_reward_distribution.tokens_per_week(epoch) / 1e18
        virtual_price = curve_3_pool.get_virtual_price() / 1e18
        # although we call this APY, this is actually APR since there is no compounding
        apy = (tokens_per_week * virtual_price * 52) / ((total_vecrv / 1e18) * crv_price)
        vault_boost = (yearn_vecrv / vault_supply) * (crv_price / yvecrv_price)
        composite = {
            "currentBoost": vault_boost,
            "boostedApy": apy * vault_boost,
            "totalApy": apy * vault_boost,
            "poolApy": apy,
            "baseApy": apy,
        }
        return Apy("backscratcher", apy, apy, ApyFees(), composite=composite)

    def tvl(self, block=None) -> Tvl:
        total_assets = self.vault.totalSupply(block_identifier=block)
        try:
            price = magic.get_price(self.token, block=block)
        except PriceError:
            price = None
        tvl = total_assets * price / 10 ** self.vault.decimals(block_identifier=block) if price else None
        return Tvl(total_assets, price, tvl) 

        


class Ygov:
    def __init__(self):
        self.name = "yGov"
        self.vault = contract("0xBa37B002AbaFDd8E89a1995dA52740bbC013D992")
        self.token = contract("0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e")

    def describe(self, block=None):
        yfi_locked = self.token.balanceOf(self.vault, block_identifier=block) / 1e18
        yfi_price = magic.get_price(str(self.token), block=block)
        return {
            'totalAssets': yfi_locked,
            'token price': yfi_price,
            'tvl': yfi_locked * yfi_price,
        }

    def total_value_at(self, block=None):
        yfi_locked = self.token.balanceOf(self.vault, block_identifier=block) / 1e18
        yfi_price = magic.get_price(str(self.token), block=block)
        return yfi_locked * yfi_price


class Registry:
    def __init__(self) -> None:
        self.vaults = [
            Backscratcher(),
            Ygov(),
        ]

    def describe(self, block=None):
        # not supported yet
        vaults = self.active_vaults_at(block)
        data = Parallel(4, "threading")(delayed(vault.describe)(block=block) for vault in vaults)
        return {vault.name: desc for vault, desc in zip(vaults, data)}

    def total_value_at(self, block=None):
        vaults = self.active_vaults_at(block)
        return {vault.name: vault.total_value_at(block=block) for vault in vaults}

    def active_vaults_at(self, block=None):
        vaults = list(self.vaults)
        if block:
            vaults = [vault for vault in self.vaults if contract_creation_block(str(vault.vault)) <= block]
        return vaults
