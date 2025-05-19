
from decimal import Decimal

from y import Network
from y.constants import CHAINID, WRAPPED_GAS_COIN

from yearn.constants import YCHAD_MULTISIG
from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import Filter, HashMatcher, IterFilter

otc_hashes = {
    Network.Mainnet: [
        ["0x57fd81a0a665324558ae91a927097e44febd89972136165f3ec6cd4d6f8bc749", Filter('log_index', 158)],

        "0x3133abba52be3bab709876479c45d8e3dbd518efa844f5ea0e4f7c4ef62b46e1",
        "0x4f28e5ecf84b84304cc6a211b17b2232113567c6ea1bfb38dd4ea9504eaaba8f",
        ["0xe635d5df793030cd185e78c0dc275311002ceeb9a7d315ad0ed0c7d0d8c375db", IterFilter('log_index', [248,249])]
    ]
}.get(CHAINID, [])

non_otc_hashes = {
    Network.Mainnet: [
        "0x941b047380e5021b52335695fb6891302bc732bca178a21db32e9a80f688c3be",
        "0x02d39311a2d5fa9b9a4c06dbe1c87b95423bbfe19d179c59455bc68cbe077eed",
    ]
}.get(CHAINID, [])

VYPER_BUYERS = [
    "0xdf5e4E54d212F7a01cf94B3986f40933fcfF589F",
    "0x6903223578806940bd3ff0C51f87aa43968424c8",
]

def is_buyer_top_up(tx: TreasuryTx) -> bool:
    return CHAINID == Network.Mainnet and tx._symbol == "DAI" and tx.to_address in VYPER_BUYERS

_BUYER_HASHES = HashMatcher([
    "0xced6de44e15b827b39cc365de3b319a30d0d23dd8d10e2d9860948d4038e178c",
    "0xa8832faf0146d7ccaac7558b86042aa79cb6fdebd6d8988ec6f5c7533066ded9",
    "0x25364b36e6dbb74db53d5aef7dfdad3c879da19743456260e8a89a3e8ad3d9ae",
    "0xdbcee8ca9beba7ec800b0b2f289358bf42fd0c1e2ea5d7650de74a5127813247",
    "0x5b950f3a341e38fe22a82d5040a9a3161b3c8d09b70f06ed1671495b02b01d6e",
    "0x4c797977155093a80265a167256575578cef4b34f54e4003c88d0e28c69df215",
])
"""These dont match due to decimal <> float discrepancy. Later we will use decimals only. For now this works.
NOTE it also seems like buybacks made via a gnosis safe may have issues too. Potential to automate these in the future.
NOTE: i think we can delete this extra elif now that the changes on line 43 have been made. test."""


def is_buying_with_buyer(tx: TreasuryTx) -> bool:
    if CHAINID == Network.Mainnet and tx._symbol == "YFI" and tx.to_address == YCHAD_MULTISIG and "Buyback" in tx._events:
        buyback_event = tx._events["Buyback"]
        if all(arg in buyback_event for arg in ("buyer", "yfi", "dai")):
            buyback_amount = Decimal(buyback_event["yfi"]) / 10**18
            if tx.amount == buyback_amount or tx in _BUYER_HASHES:
                return True
            raise ValueError(f'from node: {buyback_amount} from db: {tx.amount} diff: {buyback_amount - tx.amount}')
    return False

YFI_BUYBACK_AUCTIONS = "0x4349ed200029e6Cf38F1455B9dA88981F1806df3"

def is_buying_with_auction(tx: TreasuryTx) -> bool:
    if tx._symbol != 'YFI' or tx.to_address != YCHAD_MULTISIG or "AuctionTaken" not in tx._events:
        return False
    auctions_taken = tx._events['AuctionTaken']
    if len(auctions_taken) > 1:
        raise NotImplementedError
    event = auctions_taken[0]
    if event.address != YFI_BUYBACK_AUCTIONS:
        raise ValueError(event.address, event)
    # did the auction contract send weth to tx.sender?
    for transfer in tx._events['Transfer']:
        if transfer.address == WRAPPED_GAS_COIN:
            sender, receiver, amount = transfer.values()
            if sender == YFI_BUYBACK_AUCTIONS and tx.from_address == receiver and amount == event['taken']:
                return True
            print(f"AuctionTaken: {event}")
            print(f"Transfer: {transfer}")
    return False
