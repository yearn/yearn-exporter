import logging
from decimal import Decimal
from typing import Dict, Optional

from brownie import ZERO_ADDRESS, chain, convert
from brownie.convert.datatypes import HexString
from pony.orm import db_session, select
from y import Contract, ContractNotVerified, Network

from yearn.entities import (Address, Chain, Token, TreasuryTx, TxGroup, UserTx,
                            db)
from yearn.multicall2 import fetch_multicall
from yearn.utils import hex_to_string, is_contract

logger = logging.getLogger(__name__)

UNI_V3_POS = {
    Network.Mainnet: "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
}.get(chain.id, 'not on this chain')

@db_session
def cache_chain():
    return Chain.get(chainid=chain.id) or Chain(
        chain_name=Network.name(),
        chainid=chain.id,
        victoria_metrics_label=Network.label(),
    )

@db_session
def cache_address(address: str) -> Address:
    address = convert.to_address(address)
    chain = cache_chain()
    address_entity = Address.get(address=address, chain=chain)
    if not address_entity:
        if is_contract(address):
            try:
                nickname = f"Contract: {Contract(address)._build['contractName']}"
            except ContractNotVerified as e:
                nickname = f"Non-Verified Contract: {address}"
            address_entity = Address(
                address=address,
                chain=chain,
                is_contract=True,
                nickname=nickname,
            )
        else:
            address_entity = Address(
                address=address,
                chain=chain,
                is_contract=False,
            )
    return address_entity

@db_session
def cache_token(address: str) -> Token:
    address_entity = cache_address(address)
    token = Token.get(address=address_entity)
    if not token:
        address = convert.to_address(address)
        if address == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
            symbol, name = {
                Network.Mainnet: ("ETH","Ethereum"),
                Network.Fantom: ("FTM","Fantom"),
                Network.Arbitrum: ("ETH", "Ethereum"),
                Network.Optimism: ("ETH", "Ethereum"),
            }[chain.id]
            decimals = 18
        else:
            token = Contract(address)
            symbol, name, decimals = fetch_multicall([token,'symbol'],[token,'name'],[token,'decimals'])

            # MKR contract returns name and symbol as bytes32 which is converted to a brownie HexString
            # try to decode it
            if isinstance(name, HexString):
                name = hex_to_string(name)
            if isinstance(symbol, HexString):
                symbol = hex_to_string(symbol)
        
        if address_entity.nickname is None or address_entity.nickname.startswith("Contract: "):
            # Don't overwrite any intentionally set nicknames, if applicable
            address_entity.nickname = f"Token: {name}"
        
        try:
            token = Token(
                address=address_entity,
                symbol=symbol,
                name=name,
                decimals= 0 if address == UNI_V3_POS or decimals is None else decimals,
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
    if parent and parent != _txgroup.parent_txgroup:
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
def fetch_balances(vault_address: str, block=None) -> Dict[str, Decimal]:
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
    return {wallet: balance for wallet, balance in balances if wallet != ZERO_ADDRESS}
