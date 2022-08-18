
import logging
from typing import Optional

from brownie import chain
from yearn.entities import TreasuryTx, TxGroup
from yearn.multicall2 import fetch_multicall
from yearn.networks import Network
from yearn.treasury.accountant.classes import TopLevelTxGroup
from yearn.treasury.treasury import YearnTreasury
from yearn.utils import contract
from yearn.v1.registry import Registry as RegistryV1
from yearn.v2.registry import Registry as RegistryV2

logger = logging.getLogger(__name__)

FEES_LABEL = "Protocol Revenue"
fees = TopLevelTxGroup(FEES_LABEL)

v1 = RegistryV1() if chain.id == Network.Mainnet else None
v2 = RegistryV2()

treasury = YearnTreasury()

def is_fees_v1(tx: TreasuryTx) -> bool:
    if chain.id != Network.Mainnet:
        return False

    if not tx.to_address or tx.to_address.address not in treasury.addresses:
        return False

    for vault in v1.vaults:
        if (
            tx.token.address.address != vault.token.address
            # Fees from single-sided strategies are not denominated in `vault.token`
            and not (tx.token.symbol == "y3Crv" and tx.from_address.nickname.startswith("Contract: Strategy") and tx.from_address.nickname.endswith("3pool"))
            and not (tx.token.symbol == "yyDAI+yUSDC+yUSDT+yTUSD" and tx.from_address.nickname.startswith("Contract: Strategy") and tx.from_address.nickname.endswith("ypool"))
            ):
            continue
        
        try:
            controller = contract(vault.vault.controller(block_identifier=tx.block))
        except Exception as e:
            known_exceptions = [
                "No data was returned - the call likely reverted",
            ]

            if str(e) not in known_exceptions:
                raise

            continue

        if [tx.from_address.address, tx.to_address.address] == fetch_multicall([controller, 'strategies',vault.token.address],[controller,'rewards'], block=tx.block):
            return True

    return False

def is_fees_v2(tx: TreasuryTx) -> Optional[TxGroup]:
    return any(
        tx.from_address.address == vault.vault.address 
        and tx.token.address.address == vault.vault.address
        and tx.to_address.address in treasury.addresses
        and tx.to_address.address == vault.vault.rewards(block_identifier=tx.block)
        for vault in v2.vaults + v2.experiments
    )

def is_fees_v3(tx: TreasuryTx) -> Optional[TxGroup]:
    # Stay tuned...
    return False

def is_keep_beets(tx: TreasuryTx) -> bool:
    if chain.id != Network.Fantom:
        return False

    if tx.token.symbol == "BEETS" and tx.to_address and tx.to_address.address in treasury.addresses and tx.hash != "0x1e997aa8c79ece76face8deb8fe7df4cea4f6a1ef7cd28501013ed30dfbe238f":
        return True


fees.create_child("Vaults V1", is_fees_v1)
fees.create_child("Vaults V2", is_fees_v2)
fees.create_child("Vaults V3", is_fees_v3)
fees.create_child("KeepBEETS", is_keep_beets)
