from brownie import ZERO_ADDRESS, chain
from brownie.exceptions import CompilerError
from pony.orm import db_session, select
from tqdm import tqdm
from y.networks import Network

from yearn import constants
from yearn.entities import Address, db
from yearn.outputs.postgres.utils import cache_address
from yearn.partners.partners import partners
from yearn.treasury.accountant.constants import BRIDGE_ASSISTOOOR, DISPERSE_APP
from yearn.utils import contract


@db_session
def prepare_db() -> None:
    cache_address(ZERO_ADDRESS).nickname = "Zero Address"
    cache_treasury()
    cache_ychad()
    cache_sms()
    cache_ykp3r()
    cache_yswaps()
    cache_ymechs()
    cache_partners()
    cache_disperse_app()
    cache_stream_factory()
    cache_bridge_assistooor()
    cache_address_nicknames_for_tokens()

def cache_ychad() -> None:
    """ Label yChad in pg. """
    label = {
        Network.Mainnet: "yChad",
        Network.Fantom: "fChad",
    }.get(chain.id)

    if label:
        cache_address(constants.YCHAD_MULTISIG).nickname = f"Yearn {label} Multisig"
        db.commit()

def cache_ykp3r() -> None:
    """ Label yKP3R in pg. """
    if chain.id == Network.Mainnet:
        cache_address("0x8d12a197cb00d4747a1fe03395095ce2a5cc6819").nickname = "Yearn KP3R Wallet"
        db.commit()

def cache_yswaps() -> None:
    if chain.id == Network.Mainnet:
        cache_address("0x7d2aB9CA511EBD6F03971Fb417d3492aA82513f0").nickname = "ySwap Multisig"
        db.commit()

def cache_ymechs() -> None:
    if chain.id == Network.Mainnet:
        cache_address("0x2C01B4AD51a67E2d8F02208F54dF9aC4c0B778B6").nickname = "yMechs Multisig"
        db.commit()

def cache_sms() -> None:
    """ Label SMS in pg. """
    assert len(constants.STRATEGIST_MULTISIG) == 1, "This code was built for only one SMS. You're going to need to make some updates."
    for msig in constants.STRATEGIST_MULTISIG:
        cache_address(msig).nickname = "Yearn Strategist Multisig"

def cache_treasury() -> None:
    """ Label treasury in pg. """
    if constants.TREASURY_MULTISIG:
        cache_address(constants.TREASURY_MULTISIG).nickname = "Yearn Treasury"
        db.commit()

    if chain.id == Network.Mainnet:
        treasury_v1_andres_wallet = "0xb99a40fcE04cb740EB79fC04976CA15aF69AaaaE"
        cache_address(treasury_v1_andres_wallet).nickname = "Yearn Treasury V1"
        db.commit()

def cache_partners() -> None:
    """ Label partners in pg. """
    for partner in partners:
        cache_address(partner.treasury).nickname = "".join(word.capitalize() for word in partner.name.split()) + " Treasury"
        # coming soon...
        if hasattr(partner, 'retired_treasuries'):
            for t in partner.retired_treasuries:
                cache_address(t).nickname = "Retired ".join(word.capitalize() for word in partner.name.split()) + " Treasury"
        db.commit()

def cache_disperse_app() -> None:
    if DISPERSE_APP:
        cache_address(DISPERSE_APP).nickname = "Disperse.app"

def cache_bridge_assistooor() -> None:
    """ This wallet is an EOA that has been used to assist in bridging tokens across chains. """
    if BRIDGE_ASSISTOOOR:
        cache_address(BRIDGE_ASSISTOOOR).nickname = "Bridge Assistooor EOA"

def cache_stream_factory() -> None:
    if chain.id == Network.Mainnet:
        cache_address('0xB93427b83573C8F27a08A909045c3e809610411a').nickname = "Vesting Escrow Factory"

def cache_address_nicknames_for_tokens() -> None:
    """ Set address.nickname for addresses belonging to tokens. """
    for address in select(a for a in Address if a.token and not a.nickname):
        address.nickname = f"Token: {address.token.name}"
        db.commit()
