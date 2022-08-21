from collections import defaultdict
from math import ceil

from brownie import chain
from toolz import last
from yearn.events import decode_logs, get_logs_asap
from yearn.networks import Network
from yearn.utils import contract

YEARN_PARTNER_TRACKER = contract({
    Network.Mainnet:"0x8ee392a4787397126C163Cb9844d7c447da419D8",
    Network.Fantom:"0x086865B2983320b36C42E48086DaDc786c9Ac73B",
}[chain.id])

class AsOfDict(dict):
    """
    Allows you to get the closest previous item.
    
    >>> AsOfDict({1: 'a', 2: 'b'})[2]
    'a'
    """

    def __getitem__(self, key):
        return super().__getitem__(last(item for item in sorted(self) if item <= key))

def delegated_deposit_totals():
    delegated_deposits = defaultdict(lambda: defaultdict(lambda: defaultdict(AsOfDict)))
    for deposit in decode_logs(get_logs_asap(str(YEARN_PARTNER_TRACKER), [YEARN_PARTNER_TRACKER.topics['ReferredBalanceIncreased']])):
        partnerId, vault, depositor, amount_added, total_deposited = deposit.values()

        # Make sure AsOfDict has a start point.
        if len(delegated_deposits[vault][depositor][partnerId]) == 0:
            delegated_deposits[vault][depositor][partnerId][0] = 0

        pre_value = delegated_deposits[vault][depositor][partnerId][deposit.block_number]
        delegated_deposits[vault][depositor][partnerId][deposit.block_number] = pre_value + amount_added
    return delegated_deposits

def proportional_withdrawal_totals(delegated_deposits):
    proportional_withdrawals = defaultdict(lambda: defaultdict(lambda: defaultdict(AsOfDict)))
    for vault in list(delegated_deposits.keys()):
        vault = contract(vault)
        for transfer in decode_logs(get_logs_asap(str(vault), [vault.topics['Transfer']])):
            sender, receiver, amount = transfer.values()
            if sender not in delegated_deposits[vault.address]:
                continue

            if transfer.block_number <= min(
                block
                for partner in delegated_deposits[vault.address][sender]
                for block in delegated_deposits[vault.address][sender][partner]
                if block > 0
            ):
                continue

            partner_balances = {
                partner: delegated_deposits[vault.address][sender][partner][transfer.block_number]
                for partner in delegated_deposits[vault.address][sender]
            }

            total = sum(partner_balances.values())
            for partner, balance in partner_balances.items():
                # Make sure AsOfDict has a start point.
                if len(proportional_withdrawals[vault.address][sender][partner]) == 0:
                    proportional_withdrawals[vault.address][sender][partner][0] = 0
                proportional_withdrawals[vault.address][sender][partner][transfer.block_number] += ceil(amount * balance / total)
    return proportional_withdrawals
    
def delegated_deposit_balances():
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
                if len(balances[vault][depositor][partner]) == 0:
                    balances[vault][depositor][partner][0] = 0
                blocks = list(pdeets.keys()) + list(withdrawals[vault][depositor][partner].keys())
                for block in blocks:
                    balance = deposits[vault][depositor][partner][block]
                    if len(withdrawals[vault][depositor][partner]) > 0:
                        balance = max(balance - withdrawals[vault][depositor][partner][block], 0)
                    balances[vault][depositor][partner][block] = balance
    return balances

DELEGATED_BALANCES = delegated_deposit_balances()
