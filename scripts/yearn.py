import warnings
from dataclasses import dataclass
from typing import Optional, Union

from brownie import chain, interface, web3, accounts, rpc
from brownie.network.contract import InterfaceContainer
from click import secho
from prometheus_client import start_http_server, Gauge

from yearn import constants, curve, uniswap

warnings.simplefilter('ignore')


@dataclass
class Vault:
    vault: Union[str, InterfaceContainer]
    controller: Union[str, InterfaceContainer]
    token: Union[str, interface.ERC20]
    strategy: str
    is_wrapped: bool
    is_delegated: bool
    # the rest is populated in post init
    name: Optional[str] = None

    def __post_init__(self):
        self.vault = constants.VAULT_INTERFACES.get(self.vault, interface.yVault)(self.vault)
        self.controller = constants.CONTROLLER_INTERFACES[self.controller](self.controller)
        self.strategy = constants.STRATEGY_INTERFACES[self.strategy](self.strategy)
        self.token = interface.ERC20(self.token)
        self.name = constants.VAULT_ALIASES[str(self.vault)]

    @property
    def scale(self):
        return 10 ** self.vault.decimals()


def load_registry(address='registry.ychad.eth'):
    return interface.YRegistry(address)


def load_vaults(registry):
    # TODO: this should be heavily cached
    return [Vault(*params) for params in zip(registry.getVaults(), *registry.getVaultsInfo())]


def describe_vault(vault: Vault):
    info = {
        'vault balance': vault.vault.balance() / vault.scale,
        'share price': vault.vault.getPricePerFullShare() / 1e18,
        'vault total': vault.vault.totalSupply() / vault.scale,
        'strategy balance': vault.strategy.balanceOf() / vault.scale,
    }

    # some of the oldest vaults don't implement these methods
    if hasattr(vault.vault, 'available'):
        info['available'] = vault.vault.available() / vault.scale

    if hasattr(vault.vault, 'min') and hasattr(vault.vault, 'max'):
        info['strategy buffer'] = vault.vault.min() / vault.vault.max()

    # new curve voter proxy vaults
    if hasattr(vault.strategy, 'proxy'):
        strategy_proxy = interface.StrategyProxy(vault.strategy.proxy())
        vote_proxy = interface.CurveYCRVVoter(vault.strategy.voter())
        escrow = interface.CurveVotingEscrow(vote_proxy.escrow())
        swap = interface.CurveSwap(vault.strategy.curve())
        gauge = interface.CurveGauge(vault.strategy.gauge())
        info.update(curve.calculate_boost(gauge, vote_proxy))
        info.update(curve.calculate_apy(gauge, swap))

    if vault.strategy._name == 'StrategyYFIGovernance':
        ygov = interface.YearnGovernance(vault.strategy.gov())
        info['earned'] = ygov.earned(vault.strategy) / 1e18
        info['reward rate'] = ygov.rewardRate() / 1e18
        info['ygov balance'] = ygov.balanceOf(vault.strategy) / 1e18
        info['ygov total'] = ygov.totalSupply() / 1e18
        info['token price'] = uniswap.price_router(vault.token, uniswap.usdc)

    return info


def develop():
    registry = load_registry()
    vaults = load_vaults(registry)
    for i, vault in enumerate(vaults):
        secho(vault.name, fg='yellow')
        secho(str(vault), dim=True)
        # info = describe_vault(vault)
        # for a, b in info.items():
            # print(f'{a} = {b}')


def exporter():
    prom_gauge = Gauge('yearn', 'yearn stats', ['vault', 'param'])
    timing = Gauge('yearn_timing', '', ['vault', 'action'])
    start_http_server(8800)
    registry = load_registry()
    for block in chain.new_blocks():
        secho(f'{block.number}', fg='green')
        with timing.labels('registry', 'load').time():
            vaults = load_vaults(registry)
        for vault in vaults:
            with timing.labels(vault.name, 'describe').time():
                info = describe_vault(vault)
            for param, value in info.items():
                # print(f'{param} = {value}')
                prom_gauge.labels(vault.name, param).set(value)


