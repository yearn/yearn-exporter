from collections import Counter
from pathlib import Path

import toml
from brownie import ZERO_ADDRESS, chain, web3
from tabulate import tabulate
from web3._utils.events import construct_event_topic_set
from yearn.events import decode_logs, get_logs_asap

abi = {
    "anonymous": False,
    "inputs": [
        {"indexed": True, "internalType": "address", "name": "from", "type": "address"},
        {"indexed": True, "internalType": "address", "name": "to", "type": "address"},
        {"indexed": False, "internalType": "uint256", "name": "value", "type": "uint256"},
    ],
    "name": "Transfer",
    "type": "event",
}

base = Path('research/double-fees')
base.mkdir(parents=True, exist_ok=True)


def find_double_fees(withdrawals, fees, blacklist=None):
    assert len(withdrawals) and len(fees), "no events loaded"
    print(f"processing {len(withdrawals)=} and {len(fees)=}")
    overlap = {log["transactionHash"] for log in withdrawals} & {log["transactionHash"] for log in fees}
    print(f"{len(overlap)=}")
    withdrawals = decode_logs([log for log in withdrawals if log["transactionHash"] in overlap])
    fees = decode_logs([log for log in fees if log["transactionHash"] in overlap])
    tx_to_refund = {event.transaction_hash: tuple(event.values())[2] for event in fees}
    refunds = Counter()
    for item in withdrawals:
        tx = item.transaction_hash
        is_contract = bool(web3.eth.get_code(tuple(item.values())[0]))
        user = chain.get_transaction(tx).sender if is_contract else tuple(item.values())[0]
        if blacklist and user in blacklist:
            continue
        refunds[user] += tx_to_refund[item.transaction_hash]

    return dict(refunds.most_common())


def find_transfers(address, from_address, to_address, start_block, end_block):
    topics = construct_event_topic_set(abi, web3.codec, {"from": from_address, "to": to_address})
    return get_logs_asap(address, topics, start_block, end_block)


def reimburse_weth_in_dai():
    start_block = 11694792
    end_block = 12026337
    path = base / f"weth-double-fees-refund-in-dai-{start_block}-{end_block}.toml"
    dai = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
    strategy_dai = "0x2F90c531857a2086669520e772E9d433BbfD5496"
    treasury_vault = "0x93A62dA5a14C80f265DAbC077fCEE437B1a0Efde"
    yweth = "0xe1237aA7f535b0CC33Fd973D66cBf830354D16c7"

    # yweth withdrawals
    withdrawals = find_transfers(yweth, None, ZERO_ADDRESS, start_block, end_block)
    fees = find_transfers(dai, strategy_dai, treasury_vault, start_block, end_block)
    refunds = find_double_fees(withdrawals, fees)

    toml.dump(refunds, open(path, "wt"))
    print(tabulate([[user, value / 1e18] for user, value in refunds.items()]))
    print(f"total {sum(refunds.values()) / 1e18} to {len(refunds)} users")


def reimburse_dai_usdc_usdt_in_3pool():
    start_block = 10753482
    end_block = 12087852
    path = base / f"dai-usdc-usdt-double-fees-refund-in-3crv-{start_block}-{end_block}.toml"
    strategy_3crv = "0xC59601F0CC49baa266891b7fc63d2D5FE097A79D"
    _3crv = "0x6c3F90f043a72FA612cbac8115EE7e52BDe6E490"
    treasury_vault = "0x93A62dA5a14C80f265DAbC077fCEE437B1a0Efde"
    yusdc = "0x597aD1e0c13Bfe8025993D9e79C69E1c0233522e"
    ydai = "0xACd43E627e64355f1861cEC6d3a6688B31a6F952"
    yusdt = "0x2f08119C6f07c006695E079AAFc638b8789FAf18"
    blacklist = {
        "0x14EC0cD2aCee4Ce37260b925F74648127a889a28": "ydai exploiter",
    }

    withdrawals = find_transfers([yusdc, ydai, yusdt], None, ZERO_ADDRESS, start_block, end_block)
    fees = find_transfers(_3crv, strategy_3crv, treasury_vault, start_block, end_block)
    refunds = find_double_fees(withdrawals, fees, blacklist)

    toml.dump(refunds, open(path, "wt"))
    print(tabulate([[user, value / 1e18] for user, value in refunds.items()]))
    print(f"total {sum(refunds.values()) / 1e18} to {len(refunds)} users")


def reimburse_tusd_in_yusd():
    start_block = 10753482
    end_block = 12087852
    path = base / f"tusd-double-fees-refund-in-yusd-{start_block}-{end_block}.toml"
    strategies = [
        "0x1d91E3F77271ed069618b4BA06d19821BC2ed8b0",
        "0xe3a711987612BFD1DAFa076506f3793c78D81558",
        "0x4BA03330338172fEbEb0050Be6940c6e7f9c91b0",
    ]
    yusd = "0x5dbcF33D8c2E976c6b560249878e6F1491Bca25c"
    treasury_vault = "0x93A62dA5a14C80f265DAbC077fCEE437B1a0Efde"
    ytusd = "0x37d19d1c4E1fa9DC47bD1eA12f742a0887eDa74a"

    withdrawals = find_transfers(ytusd, None, ZERO_ADDRESS, start_block, end_block)
    fees = find_transfers(yusd, strategies, treasury_vault, start_block, end_block)
    refunds = find_double_fees(withdrawals, fees)

    toml.dump(refunds, open(path, "wt"))
    print(tabulate([[user, value / 1e18] for user, value in refunds.items()]))
    print(f"total {sum(refunds.values()) / 1e18} to {len(refunds)} users")


def main():
    reimburse_weth_in_dai()
    reimburse_dai_usdc_usdt_in_3pool()
    reimburse_tusd_in_yusd()
