from brownie.network.contract import Contract

from yearn.curve import crv, voting_escrow
from yearn.prices import magic
from yearn.utils import contract_creation_block


class Backscratcher:
    def __init__(self):
        self.name = "yveCRV"
        self.vault = Contract("0xc5bDdf9843308380375a611c18B50Fb9341f502A")
        self.proxy = Contract("0xF147b8125d2ef93FB6965Db97D6746952a133934")

    def total_value_at(self, block=None):
        crv_locked = voting_escrow.balanceOf["address"](self.proxy, block_identifier=block) / 1e18
        crv_price = magic.get_price(crv, block=block)
        return crv_locked * crv_price


class Registry:
    def __init__(self) -> None:
        self.vaults = [Backscratcher()]

    def describe(self, block=None):
        return None

    def total_value_at(self, block=None):
        vaults = self.active_vaults_at(block)
        return {vault.name: vault.total_value_at(block=block) for vault in vaults}

    def active_vaults_at(self, block=None):
        vaults = list(self.vaults)
        if block:
            vaults = [vault for vault in self.vaults if contract_creation_block(str(vault.vault)) <= block]
        return vaults