def audit():
    """
    Audit vault and strategy configuration.
    """
    governance = web3.ens.resolve('ychad.eth')
    registry = load_registry()
    vaults = load_vaults(registry)
    for v in vaults:
        if v.vault.governance() != governance:
            secho(f'{v.name} vault governance == {v.vault.governance()}', fg='red')
            print(f'{v.vault}.setGovernance({governance})')
        if v.strategy.governance() != governance:
            secho(f'{v.name} strategy governance == {v.strategy.governance()}', fg='red')
            print(f'{v.strategy}.setGovernance({governance})')


def lp():
    pool_info = {
        'compound': {
            'swap': '0xA2B47E3D5c44877cca798226B7B8118F9BFb7A56',
            'swap_token': '0x845838DF265Dcd2c412A1Dc9e959c7d08537f8a2',
            'gauge': '0x7ca5b0a2910B33e9759DC7dDB0413949071D7575',
        },
        'usdt': {
            'swap': '0x52EA46506B9CC5Ef470C5bf89f17Dc28bB35D85C',
            'swap_token': '0x9fC689CCaDa600B6DF723D9E47D84d76664a1F23',
            'gauge': '0xBC89cd85491d81C6AD2954E6d0362Ee29fCa8F53',
        },
        'y': {
            'swap': '0x45F783CCE6B7FF23B2ab2D70e416cdb7D6055f51',
            'swap_token': '0xdF5e0e81Dff6FAF3A7e52BA697820c5e32D806A8',
            'gauge': '0xFA712EE4788C042e2B7BB55E6cb8ec569C4530c1',
        },
        'busd': {
            'swap': '0x79a8C46DeA5aDa233ABaFFD40F3A0A2B1e5A4F27',
            'swap_token': '0x3B3Ac5386837Dc563660FB6a0937DFAa5924333B',
            'gauge': '0x69Fb7c45726cfE2baDeE8317005d3F94bE838840',
        },
        'susdv2': {
            'swap': '0xA5407eAE9Ba41422680e2e00537571bcC53efBfD',
            'swap_token': '0xC25a3A3b969415c80451098fa907EC722572917F',
            'gauge': '0xA90996896660DEcC6E997655E065b23788857849',
        },
        'pax': {
            'swap': '0x06364f10B501e868329afBc005b3492902d6C763',
            'swap_token': '0xD905e2eaeBe188fc92179b6350807D8bd91Db0D8',
            'gauge': '0x64E3C23bfc40722d3B649844055F1D51c1ac041d',
        },
        'ren': {
            'swap': '0x93054188d876f558f4a66B2EF1d97d16eDf0895B',
            'swap_token': '0x49849C98ae39Fff122806C06791Fa73784FB3675',
            'gauge': '0xB1F2cdeC61db658F091671F5f199635aEF202CAC',
        },
        'sbtc': {
            'swap': '0x7fC77b5c7614E1533320Ea6DDc2Eb61fa00A9714',
            'swap_token': '0x075b1bb99792c9E1041bA13afEf80C91a1e70fB3',
            'gauge': '0x705350c4BcD35c9441419DdD5d2f097d7a55410F',
        },
    }
    for name, item in pool_info.items():
        swap = interface.CurveSwap(item['swap'])
        gauge = interface.CurveGauge(item['gauge'])
        print(name, curve.calculate_apy(gauge, swap))


def harvest():
    assert rpc.is_active()
    andre = accounts.at('andrecronje.eth', force=True)
    print(andre)
    governance = web3.ens.resolve('ychad.eth')
    registry = load_registry()
    vaults = load_vaults(registry)
    for v in vaults:
        secho(v.name, fg='green')
        print(v)
        try:
            tx = v.strategy.harvest({'from': andre})
            tx.info()
        except AttributeError:
            pass
