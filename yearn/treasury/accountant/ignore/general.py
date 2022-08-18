
from brownie import ZERO_ADDRESS, chain
from brownie.exceptions import RPCRequestError
from pony.orm import commit, select
from yearn.constants import ERC20_TRANSFER_EVENT_HASH
from yearn.entities import TreasuryTx
from yearn.events import decode_logs, get_logs_asap
from yearn.networks import Network
from yearn.outputs.postgres.utils import (cache_address, cache_chain,
                                          cache_token, cache_txgroup)
from yearn.prices import constants, magic
from yearn.treasury.accountant.classes import HashMatcher
from yearn.treasury.accountant.constants import (DISPERSE_APP, PENDING_LABEL,
                                                  treasury)
from yearn.utils import contract


def is_internal_transfer(tx: TreasuryTx) -> bool:
    return tx.to_address and tx.to_address.address in treasury.addresses and tx.from_address.address in treasury.addresses

def has_amount_zero(tx: TreasuryTx) -> bool:
    return tx.amount == 0

def is_disperse_dot_app(tx: TreasuryTx) -> bool:
    if tx._to_nickname == "Disperse.app":
        eee_address = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
        # Make sure the other side of disperse.app txs are in the pg db.
        query = select(t for t in TreasuryTx if t.hash == tx.hash and t._from_nickname == "Disperse.app" and t.token.address.address == tx.token.address.address)
        if len(query) == 0 and "Transfer" in tx._events and tx.token.address.address != eee_address:
            # find transfer events and add txs to pg
            transfers = [
                transfer
                for transfer in get_logs_asap(None, [ERC20_TRANSFER_EVENT_HASH], tx.block, tx.block)
                if transfer.transactionHash.hex() == tx.hash
            ]
            print(f'len logs: {len(tx._events["Transfer"])}')
            for transfer in transfers:
                sender, receiver, amount = decode_logs([transfer])["Transfer"][0].values()
                if sender == DISPERSE_APP and transfer.address == tx.token.address.address:
                    amount /= tx.token.scale
                    price = magic.get_price(transfer.address, block=tx.block)
                    TreasuryTx(
                        chain = cache_chain(),
                        timestamp = chain[tx.block].timestamp,
                        block = tx.block,
                        hash = tx.hash,
                        log_index = transfer.logIndex,
                        token = cache_token(transfer.address),
                        from_address = tx.to_address,
                        to_address = cache_address(receiver),
                        amount = amount,
                        price = price,
                        value_usd = amount * price,
                        txgroup = cache_txgroup(PENDING_LABEL),
                    )
            commit()

            # Only sort the input tx once we are sure we have the output txs
            # NOTE this only works for ERC20s
            if len(query) == len(transfers) and len(query) > 0:
                return True
        
        if len(query) == 0 and tx.token.address.address == eee_address and tx.to_address:
            # find internal txs and add to pg
            for int_tx in chain.get_transaction(tx.hash).internal_transfers:
                if int_tx['from'] == tx.to_address.address:
                    amount = int_tx['value'] / tx.token.scale
                    price = magic.get_price(eee_address, tx.block)
                    TreasuryTx(
                        chain = cache_chain(),
                        timestamp = chain[tx.block].timestamp,
                        block = tx.block,
                        hash = tx.hash,
                        log_index = None,
                        token = cache_token("0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"),
                        from_address = tx.to_address,
                        to_address = cache_address(int_tx['to']),
                        amount = amount,
                        price = price,
                        value_usd = amount * price,
                        txgroup = cache_txgroup(PENDING_LABEL),
                    )
            commit()
        
        # Did we already insert the outputs for this disperse tx / token? 
        if len(query) > 0:
            return True

def is_gnosis_execution(tx: TreasuryTx) -> bool:
    if (
        tx.amount == 0
        and tx.to_address
        and tx.to_address.address in treasury.addresses
        ):
        try:
            con = contract(tx.to_address.address)
        except ValueError as e:
            if "contract source code not verified" in str(e).lower() or str(e).endswith('has not been verified'):
                return False
            raise

        if con._build['contractName'] != "GnosisSafeProxy":
            return False
        
        if tx._transaction.status == 0: # Reverted
            return True
        try:
            events = tx._events
        except RPCRequestError:
            return False
        if "ExecutionSuccess" in events:
            return True

def is_weth(tx: TreasuryTx) -> bool:
    # Withdrawal
    if tx.from_address.address == ZERO_ADDRESS and tx.to_address and tx.to_address.address in treasury.addresses and tx.token.address.address == constants.weth:
        return True
    if tx.from_address.address in treasury.addresses and tx.to_address and tx.to_address.address == constants.weth and tx.token.address.address == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
        return True
    if tx.from_address.address in treasury.addresses and tx.to_address and tx.to_address.address == ZERO_ADDRESS and tx.token.address.address == constants.weth:
        return True
    if tx.from_address.address == constants.weth and tx.to_address and tx.to_address.address in treasury.addresses and tx.token.address.address == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
        return True

def is_scam_airdrop(tx: TreasuryTx) -> bool:
    hashes = {
        Network.Mainnet: [
            "0x9db063448c75a204148f4ede546223342463e288bcce7ebf1ed476e296f62824",
        ]
    }.get(chain.id, [])
    return tx in HashMatcher(hashes)

def is_otc_trader(tx: TreasuryTx) -> bool:
    """ Yearn supplied liquidity so people could convert from YFI <> WOOFY on Fantom. """ 
    OTC_TRADER_ADDRESS = "0xfa42022707f02cFfC80557B166d625D52346dd6d"
    if tx.to_address:
        return OTC_TRADER_ADDRESS in [tx.from_address.address, tx.to_address.address]
