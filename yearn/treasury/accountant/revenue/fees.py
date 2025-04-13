
import asyncio
import logging

from dank_mids.helpers import lru_cache_lite
from y import Contract

from yearn.entities import TreasuryTx
from yearn.treasury.accountant.constants import treasury, v1, v2
#raise Exception('loaded constants')

logger = logging.getLogger(__name__)

_vaults = asyncio.get_event_loop().run_until_complete(v2.vaults)
logger.info('%s v2 vaults loaded', len(_vaults))
_experiments = asyncio.get_event_loop().run_until_complete(v2.experiments)
logger.info('%s v2 experiments loaded', len(_experiments))
_removed = asyncio.get_event_loop().run_until_complete(v2.removed)
logger.info('%s removed v2 vaults loaded', len(_removed))
v2_vaults = _vaults + _experiments + _removed


# v1 helpers
_is_y3crv = lambda tx: tx._symbol == "y3Crv" and tx._from_nickname.startswith("Contract: Strategy") and tx._from_nickname.endswith("3pool")
_is_ypool = lambda tx: tx._symbol == "yyDAI+yUSDC+yUSDT+yTUSD" and tx._from_nickname.startswith("Contract: Strategy") and tx._from_nickname.endswith("ypool")

@lru_cache_lite
def _get_rewards(controller: Contract, block: int) -> str:
    try:
        return controller.rewards(block_identifier=block)
    except ValueError as e:
        if str(e) == "No data was returned - the call likely reverted":
            return None
        raise


def is_fees_v1(tx: TreasuryTx) -> bool:
    if tx.to_address.address not in treasury.addresses:
        return False

    for vault in v1.vaults:
        if tx.token != vault.token.address:
            # Fees from single-sided strategies are not denominated in `vault.token`
            if not (_is_y3crv(tx) or _is_ypool(tx)):
                continue
        
        rewards = _get_rewards(vault.controller, tx.block)
        if tx.to_address != rewards:
            logger.debug('to address %s doesnt match rewards address %s', tx.to_address.address, rewards)
            continue
        strategy = vault.controller.strategies(vault.token.address, block_identifier=tx.block)
        if tx.from_address != strategy:
            logger.debug('from address %s doesnt match strategy %s set on controller %s', tx.from_address.address, strategy, vault.controller)
            continue
        return True
    return False


def is_fees_v2(tx: TreasuryTx) -> bool:
    if tx.to_address.address not in treasury.addresses:
        return False
    if any(
        tx.from_address == vault.vault.address 
        and tx.token == vault.vault.address
        and tx.to_address == vault.vault.rewards(block_identifier=tx.block)
        for vault in v2_vaults
    ):
        return True
    elif is_inverse_fees_from_stash_contract(tx):
        if tx.value_usd > 0:
            tx.value_usd *= -1
        return True
    return False

def is_fees_v3(tx: TreasuryTx) -> bool:
    # Stay tuned...
    return False

def is_yearn_fed_fees(tx: TreasuryTx) -> bool:
    if tx.to_address.address in treasury.addresses:
        # New version
        if tx._symbol in ["yvCurve-DOLA-U", "CRV"] and tx.from_address == "0x64e4fC597C70B26102464B7F70B1F00C77352910":
            return True
        # Old versions
        if tx._symbol in ["yvCurve-DOLA-U", "yveCRV-DAO"] and tx.from_address in ["0x09F61718474e2FFB884f438275C0405E3D3559d3", "0x7928becDda70755B9ABD5eE7c7D5E267F1412042"]:
            return True
        if tx._symbol == "INV" and tx._from_nickname == "Inverse Treasury" and tx._to_nickname == "ySwap Multisig":
            return True
        if tx.from_address == "0x9D5Df30F475CEA915b1ed4C0CCa59255C897b61B" and tx._to_nickname == "ySwap Multisig":
            return True
    return False

def is_dolafraxbp_fees(tx: TreasuryTx) -> bool:
    return tx._from_nickname == "Contract: StrategyConvexFraxBpRewardsClonable" and tx._to_nickname == "Yearn yChad Multisig" and tx._symbol == "yvCurve-DOLA-FRAXBP-U"

def is_temple(tx: TreasuryTx) -> bool:
    if tx._to_nickname in  ["Yearn Treasury", "Yearn yChad Multisig"]: # fees have been sent to both
        if tx._from_nickname == "Contract: StrategyConvexCrvCvxPairsClonable" and tx._symbol == "CRV":
            return True
        elif tx._from_nickname == "Contract: Splitter" and tx._symbol in ["yveCRV-DAO","CRV"]:
            return True
    return False

def is_inverse_fees_from_stash_contract(tx: TreasuryTx) -> bool:
    return tx.from_address == "0xE376e8e8E3B0793CD61C6F1283bA18548b726C2e" and tx.to_address.nickname == "Token: Curve stETH Pool yVault"
