from yearn.entities import TreasuryTx


def is_compound_deposit(tx: TreasuryTx) -> bool:
    if "Mint" in tx._events:
        for event in tx._events["Mint"]:
            if all(arg in event for arg in {'minter', 'mintTokens', 'mintAmount'}):
                minter = event['minter']
                minted = tx.token.scale_value(event['mintTokens'])
                # cToken side
                if tx.token == tx.from_address == event.address and tx.to_address == minter and minted == tx.amount:
                    return True
                # underlying side
                elif tx.to_address == event.address and tx.from_address == minter and minted == tx.amount:
                    return True
    return False

def is_compound_withdrawal(tx: TreasuryTx) -> bool:
    if "Redeem" in tx._events:
        for event in tx._events['Redeem']:
            if all(arg in event for arg in {'redeemer', 'redeemTokens', 'redeemAmount'}):
                redeemer = event['redeemer']
                redeemed = tx.token.scale_value(event['redeemTokens'])
                # cToken side
                if event.address == tx.token and tx.from_address == redeemer and redeemed == tx.amount:
                    return True
                # underlying side
                elif tx.to_address == redeemer and tx.from_address == event.address and redeemed == tx.amount:
                    return True
    return False
