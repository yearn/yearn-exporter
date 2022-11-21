
from yearn.entities import TreasuryTx
from pony.orm import select
from yearn.treasury.accountant.classes import HashMatcher
from yearn.treasury.accountant.constants import treasury
from yearn.treasury.accountant.ignore.swaps.skip_tokens import SKIP_TOKENS

YSWAPS = "0x9008D19f58AAbD9eD0D60971565AA8510560ab41"

def is_cowswap_swap(tx: TreasuryTx) -> bool:
    if "Trade" in tx._events:
        for trade in tx._events["Trade"]:
            if trade.address == YSWAPS and trade["owner"] in treasury.addresses and trade['buyToken'] not in SKIP_TOKENS:
                if tx.token.address.address == trade["buyToken"] and tx.to_address.address in treasury.addresses and round(float(tx.amount), 15) == round(trade['buyAmount'] / tx.token.scale, 15):
                    return True
                elif tx.token.address.address == trade["sellToken"] and tx.from_address.address == trade['owner'] and round(float(tx.amount), 15) == round(trade['sellAmount'] / tx.token.scale, 15):
                    # Did Yearn actually receive the other side of the trade?
                    other_side_query = select(
                        t for t in TreasuryTx
                        if t.hash == tx.hash
                        and t.token.address.address == trade['buyToken']
                        and t.from_address.address == YSWAPS
                        and t.to_address.address in treasury.addresses
                    )
                    if len(other_side_query) > 0:
                        return True
    # TODO figure out why hueristics above didn't catch these:
    return tx in HashMatcher([
        "0xc72f39e4f4a5f125edecbb6d1273b9f0f6f533ad039a5c7f71005f5811fb7480",
    ])
