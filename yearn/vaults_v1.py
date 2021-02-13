from dataclasses import dataclass
from typing import Optional

from brownie import interface, web3, Contract
from brownie.network.contract import InterfaceContainer

from yearn import constants, curve, uniswap


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
        self.vault = constants.VAULT_INTERFACES.get(self.vault, interface.yVault)(self.vault)
        self.controller = constants.CONTROLLER_INTERFACES[self.controller](self.controller)

        try:
            self.strategy = constants.STRATEGY_INTERFACES[self.strategy](self.strategy)
        except KeyError:
            print("unable to find interface for strategy ", self.strategy)
            self.strategy = Contract.from_explorer(self.strategy)

        self.token = interface.ERC20(self.token)

        try:
            self.name = constants.VAULT_ALIASES[str(self.vault)]
        except KeyError:
            print("unable to find vault name ", self.vault)
            vault_contract = Contract.from_explorer(self.vault)
            name = vault_contract.name()
            print("vault name found ", self.vault, " -> ", name)
            self.name = name

        self.decimals = self.vault.decimals()  # vaults inherit decimals from token

    def describe(self):
        scale = 10 ** self.decimals
        info = {
            "vault balance": self.vault.balance() / scale,
            "vault total": self.vault.totalSupply() / scale,
            "strategy balance": self.strategy.balanceOf() / scale,
            "share price": 0,
        }
        try:
            info["share price"] = self.vault.getPricePerFullShare() / 1e18
        except ValueError:
            pass

        # some of the oldest vaults don't implement these methods
        if hasattr(self.vault, "available"):
            info["available"] = self.vault.available() / scale

        if hasattr(self.vault, "min") and hasattr(self.vault, "max"):
            info["strategy buffer"] = self.vault.min() / self.vault.max()

        # new curve voter proxy vaults
        if hasattr(self.strategy, "proxy"):
            vote_proxy = interface.CurveYCRVVoter(self.strategy.voter())
            swap = interface.CurveSwap(curve.registry.get_pool_from_lp_token(self.token))
            gauge = interface.CurveGauge(self.strategy.gauge())
            info.update(curve.calculate_boost(gauge, vote_proxy))
            info.update(curve.calculate_apy(gauge, swap))
            info["earned"] = gauge.claimable_tokens.call(vote_proxy).to("ether")

        if hasattr(self.strategy, "earned"):
            info["lifetime earned"] = self.strategy.earned() / scale

        if self.strategy._name == "StrategyYFIGovernance":
            ygov = interface.YearnGovernance(self.strategy.gov())
            info["earned"] = ygov.earned(self.strategy) / 1e18
            info["reward rate"] = ygov.rewardRate() / 1e18
            info["ygov balance"] = ygov.balanceOf(self.strategy) / 1e18
            info["ygov total"] = ygov.totalSupply() / 1e18

        if "token price" not in info:
            if self.name in ["aLINK"]:
                info["token price"] = uniswap.token_price(self.vault.underlying())
            elif self.name in ["USDC", "TUSD", "DAI", "USDT"]:
                info["token price"] = 1
            else:
                info["token price"] = uniswap.token_price(self.token)

        info["tvl"] = info["vault balance"] * info["token price"]
        return info


def load_registry(address="registry.ychad.eth"):
    return interface.YRegistry(web3.ens.resolve(address))


def load_vaults(registry):
    return [VaultV1(*params) for params in zip(registry.getVaults(), *registry.getVaultsInfo())]
