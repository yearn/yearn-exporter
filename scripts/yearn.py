import warnings
from dataclasses import dataclass
from typing import Optional, Union

from brownie import interface
from brownie.network.contract import InterfaceContainer
from click import secho

warnings.simplefilter('ignore')

CONTROLLER_INTERFACES = {
    '0x2be5D998C95DE70D9A38b3d78e49751F10F9E88b': interface.ControllerV1,
    '0x9E65Ad11b299CA0Abefc2799dDB6314Ef2d91080': interface.ControllerV2,
}

VAULT_INTERFACES = {
    '0x29E240CFD7946BA20895a7a02eDb25C210f9f324': interface.yDelegatedVault,
    '0x881b06da56BB5675c54E4Ed311c21E54C5025298': interface.yWrappedVault,
}

STRATEGY_INTERFACES = {
    '0x25fAcA21dd2Ad7eDB3a027d543e617496820d8d6': interface.StrategyVaultUSDC,
    '0xA30d1D98C502378ad61Fe71BcDc3a808CF60b897': interface.StrategyDForceUSDC,
    '0xc999fb87AcA383A63D804A575396F65A55aa5aC8': interface.StrategyCurveYCRVVoter,
    '0x1d91E3F77271ed069618b4BA06d19821BC2ed8b0': interface.StrategyTUSDCurve,
    '0xAa880345A3147a1fC6889080401C791813ed08Dc': interface.StrategyDAICurve,
    '0x787C771035bDE631391ced5C083db424A4A64bD8': interface.StrategyDForceUSDT,
    '0x40BD98e3ccE4F34c087a73DD3d05558733549afB': interface.StrategyCreamYFI,
    '0x2EE856843bB65c244F527ad302d6d2853921727e': interface.StrategyCurveYBUSDVoterProxy,
    '0x4FEeaecED575239b46d70b50E13532ECB62e4ea8': interface.StrategyCurveSBTC,
    '0x932fc4fd0eEe66F22f1E23fBA74D7058391c0b15': interface.StrategyMKRVaultDAIDelegate,
}


@dataclass
class Vault:
    vault: Union[str, InterfaceContainer]
    controller: Union[str, InterfaceContainer]
    token: Union[str, interface.ERC20]
    strategy: str
    is_wrapped: bool
    is_delegated: bool
    # the rest is populated in post_init
    name: Optional[str] = None

    def __post_init__(self):
        self.vault = VAULT_INTERFACES.get(self.vault, interface.yVault)(self.vault)
        self.controller = CONTROLLER_INTERFACES[self.controller](self.controller)
        self.token = interface.ERC20(self.token)
        self.strategy = STRATEGY_INTERFACES[self.strategy](self.strategy)
        self.name = self.vault.name()

    @property
    def _vault_class(self):
        if self.is_delegated:
            return interface.YWrappedVault
        return interface.YVault

    @property
    def scale(self):
        return 10 ** self.vault.decimals()


def load_registry(address='registry.ychad.eth'):
    return interface.YRegistry(address)


def load_vaults(registry):
    return [Vault(*params) for params in zip(registry.getVaults(), *registry.getVaultsInfo())]


def exporter():
    registry = load_registry()
    vaults = load_vaults(registry)
    for i, vault in enumerate(vaults):
        secho(f'{i} {vault}', fg='green')
        secho(vault.name, fg='yellow')
        print('balance', vault.vault.balance() / vault.scale)
        if hasattr(vault.vault, 'available'):
            print('available', vault.vault.available() / vault.scale)
        print('price', vault.vault.getPricePerFullShare() / 1e18)
        print('total supply', vault.vault.totalSupply() / vault.scale)
        if hasattr(vault.vault, 'min') and hasattr(vault.vault, 'max'):
            print('strategy buffer', vault.vault.min() / vault.vault.max())
