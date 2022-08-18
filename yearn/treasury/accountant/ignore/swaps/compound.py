
from yearn.entities import TreasuryTx


def is_compound_deposit(tx: TreasuryTx) -> bool:
    if "Mint" in tx._events:
        for event in tx._events["Mint"]:
            if all(arg in event for arg in {'minter', 'mintTokens', 'mintAmount'}):
                # cToken side
                if event.address == tx.token.address.address == tx.from_address.address and tx.to_address and tx.to_address.address == event['minter'] and round(event['mintTokens']/tx.token.scale, 15) == round(float(tx.amount), 15):
                    return True
                # underlying side
                elif tx.to_address and tx.to_address.address == event.address and tx.from_address.address == event['minter'] and round(event['mintAmount']/tx.token.scale, 15) == round(float(tx.amount), 15):
                    return True

def is_compound_withdrawal(tx: TreasuryTx) -> bool:
    if "Redeem" in tx._events:
        for event in tx._events['Redeem']:
            if all(arg in event for arg in {'redeemer', 'redeemTokens', 'redeemAmount'}):
                # cToken side
                if event.address == tx.token.address.address and tx.from_address.address == event['redeemer'] and round(event['redeemTokens']/tx.token.scale, 15) == round(float(tx.amount), 15):
                    return True
                # underlying side
                elif tx.to_address and tx.to_address.address == event['redeemer'] and tx.from_address.address == event.address and round(event['redeemAmount']/tx.token.scale, 15) == round(float(tx.amount), 15):
                    return True
