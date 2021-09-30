from collections import defaultdict

from brownie import Contract
from joblib import Parallel, delayed

from yearn.utils import contract_creation_block
from yearn.multicall2 import fetch_multicall, multicall_matrix
from yearn.prices import magic

IEARN = {
    # v1 - deprecated
    # v2
    "yDAIv2": "0x16de59092dAE5CcF4A1E6439D611fd0653f0Bd01",
    "yUSDCv2": "0xd6aD7a6750A7593E092a9B218d66C0A814a3436e",
    "yUSDTv2": "0x83f798e925BcD4017Eb265844FDDAbb448f1707D",
    "ysUSDv2": "0xF61718057901F84C4eEC4339EF8f0D86D2B45600",
    "yTUSDv2": "0x73a052500105205d34daf004eab301916da8190f",
    "yWBTCv2": "0x04Aa51bbcB46541455cCF1B8bef2ebc5d3787EC9",
    # v3
    "yDAIv3": "0xC2cB1040220768554cf699b0d863A3cd4324ce32",
    "yUSDCv3": "0x26EA744E5B887E5205727f55dFBE8685e3b21951",
    "yUSDTv3": "0xE6354ed5bC4b393a5Aad09f21c46E101e692d447",
    "yBUSDv3": "0x04bC0Ab673d88aE9dbC9DA2380cB6B79C4BCa9aE",
}


class Earn:
    def __init__(self, name, vault):
        self.name = name
        self.vault = Contract(vault)
        self.token = self.vault.token()
        self.scale = 10 ** self.vault.decimals()

    def __repr__(self) -> str:
        return f"Earn({repr(self.name)}, {repr(self.vault.address)})"


class Registry:
    def __init__(self):
        self.vaults = [Earn(name, vault) for name, vault in IEARN.items()]

    def __repr__(self):
        return f"<Earn vaults={len(self.vaults)}>"

    def describe(self, block=None) -> dict:
        vaults = self.active_vaults_at_block(block)
        contracts = [vault.vault for vault in vaults]
        results = multicall_matrix(contracts, ["totalSupply", "pool", "getPricePerFullShare", "balance"], block=block)
        output = defaultdict(dict)
        prices = Parallel(8, "threading")(delayed(magic.get_price)(vault.token, block=block) for vault in vaults)
        for vault, price in zip(vaults, prices):
            res = results[vault.vault]
            if res['getPricePerFullShare'] is None:
                continue

            output[vault.name] = {
                "total supply": res["totalSupply"] / vault.scale,
                "available balance": res["balance"] / vault.scale,
                "pooled balance": res["pool"] / vault.scale,
                "price per share": res['getPricePerFullShare'] / 1e18,
                "token price": price,
                "tvl": res["pool"] / vault.scale * price,
                "address": vault.vault,
                "version": "iearn",
            }

        return dict(output)

    def total_value_at(self, block=None):
        vaults = self.active_vaults_at_block(block)
        prices = Parallel(8, "threading")(delayed(magic.get_price)(vault.token, block=block) for vault in vaults)
        results = fetch_multicall(*[[vault.vault, "pool"] for vault in vaults], block=block)
        return {vault.name: assets * price / vault.scale for vault, assets, price in zip(vaults, results, prices)}

    def active_vaults_at_block(self, block=None):
        if block is None:
            return self.vaults
        return [vault for vault in self.vaults if contract_creation_block(str(vault.vault)) < block]
