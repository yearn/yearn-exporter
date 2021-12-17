from brownie import Contract, chain, ZERO_ADDRESS
from pony.orm import ObjectNotFound, db_session, TransactionIntegrityError, select
from yearn.cache import memory
import logging
from yearn.entities import Address, Token, UserTx, db
from yearn.multicall2 import fetch_multicall
from yearn.utils import is_contract

@db_session
@memory.cache()
def cache_address(address: str) -> Address:
    try:
        return Address[chain.id,address]
    except ObjectNotFound:
        try:
            return Address(chainid=chain.id,address=address,is_contract=is_contract(address))
        except TransactionIntegrityError: # This can happen if two threads try to insert at same time
            return Address[chain.id,address]

@db_session
@memory.cache()
def cache_token(address: str) -> Token:
    address_entity = cache_address(address)
    try:
        return Token[chain.id,address]
    except ObjectNotFound:
        contract = Contract(address)
        symbol, name, decimals = fetch_multicall([contract,'symbol'],[contract,'name'],[contract,'decimals'])
        entity = Token(token=address_entity,symbol=symbol,name=name,decimals=decimals)
        print(f'token {symbol} added to postgres')
        return entity

@db_session
def last_recorded_block(Entity: db.Entity) -> int:
    '''
    Returns last block recorded for sql entity type `Entity`
    '''
    TreasuryTx = 1 # NOTE: Get rid of this when treasury txs are implemented
    if type(Entity) == UserTx:
        return select(max(e.block) for e in Entity if e.vault.chainid == chain.id)
    elif type(Entity) == TreasuryTx:
        return select(max(e.block) for e in Entity if e.token.chainid == chain.id)
    return select(max(e.block) for e in Entity if e.chainid == chain.id)

@db_session
def fetch_balances(vault_address: str, block=None):
    if block and block > last_recorded_block(UserTx):
        # NOTE: we use `postgres.` instead of `self.` so we can make use of parallelism
        raise Exception('this block has not yet been cached into postgres')
    if block:
        balances = db.select(f"""
            a.wallet, coalesce(amount_in,0) - coalesce(amount_out,0) balance
            from (
                select "to" wallet, sum(amount) amount_in
                from user_txs where chainid = $(chain.id) and vault = $vault_address and block <= $block
                group by "to" ) a
            left join (
                select "from" wallet, sum(amount) amount_out
                from user_txs where chainid = $(chain.id) and vault = $vault_address and block <= $block
                group by "from") b on a.wallet = b.wallet
                """)
    else:
        balances = db.select(f"""
            a.wallet, coalesce(amount_in,0) - coalesce(amount_out,0) balance
            from (
                select "to" wallet, sum(amount) amount_in
                from user_txs where chainid = $(chain.id) and vault = $vault_address
                group by "to" ) a
            left join (
                select "from" wallet, sum(amount) amount_out
                from user_txs where chainid = $(chain.id) and vault = $vault_address
                group by "from") b on a.wallet = b.wallet
                """)
    return {wallet: balance for wallet,balance in balances if wallet != ZERO_ADDRESS}