from brownie import chain
from brownie.exceptions import CompilerError
from pony.orm import db_session, select
from yearn import constants
from yearn.entities import Address
from yearn.networks import Network
from yearn.outputs.postgres.utils import cache_address
from yearn.utils import contract


@db_session
def prepare_db() -> None:
    cache_treasury()
    cache_ychad()
    cache_sms()
    cache_address_nicknames_for_tokens()
    cache_address_nicknames_for_contracts()

def cache_ychad() -> None:
    """ Label yChad in pg. """
    cache_address(constants.YCHAD_MULTISIG).nickname = "Yearn yChad Multisig"

def cache_sms() -> None:
    """ Label SMS in pg. """
    assert len(constants.STRATEGIST_MULTISIG) == 1, "This code was built for only one SMS. You're going to need to make some updates."
    for msig in constants.STRATEGIST_MULTISIG:
        cache_address(msig).nickname = "Yearn Strategist Multisig"

def cache_treasury() -> None:
    """ Label treasury in pg. """
    if constants.TREASURY_MULTISIG:
        cache_address(constants.TREASURY_MULTISIG).nickname = "Yearn Treasury"

    if chain.id == Network.Mainnet:
        treasury_v1_andres_wallet = "0xb99a40fcE04cb740EB79fC04976CA15aF69AaaaE"
        cache_address(treasury_v1_andres_wallet).nickname = "Yearn Treasury V1"

def cache_address_nicknames_for_tokens() -> None:
    """ Set address.nickname for addresses belonging to tokens. """
    for address in select(a for a in Address if a.token and not a.nickname):
        address.nickname = f"Token: {address.token.name}"

def cache_address_nicknames_for_contracts() -> None:
    """ Set address.nickname for addresses belonging to non-token contracts. """
    for address in select(a for a in Address if a.is_contract and not a.token and (not a.nickname or a.nickname.startswith("Non-Verified")) and a.chain.chainid == chain.id):
        try:
            address.nickname = f"Contract: {contract(address.address)._build['contractName']}"
        except ValueError as e:
            if "Contract source code not verified" not in str(e):
                raise
            address.nickname = f"Non-Verified Contract: {address.address}"
        except CompilerError:
            pass
