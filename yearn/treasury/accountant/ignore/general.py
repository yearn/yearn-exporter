
import logging
from decimal import Decimal

from brownie import ZERO_ADDRESS, chain
from brownie.exceptions import RPCRequestError
from pony.orm import commit, select
from requests import HTTPError
from y import ContractNotVerified, Network, get_price
from y.constants import CHAINID
from y.networks import Network

from yearn.constants import ERC20_TRANSFER_EVENT_HASH, TREASURY_WALLETS
from yearn.entities import TreasuryTx
from yearn.events import decode_logs, get_logs_asap
from yearn.outputs.postgres.utils import (address_dbid, chain_dbid,
                                          cache_txgroup, token_dbid)
from yearn.prices import constants
from yearn.treasury.accountant.classes import Filter, HashMatcher
from yearn.treasury.accountant.constants import (DISPERSE_APP, PENDING_LABEL,
                                                 treasury)

logger = logging.getLogger(__name__)


def is_internal_transfer(tx: TreasuryTx) -> bool:
    if CHAINID == Network.Mainnet and tx.block > 17162286 and "yMechs Multisig" in [tx._from_nickname, tx._to_nickname]:
        # as of may 1 2023, ymechs wallet split from treasury
        return False
    return tx.to_address.address in treasury.addresses and tx.from_address.address in treasury.addresses

def has_amount_zero(tx: TreasuryTx) -> bool:
    return tx.amount == 0

def is_disperse_dot_app(tx: TreasuryTx) -> bool:
    if tx._to_nickname != "Disperse.app":
        return False
    eee_address = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
    # Make sure the other side of disperse.app txs are in the pg db.
    query = select(t for t in TreasuryTx if t.hash == tx.hash and t._from_nickname == "Disperse.app" and t.token == tx.token)
    if len(query) == 0 and "Transfer" in tx._events and tx.token != eee_address:
        # find transfer events and add txs to pg
        transfers = [
            transfer
            for transfer in get_logs_asap(None, [ERC20_TRANSFER_EVENT_HASH], tx.block, tx.block)
            if transfer.transactionHash.hex() == tx.hash
        ]
        print(f'len logs: {len(tx._events["Transfer"])}')
        for transfer in transfers:
            if tx.token == transfer.address:
                sender, receiver, amount = decode_logs([transfer])["Transfer"][0].values()
                if sender == DISPERSE_APP:
                    amount /= Decimal(tx.token.scale)
                    price = Decimal(get_price(transfer.address, block=tx.block))
                    TreasuryTx(
                        chain = chain_dbid(),
                        timestamp = chain[tx.block].timestamp,
                        block = tx.block,
                        hash = tx.hash,
                        log_index = transfer.logIndex,
                        # NOTE: We pass the entity pk instead of the entity obj so we can avoid the occasional 
                        #       `TransactionError("An attempt to mix objects belonging to different transactions")`
                        #       when processing never-before-seen entities.
                        token = token_dbid(transfer.address),
                        from_address = tx.to_address,
                        to_address = address_dbid(receiver),
                        amount = amount,
                        price = round(price, 18),
                        value_usd = round(amount * price, 18),
                        txgroup = cache_txgroup(PENDING_LABEL).txgroup_id,
                    )
        commit()

        # Only sort the input tx once we are sure we have the output txs
        # NOTE this only works for ERC20s
        if len(query) == len(transfers) and len(query) > 0:
            return True
    
    if len(query) == 0 and tx.token == eee_address and tx.to_address:
        # find internal txs and add to pg
        try:
            for int_tx in chain.get_transaction(tx.hash).internal_transfers:
                if tx.to_address == int_tx['from']:
                    amount = int_tx['value'] / Decimal(tx.token.scale)
                    price = Decimal(get_price(eee_address, tx.block))
                    TreasuryTx(
                        chain = chain_dbid(),
                        timestamp = chain[tx.block].timestamp,
                        block = tx.block,
                        hash = tx.hash,
                        log_index = None,
                        token = token_dbid("0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"),
                        from_address = tx.to_address,
                        to_address = address_dbid(int_tx['to']),
                        amount = amount,
                        price = round(price, 18),
                        value_usd = round(amount * price, 18),
                        txgroup = cache_txgroup(PENDING_LABEL).txgroup_id,
                    )
            commit()
        except HTTPError as e:
            print(e.response.__dict__)
            raise
    
    # Did we already insert the outputs for this disperse tx / token? 
    return len(query) > 0

def is_gnosis_execution(tx: TreasuryTx) -> bool:
    if tx.amount != 0 or tx.to_address.address not in treasury.addresses:
        return False
    
    try:
        con = tx.to_address.contract
    except ContractNotVerified:
        return False

    if con._build['contractName'] != "GnosisSafeProxy":
        return False
    
    if tx._transaction.status == 0: # Reverted
        return True
    try:
        events = tx._events
    except RPCRequestError:
        return False
    return "ExecutionSuccess" in events

