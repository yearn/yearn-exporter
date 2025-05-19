from yearn.entities import TreasuryTx


def is_compound_deposit(tx: TreasuryTx) -> bool:
    if "Mint" in tx._events:
        for event in tx._events["Mint"]:
            if all(arg in event for arg in {'minter', 'mintTokens', 'mintAmount'}):
                # cToken side
                if tx.token == tx.from_address == event.address and tx.to_address == event['minter'] and Decimal(event['mintTokens']) / tx.token.scale == tx.amount:
                    return True
                # underlying side
                elif tx.to_address == event.address and tx.from_address == event['minter'] and Decimal(event['mintAmount']) / tx.token.scale == tx.amount:
                    return True
    return False

def is_compound_withdrawal(tx: TreasuryTx) -> bool:
    if "Redeem" in tx._events:
        for event in tx._events['Redeem']:
            if all(arg in event for arg in {'redeemer', 'redeemTokens', 'redeemAmount'}):
                # cToken side
                if event.address == tx.token and tx.from_address == event['redeemer'] and Decimal(event['redeemTokens']) / tx.token.scale == tx.amount:
                    return True
                # underlying side
                elif tx.to_address == event['redeemer'] and tx.from_address == event.address and Decimal(event['redeemAmount']) / tx.token.scale == tx.amount:
                    return True
    return False
