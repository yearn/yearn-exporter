from typing import Optional
from dataclasses import dataclass

from brownie import interface
from brownie.network.contract import InterfaceContainer

from yearn import constants


@dataclass
class Vault:
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
        self.strategy = constants.STRATEGY_INTERFACES[self.strategy](self.strategy)
        self.token = interface.ERC20(self.token)
        self.name = constants.VAULT_ALIASES[str(self.vault)]
        self.decimals = self.vault.decimals()  # vaults inherit decimals from token

    @property
    def scale(self):
        return 10 ** self.decimals


def load_registry(address="registry.ychad.eth"):
    return interface.YRegistry(address)


def load_vaults(registry):
    return [Vault(*params) for params in zip(registry.getVaults(), *registry.getVaultsInfo())]
