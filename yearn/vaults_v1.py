import logging
from dataclasses import dataclass
from typing import Optional

from brownie import Contract, interface, web3
from brownie.network.contract import InterfaceContainer
from joblib import Parallel, delayed

from yearn import constants, curve
from yearn.events import contract_creation_block
from yearn.mutlicall import fetch_multicall
from yearn.prices import magic

logger = logging.getLogger(__name__)


@dataclass
class VaultV1:
    vault: InterfaceContainer
    controller: InterfaceContainer
    token: interface.ERC20
    strategy: str
    is_wrapped: bool
    is_delegated: bool
    # the rest is populated in post init
    name: Optional[str] = None
    decimals: Optional[int] = None

    def __post_init__(self):
        self.vault = Contract(self.vault)
        self.controller = Contract(self.controller)
        self.strategy = Contract(self.strategy)
        self.token = Contract(self.token)
        if str(self.vault) not in constants.VAULT_ALIASES:
            logger.warning("no vault alias for %s, reading from vault.sybmol()", self.vault)
        self.name = constants.VAULT_ALIASES.get(str(self.vault), self.vault.symbol())
        self.decimals = self.vault.decimals()  # vaults inherit decimals from token

    def describe(self):
        scale = 10 ** self.decimals
        info = {}
        try:
            info["share price"] = self.vault.getPricePerFullShare() / 1e18
        except ValueError:
            # no money in vault, exit early
            return {"tvl": 0}

        attrs = {
            "vault balance": [self.vault, "balance"],
            "vault total": [self.vault, "totalSupply"],
            "strategy balance": [self.strategy, "balanceOf"],
        }

        # some of the oldest vaults don't implement these methods
        if hasattr(self.vault, "available"):
            attrs["available"] = [self.vault, "available"]

        if hasattr(self.vault, "min") and hasattr(self.vault, "max"):
            attrs["min"] = [self.vault, "min"]
            attrs["max"] = [self.vault, "max"]

        # new curve voter proxy vaults
        if hasattr(self.strategy, "proxy"):
            results = fetch_multicall(
                [self.strategy, "voter"],
                [curve.registry, "get_pool_from_lp_token", self.token],
                [self.strategy, "gauge"],
            )
            vote_proxy = interface.CurveYCRVVoter(results[0])
            swap = Contract(results[1])
            gauge = Contract(results[2])
            info.update(curve.calculate_boost(gauge, vote_proxy))
            info.update(curve.calculate_apy(gauge, swap))
            info["earned"] = gauge.claimable_tokens.call(vote_proxy).to("ether")

        if hasattr(self.strategy, "earned"):
            info["lifetime earned"] = self.strategy.earned() / scale

        if self.strategy._name == "StrategyYFIGovernance":
            ygov = interface.YearnGovernance(self.strategy.gov())
            attrs["earned"] = [ygov, "earned", self.strategy]
            attrs["reward rate"] = [ygov, "rewardRate"]
            attrs["ygov balance"] = [ygov, "balanceOf", self.strategy]
            attrs["ygov total"] = [ygov, "totalSupply"]

        # fetch attrs as multicall
        try:
            results = fetch_multicall(*attrs.values())
        except ValueError:
            pass
        else:
            for name, attr in zip(attrs, results):
                info[name] = attr / scale

        # some additional post-processing
        if "min" in info:
            info["strategy buffer"] = info.pop("min") / info.pop("max")

        if "token price" not in info:
            if self.name in ["aLINK"]:
                info["token price"] = magic.get_price(self.vault.underlying())
            elif self.name in ["USDC", "TUSD", "DAI", "USDT"]:
                info["token price"] = 1
            else:
                info["token price"] = magic.get_price(self.token)

        info["tvl"] = info["vault balance"] * info["token price"]
        return info


class Registry:
    def __init__(self):
        self.registry = interface.YRegistry(web3.ens.resolve("registry.ychad.eth"))
        self.vaults = [VaultV1(*params) for params in zip(self.registry.getVaults(), *self.registry.getVaultsInfo())]
        # patch aLINK
        for vault in self.vaults:
            if vault.name == 'aLINK':
                vault.token = vault.vault.underlying()

    def __repr__(self) -> str:
        return f"<Registry vaults={len(self.vaults)}>"

    def describe(self, block=None):
        if block:
            raise NotImplementedError("historical data not implemented yet")
        data = Parallel(8, "threading")(delayed(vault.describe)() for vault in self.vaults)
        return {vault.name: desc for vault, desc in zip(self.vaults, data)}

    def total_value_at(self, block=None):
        vaults = self.active_vaults_at(block)
        prices = Parallel(8, "threading")(delayed(magic.get_price)(vault.token, block) for vault in vaults)
        try:
            balances = fetch_multicall(*[[vault.vault, "balance"] for vault in vaults], block=block)
        except ValueError:
            logger.error('multicall failed, fallback to slow balances')
            balances = Parallel(8, "threading")(delayed(maybe_balance)(vault, block) for vault in vaults)
        
        data = {vault.name: balance * price / 10 ** vault.decimals for vault, balance, price in zip(vaults, balances, prices)}

        # add backscratcher
        crv_price = magic.get_price(curve.crv, block=block)
        if crv_price:
            data['yveCRV'] = crv_price * curve.voting_escrow.balanceOfAt('0xF147b8125d2ef93FB6965Db97D6746952a133934', block) / 1e18
        return data

    def active_vaults_at(self, block=None):
        vaults = list(self.vaults)
        if block:
            vaults = [vault for vault in vaults if contract_creation_block(str(vault.vault)) < block]
        return vaults


def maybe_balance(vault, block):
    try:
        return vault.vault.balance(block_identifier=block)
    except ValueError:
        logger.error('could not fetch balance of %s at %s', vault.name, block)
        return 0
