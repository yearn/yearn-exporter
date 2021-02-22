from dataclasses import dataclass
from typing import Optional
import warnings

from brownie import interface, web3, Contract
from brownie.network.contract import InterfaceContainer

from yearn import constants, curve, uniswap
from yearn.mutlicall import fetch_multicall


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
        if self.strategy not in constants.STRATEGY_INTERFACES:
            warnings.warn(f'no strategy interface for {self.strategy}, reading from etherscan')
        self.strategy = constants.STRATEGY_INTERFACES.get(self.strategy, Contract)(self.strategy)
        self.token = interface.ERC20(self.token)
        if str(self.vault) not in constants.VAULT_ALIASES:
            warnings.warn(f'no vault alias for {self.vault}, reading from vault.sybmol()')
        self.name = constants.VAULT_ALIASES.get(str(self.vault), self.vault.symbol())
        self.decimals = self.vault.decimals()  # vaults inherit decimals from token

    def describe(self):
        scale = 10 ** self.decimals
        info = {}
        try:
            info['share price'] = self.vault.getPricePerFullShare() / 1e18
        except ValueError:
            # no money in vault, exit early
            return {'tvl': 0}

        attrs = {
            'vault balance': [self.vault, 'balance'],
            'vault total': [self.vault, 'totalSupply'],
            'strategy balance': [self.strategy, 'balanceOf'],
        }

        # some of the oldest vaults don't implement these methods
        if hasattr(self.vault, "available"):
            attrs['available'] = [self.vault, 'available']

        if hasattr(self.vault, "min") and hasattr(self.vault, "max"):
            attrs['min'] = [self.vault, 'min']
            attrs['max'] = [self.vault, 'max']

        # new curve voter proxy vaults
        if hasattr(self.strategy, "proxy"):
            results = fetch_multicall(
                [self.strategy, 'voter'],
                [curve.registry, 'get_pool_from_lp_token', self.token],
                [self.strategy, 'gauge'],
            )
            vote_proxy = interface.CurveYCRVVoter(results[0])
            swap = interface.CurveSwap(results[1])
            gauge = interface.CurveGauge(results[2])
            info.update(curve.calculate_boost(gauge, vote_proxy))
            info.update(curve.calculate_apy(gauge, swap))
            info["earned"] = gauge.claimable_tokens.call(vote_proxy).to("ether")

        if hasattr(self.strategy, "earned"):
            info["lifetime earned"] = self.strategy.earned() / scale

        if self.strategy._name == "StrategyYFIGovernance":
            ygov = interface.YearnGovernance(self.strategy.gov())
            attrs["earned"] = [ygov, 'earned', self.strategy]
            attrs["reward rate"] = [ygov, 'rewardRate']
            attrs["ygov balance"] = [ygov, 'balanceOf', self.strategy]
            attrs["ygov total"] = [ygov, 'totalSupply']

        # fetch attrs as multicall
        try:
            results = fetch_multicall(*attrs.values())
        except ValueError:
            pass
        else:
            for name, attr in zip(attrs, results):
                info[name] = attr / scale
        
        # some additional post-processing
        if 'min' in info:
            info["strategy buffer"] = info.pop('min') / info.pop('max')

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
