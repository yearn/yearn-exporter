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

        vault_deposits = delegated_deposits[vault]
        depositor_deposits = vault_deposits[depositor]
        partner_deposits = depositor_deposits[partnerId]

        # Make sure AsOfDict has a start point.
        if len(partner_deposits) == 0:
            partner_deposits[0] = 0

        pre_value = partner_deposits[deposit.block_number]
        partner_deposits[deposit.block_number] = pre_value + amount_added
    return delegated_deposits

def proportional_withdrawal_totals(delegated_deposits):
    proportional_withdrawals = defaultdict(lambda: defaultdict(lambda: defaultdict(AsOfDict)))
    for vault in list(delegated_deposits.keys()):
        vault = contract(vault)
        for transfer in decode_logs(get_logs_asap(str(vault), [vault.topics['Transfer']])):
            sender, receiver, amount = transfer.values()
            vault_deposits = delegated_deposits[vault.address]
            if sender not in vault_deposits:
                continue
            
            sender_deposits = vault_deposits[sender]

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
                vault_withdrawals = proportional_withdrawals[vault.address]
                sender_withdrawals = vault_withdrawals[sender]
                partner_withdrawals = sender_withdrawals[partner]
                # Make sure AsOfDict has a start point.
                if len(partner_withdrawals) == 0:
                    partner_withdrawals[0] = 0
                partner_withdrawals[transfer.block_number] += ceil(amount * balance / total)
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
                vault_balances = balances[vault]
                depositor_balances = vault_balances[depositor]
                partner_balances = depositor_balances[partner]
                if len(partner_balances) == 0:
                    partner_balances[0] = 0
                vault_withdrawals = withdrawals[vault]
                depositor_withdrawals = vault_withdrawals[depositor]
                partner_withdrawals = depositor_withdrawals[partner]
                blocks = list(pdeets.keys()) + list(partner_withdrawals.keys())
                for block in blocks:
                    vault_deposits = deposits[vault]
                    depositor_deposits = vault_deposits[depositor]
                    partner_deposits = depositor_deposits[partner]
                    balance = partner_deposits[block]
                    if len(partner_withdrawals) > 0:
                        balance = max(balance - partner_withdrawals[block], 0)
                    partner_balances[block] = balance
    return balances

DELEGATED_BALANCES = delegated_deposit_balances()
