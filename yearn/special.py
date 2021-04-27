from brownie.network.contract import Contract
from joblib import Parallel, delayed

from yearn.curve import crv, voting_escrow
from yearn.prices import magic
from yearn.utils import contract_creation_block


class Backscratcher:
    def __init__(self):
        self.name = "yveCRV"
        self.vault = Contract("0xc5bDdf9843308380375a611c18B50Fb9341f502A")
        self.token = Contract("0xD533a949740bb3306d119CC777fa900bA034cd52")
        self.proxy = Contract("0xF147b8125d2ef93FB6965Db97D6746952a133934")

    def describe(self, block=None):
        crv_locked = voting_escrow.balanceOf["address"](self.proxy, block_identifier=block) / 1e18
        crv_price = magic.get_price(crv, block=block)
        return {
            'totalSupply': crv_locked,
            'token price': crv_price,
            'tvl': crv_locked * crv_price,
        }

    def total_value_at(self, block=None):
        crv_locked = voting_escrow.balanceOf["address"](self.proxy, block_identifier=block) / 1e18
        crv_price = magic.get_price(crv, block=block)
        return crv_locked * crv_price


class Ygov:
    def __init__(self):
        self.name = "yGov"
        self.vault = Contract("0xBa37B002AbaFDd8E89a1995dA52740bbC013D992")
        self.token = Contract("0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e")

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