def is_weth(tx: TreasuryTx) -> bool:
    # Withdrawal
    if tx.from_address == ZERO_ADDRESS and tx.to_address.address in treasury.addresses and tx.token == constants.weth:
        return True
    if tx.from_address.address in treasury.addresses and tx.to_address == constants.weth and tx.token == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
        return True
    if tx.from_address.address in treasury.addresses and tx.to_address == ZERO_ADDRESS and tx.token == constants.weth:
        return True
    if tx.from_address == constants.weth and tx.to_address.address in treasury.addresses and tx.token == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
        return True
    return False

def is_stream_replenishment(tx: TreasuryTx) -> bool:
    if tx._to_nickname in  ["Contract: LlamaPay", "Vesting Escrow Factory"]:
        return True
    
    # Puling unused funds back from vesting escrow / llamapay
    elif tx in HashMatcher({
        Network.Mainnet: [
            ["0x1621ba5c9b57930c97cc43d5d6d401ee9c69fed435b0b458ee031544a10bfa75", Filter('log_index', 487)],
        ],
    }.get(CHAINID, [])) or tx._from_nickname == "Contract: LlamaPay":
        if tx.amount > 0:
            tx.amount *= -1
        if tx.value_usd > 0:
            tx.value_usd *= -1
        return True
    return False

def is_scam_airdrop(tx: TreasuryTx) -> bool:
    hashes = {
        Network.Mainnet: [
            "0x9db063448c75a204148f4ede546223342463e288bcce7ebf1ed476e296f62824",
        ]
    }.get(CHAINID, [])
    return tx in HashMatcher(hashes)

_OTC_TRADER_ADDRESS = "0xfa42022707f02cFfC80557B166d625D52346dd6d"

def is_otc_trader(tx: TreasuryTx) -> bool:
    """ Yearn supplied liquidity so people could convert from YFI <> WOOFY on Fantom. """ 
    return tx.to_address is not None and _OTC_TRADER_ADDRESS in [tx.from_address.address, tx.to_address.address]

def is_reclaim_locked_vest(tx: TreasuryTx) -> bool:
    """Unvested portion of vesting packages clawed back to prepare for veYFI"""
    return tx in HashMatcher(["0x4a9b8af71ab412a0b0cbe948d5a99b49cfe7e72b73d9f5b5d90e418352965dcf"])

def is_lido_dev(tx: TreasuryTx) -> bool:
    """Yearn had some LDO tokens from Lido that it can spend on any Lido-related dev expense"""
    return tx in HashMatcher([
        ["0x44fdf3172c73b410400718badc7801a7fc496227b5325d90ed840033e16d8366", Filter('_symbol', 'LDO')],
    ])

def is_ycrv_for_testing(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        # Sent as yvBoost from a contributor, sent back as st-yCRV when testing complete
        "0x6dc184b139f9139e1957fd13c79b88bbc3d7aaa4d1763636c3243c6034318957",
        "0xcca77bd81437b603c4ec06d3be355aada276bac1a93ac9a77748a67799f1cc96",
        
        # sent as st-yCRV, sent back as CRV when testing complete
        "0xcbf408c7edcc9aab0d81822308009995caf12c0399da39c7d7febbf5692ea5fe",
        "0x97216ee7b0d3b474de38e0a5b978e20e6f636cc019eac75cd591280b6b8efc80",
        ["0x85dc73fca1a8ec500bc46cd18782b8bba4c811714597fbdaaa209ac9f0c7f253", Filter('log_index', 279)],
    ])

VESTING_FACTORY = "0x98d3872b4025ABE58C4667216047Fe549378d90f"

def is_vest_factory(tx: TreasuryTx) -> bool:
    return tx.to_address == VESTING_FACTORY

def is_ignore_ymechs(tx: TreasuryTx) -> bool:
    """After may 1 2023 ymechs wallet separated from yearn treasury"""
    if tx.block <= 17162286:
        return False
    return (
        (tx._from_nickname == "yMechs Multisig" and tx.to_address not in TREASURY_WALLETS)
        or (tx._to_nickname == "yMechs Multisig" and tx.from_address not in TREASURY_WALLETS)
    )

def is_returned_fundus(tx: TreasuryTx) -> bool:
    """A user accientally refunded their yield to yChad, yChad sent it back."""
    return tx.hash == "0x2c2fb9d88a7a25b100ae3ba08bdb1cafbbd6a63386a08fdcfe32d077836defa3" or (
        tx.hash == "0xd7e7abe600aad4a3181a3a410bef2539389579d2ed28f3e75dbbf3a7d8613688" and tx.log_index == 556
    )
