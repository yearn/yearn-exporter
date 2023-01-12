import logging
from typing import Optional

from brownie import ZERO_ADDRESS, chain, convert
from brownie.convert.datatypes import HexString
from pony.orm import ObjectNotFound, db_session, select
from yearn.entities import (Address, Chain, Token, TreasuryTx, TxGroup, UserTx,
                            db)
from yearn.multicall2 import fetch_multicall
from yearn.networks import Network
from yearn.utils import contract, is_contract, hex_to_string

logger = logging.getLogger(__name__)

@db_session
def cache_chain():
    _chain = Chain.get(chainid=chain.id)
    if not _chain:
        _chain = Chain(
            chain_name = Network(chain.id).name,
            chainid = chain.id,
            victoria_metrics_label = Network.label(chain.id)
        )
    return _chain

@db_session
def cache_address(address: str) -> Address:
    address = convert.to_address(address)
    chain = cache_chain()
    address_entity = Address.get(address=address, chain=chain)
    if not address_entity:
        address_entity = Address(
            address=address,
            chain=chain,
            is_contract=is_contract(address)
        )
    return address_entity

@db_session
def cache_token(address: str) -> Token:
    address_entity = cache_address(address)
    token = Token.get(address=address_entity)
    if not token:
        if convert.to_address(address) == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
            symbol, name = {
                Network.Mainnet: ("ETH","Ethereum"),
                Network.Fantom: ("FTM","Fantom"),
                Network.Arbitrum: ("ETH", "Ethereum"),
                Network.Optimism: ("ETH", "Ethereum"),
            }[chain.id]
            decimals = 18
        else:
            token = contract(address)
            symbol, name, decimals = fetch_multicall([token,'symbol'],[token,'name'],[token,'decimals'])

            # MKR contract returns name and symbol as bytes32 which is converted to a brownie HexString
            # try to decode it
            if isinstance(name, HexString):
                name = hex_to_string(name)
            if isinstance(symbol, HexString):
                symbol = hex_to_string(symbol)
        try:
            token = Token(
                address=address_entity,
                symbol=symbol,
                name=name,
                decimals=decimals,
                chain=cache_chain()
            )
        except ValueError as e:
            """ Give us a little more info to help with debugging. """
            raise ValueError(str(e), token.address, symbol, name, decimals)
        logger.info(f'token {symbol} added to postgres')
    return token

@db_session    
def cache_txgroup(name: str, parent: Optional[TxGroup] = None) -> TxGroup:
    _txgroup = TxGroup.get(name=name)
    if not _txgroup:
        _txgroup = TxGroup(name=name, parent_txgroup=parent)
        logger.info(f'TxGroup {name} added to postgres')
    if parent != _txgroup.parent_txgroup:
        _txgroup.parent_txgroup = parent
    return _txgroup

@db_session
def last_recorded_block(Entity: db.Entity) -> int:
    '''
    Returns last block recorded for sql entity type `Entity`
    '''
    if Entity == UserTx:
        return select(max(e.block) for e in Entity if e.chain.chainid == chain.id).first()
    elif Entity == TreasuryTx:
        return select(max(e.block) for e in Entity if e.chain.chainid == chain.id).first()
    return select(max(e.block) for e in Entity if e.chainid == chain.id).first()

@db_session
def fetch_balances(vault_address: str, block=None):
    token_dbid = select(t.token_id for t in Token if t.chain.chainid == chain.id and t.address.address == vault_address).first()
    if block and block > last_recorded_block(UserTx):
        # NOTE: we use `postgres.` instead of `self.` so we can make use of parallelism
        raise Exception('this block has not yet been cached into postgres')
    if block:
        balances = db.select(f"""
            a.wallet, coalesce(amount_in,0) - coalesce(amount_out,0) balance
            from (
                select "to" wallet, sum(amount) amount_in
                from user_txs where token_id = $token_dbid and block <= $block
                group by "to" ) a
            left join (
                select "from" wallet, sum(amount) amount_out
                from user_txs where token_id = $token_dbid and block <= $block
                group by "from") b on a.wallet = b.wallet
                """)
    else:
        balances = db.select(f"""
            a.wallet, coalesce(amount_in,0) - coalesce(amount_out,0) balance
            from (
                select "to" wallet, sum(amount) amount_in
                from user_txs where token_id = $token_dbid
                group by "to" ) a
            left join (
                select "from" wallet, sum(amount) amount_out
                from user_txs where token_id = $token_dbid
                group by "from") b on a.wallet = b.wallet
                """)
    return {wallet: balance for wallet,balance in balances if wallet != ZERO_ADDRESS}
