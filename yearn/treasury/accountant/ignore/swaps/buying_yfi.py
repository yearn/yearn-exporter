
from brownie import chain
from yearn.constants import YCHAD_MULTISIG
from yearn.entities import TreasuryTx
from yearn.networks import Network
from yearn.treasury.accountant.classes import Filter, HashMatcher, IterFilter

otc_hashes = {
    Network.Mainnet: [
        ["0x57fd81a0a665324558ae91a927097e44febd89972136165f3ec6cd4d6f8bc749", Filter('log_index', 158)],

        "0x3133abba52be3bab709876479c45d8e3dbd518efa844f5ea0e4f7c4ef62b46e1",
        "0x4f28e5ecf84b84304cc6a211b17b2232113567c6ea1bfb38dd4ea9504eaaba8f",
        ["0xe635d5df793030cd185e78c0dc275311002ceeb9a7d315ad0ed0c7d0d8c375db", IterFilter('log_index', [248,249])]
    ]
}.get(chain.id, [])

non_otc_hashes = {
    Network.Mainnet: [
        "0x941b047380e5021b52335695fb6891302bc732bca178a21db32e9a80f688c3be",
        "0x02d39311a2d5fa9b9a4c06dbe1c87b95423bbfe19d179c59455bc68cbe077eed",
    ]
}.get(chain.id, [])

VYPER_BUYERS = [
    "0xdf5e4E54d212F7a01cf94B3986f40933fcfF589F",
    "0x6903223578806940bd3ff0C51f87aa43968424c8",
]

def is_buyer_top_up(tx: TreasuryTx) -> bool:
    if chain.id == Network.Mainnet and tx._symbol == "DAI" and tx.to_address and (tx._to_nickname == "asdfg" or tx.to_address.address in VYPER_BUYERS):
        return True

def is_buying_with_buyer(tx: TreasuryTx) -> bool:
    if chain.id == Network.Mainnet and tx._symbol == "YFI" and tx.to_address and tx.to_address.address == YCHAD_MULTISIG:
        event_args = {"buyer", "yfi", "dai"}
        if "Buyback" in tx._events and all(arg in tx._events["Buyback"] for arg in event_args):
            amount_from_chain = round(tx._events["Buyback"]["yfi"] / 1e18, 15)
            amount_from_db = round(float(tx.amount), 15)
            if amount_from_chain == amount_from_db:
                return True
            else:
                # These dont match due to decimal <> float discrepancy. Later we will use decimals only. For now this works.
                if tx in HashMatcher([
                    "0xced6de44e15b827b39cc365de3b319a30d0d23dd8d10e2d9860948d4038e178c",
                    "0xa8832faf0146d7ccaac7558b86042aa79cb6fdebd6d8988ec6f5c7533066ded9",
                    "0x25364b36e6dbb74db53d5aef7dfdad3c879da19743456260e8a89a3e8ad3d9ae",
                ]):
                    return True
                raise ValueError(f'from node: {amount_from_chain} from db: {amount_from_db} diff: {amount_from_chain - amount_from_db}')
