from collections import defaultdict
from math import ceil

from a_sync import AsyncThreadPoolExecutor
from async_lru import alru_cache
from eth_utils.toolz import last
from joblib import Parallel, delayed
from y import Contract, Network
from y.constants import CHAINID

from yearn.events import decode_logs, get_logs_asap

YEARN_PARTNER_TRACKER = Contract({
    Network.Mainnet: "0x8ee392a4787397126C163Cb9844d7c447da419D8",
    Network.Fantom: "0x086865B2983320b36C42E48086DaDc786c9Ac73B",
    Network.Arbitrum: "0x0e5b46E4b2a05fd53F5a4cD974eb98a9a613bcb7",
    Network.Optimism: "0x7E08735690028cdF3D81e7165493F1C34065AbA2",
    Network.Base: "0xD0F08E42A40569fF83D28AA783a5b6537462667c",
}[CHAINID])

class AsOfDict(dict):
    """
    Allows you to get the closest previous item.
    
    >>> AsOfDict({1: 'a', 2: 'b'})[2]
    'a'
    """

    def __init__(self):
        self[0] = 0

    def __getitem__(self, key):
        return super().__getitem__(last(item for item in sorted(self) if item <= key))

def delegated_deposit_totals():
    delegated_deposits = defaultdict(lambda: defaultdict(lambda: defaultdict(AsOfDict)))
    for deposit in decode_logs(get_logs_asap(str(YEARN_PARTNER_TRACKER), [YEARN_PARTNER_TRACKER.topics['ReferredBalanceIncreased']])):
        partnerId, vault, depositor, amount_added, total_deposited = deposit.values()
        partner_deposits = _unwrap(delegated_deposits, vault, depositor, partnerId)

        pre_value = partner_deposits[deposit.block_number]
        partner_deposits[deposit.block_number] = pre_value + amount_added
    return delegated_deposits

def proportional_withdrawal_totals(delegated_deposits):
    proportional_withdrawals = defaultdict(lambda: defaultdict(lambda: defaultdict(AsOfDict)))
    all_logs = Parallel(16, "threading")(delayed(get_logs_asap)(vault, [Contract(vault).topics['Transfer']]) for vault in delegated_deposits)
    for vault, logs in zip(delegated_deposits, all_logs):
        for transfer in decode_logs(logs):
            sender, receiver, amount = transfer.values()
            vault_deposits = delegated_deposits[vault]
            if sender not in vault_deposits:
                continue
            
            sender_deposits = vault_deposits[sender]

            # If the withdrawal took place prior to the user's first delegated partner deposit, skip.
            if transfer.block_number < min(
                block
                for partner in sender_deposits
                for block in sender_deposits[partner]
                if block > 0
            ):
                continue

            partner_balances = {
                partner: sender_deposits[partner][transfer.block_number]
                for partner in sender_deposits
            }

            total = sum(partner_balances.values())
            for partner, balance in partner_balances.items():
                partner_withdrawals = _unwrap(proportional_withdrawals, vault, sender, partner)
                partner_withdrawals[transfer.block_number] += ceil(amount * balance / total)
    return proportional_withdrawals

def _delegated_deposit_balances():
    """
    Returns a dict used to lookup the delegated balance of each `partner` for each `depositor` to each `vault` at `block`.
        {vault: {depositor: {partner: AsOfDict({block: amount})}}}
    """
    deposits = delegated_deposit_totals()
    withdrawals = proportional_withdrawal_totals(deposits)

    balances = defaultdict(lambda: defaultdict(lambda: defaultdict(AsOfDict)))
    for vault, vdeets in deposits.items():
        for depositor, ddeets in vdeets.items():
            for partner, pdeets in ddeets.items():

                partner_balances = _unwrap(balances, vault, depositor, partner)
                partner_withdrawals = _unwrap(withdrawals, vault, depositor, partner)

                blocks = list(pdeets.keys()) + list(partner_withdrawals.keys())
                for block in blocks:
                    partner_deposits = _unwrap(deposits, vault, depositor, partner)
                    balance = partner_deposits[block]
                    if len(partner_withdrawals) > 0:
                        balance = max(balance - partner_withdrawals[block], 0)
                    partner_balances[block] = balance
    return balances

thread = AsyncThreadPoolExecutor(1)

@alru_cache
async def delegated_deposit_balances():
    return await thread.run(_delegated_deposit_balances)

def _unwrap(root_dict, vault, depositor, partner):
    vault_based = root_dict[vault]
    depositor_based = vault_based[depositor]
    partner_based = depositor_based[partner]
    return partner_based
