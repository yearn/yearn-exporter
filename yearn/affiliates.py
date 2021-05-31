from bisect import bisect_right
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List
from yearn.utils import get_block_timestamp

import matplotlib.pyplot as plt
import pandas as pd
from brownie import web3
from joblib.parallel import Parallel, delayed
from web3._utils.abi import filter_by_name
from web3._utils.events import construct_event_topic_set

from yearn.events import decode_logs, get_logs_asap
from yearn.multicall2 import batch_call
from yearn.prices import magic
from yearn.v2.vaults import Vault

TIERS = {
    0: 0,
    1_000_000: 0.10,
    5_000_000: 0.15,
    10_000_000: 0.20,
    50_000_000: 0.25,
    100_000_000: 0.30,
    200_000_000: 0.35,
    400_000_000: 0.40,
    700_000_000: 0.45,
    1_000_000_000: 0.5,
}


def get_tier(amount):
    keys = sorted(TIERS)
    index = bisect_right(keys, amount) - 1
    return TIERS[keys[index]]


def get_timestamps(blocks):
    data = Parallel(50, 'threading')(delayed(get_block_timestamp)(block) for block in blocks)
    return pd.to_datetime([x * 1e9 for x in data])


@lru_cache()
def get_protocol_fees(address):
    """
    Get all protocol fee payouts for a given vault.

    Fees can be found as vault share transfers to the rewards address.
    """
    vault = Vault.from_address(address)
    rewards = vault.vault.rewards()

    topics = construct_event_topic_set(
        filter_by_name('Transfer', vault.vault.abi)[0],
        web3.codec,
        {'sender': address, 'receiver': rewards},
    )
    logs = decode_logs(get_logs_asap(address, topics))
    return {log.block_number: log['value'] / vault.scale for log in logs}


@dataclass
class Wrapper:
    name: str
    vault: str
    wrapper: str

    def protocol_fees(self):
        return get_protocol_fees(self.vault)

    def balances(self, blocks):
        vault = Vault.from_address(self.vault)
        balances = batch_call([[vault.vault, 'balanceOf', self.wrapper, block] for block in blocks])
        return [balance / vault.scale for balance in balances]

    def total_supplies(self, blocks):
        vault = Vault.from_address(self.vault)
        supplies = batch_call([[vault.vault, 'totalSupply', block] for block in blocks])
        return [supply / vault.scale for supply in supplies]

    def vault_prices(self, blocks):
        prices = Parallel(50, 'threading')(delayed(magic.get_price)(self.vault, block=block) for block in blocks)
        return prices


@dataclass
class Partner:
    name: str
    wrappers: List[Wrapper]
    treasury: str = None

    def process(self):
        # snapshot wrapper share at each harvest
        wrappers = []
        for wrapper in self.wrappers:
            protocol_fees = wrapper.protocol_fees()
            blocks, protocol_fees = zip(*protocol_fees.items())
            wrap = pd.DataFrame(
                {
                    'block': blocks,
                    'timestamp': get_timestamps(blocks),
                    'protocol_fee': protocol_fees,
                    'balance': wrapper.balances(blocks),
                    'total_supply': wrapper.total_supplies(blocks),
                    'vault_price': wrapper.vault_prices(blocks),
                }
            )
            wrap['balance_usd'] = wrap.balance * wrap.vault_price
            wrap['share'] = wrap.balance / wrap.total_supply
            wrap['payout_base'] = wrap.share * wrap.protocol_fee * 0.65
            wrap['wrapper'] = wrapper.wrapper
            wrap['vault'] = wrapper.vault
            wrap = wrap.set_index('block')
            wrappers.append(wrap)
            # save a csv for reporting
            path = Path(f'research/affiliates/{self.name}/{wrapper.name}.csv')
            path.parent.mkdir(parents=True, exist_ok=True)
            wrap.to_csv(path)

        # calculate partner fee tier from cummulative wrapper balances
        partner = pd.concat(wrappers)
        total_balances = pd.pivot_table(partner, 'balance_usd', 'block', 'vault', 'sum').ffill().sum(axis=1)
        tiers = total_balances.apply(get_tier).rename('tier')
        # plot
        total_balances.plot()
        tiers.plot(secondary_y=True)
        path = Path(f'research/affiliates/{self.name}/balance.png')
        plt.savefig(path, dpi=300)

        # calculate final payout by vault after tier adjustments
        partner = partner.join(tiers)
        partner['payout'] = partner.payout_base * partner.tier
        payouts = partner.groupby('vault').payout.sum()
        print(payouts)
        path = Path(f'research/affiliates/{self.name}/payouts.csv')
        payouts.to_csv(path)


affiliates = [
    Partner(
        name='alchemix',
        wrappers=[
            Wrapper(
                name='dai',
                vault='0x19D3364A399d251E894aC732651be8B0E4e85001',
                wrapper='0x014dE182c147f8663589d77eAdB109Bf86958f13',
            ),
            Wrapper(
                name='dai-2',
                vault='0x19D3364A399d251E894aC732651be8B0E4e85001',
                wrapper='0x491EAFC47D019B44e13Ef7cC649bbA51E15C61d7',
            ),
        ],
    ),
    Partner(
        name='inverse',
        wrappers=[
            Wrapper(
                name='dai-wbtc',
                vault='0x19D3364A399d251E894aC732651be8B0E4e85001',
                wrapper='0xB0B02c75Fc1D07d351C991EBf8B5F5b48F24F40B',
            ),
            Wrapper(
                name='dai-weth',
                vault='0x19D3364A399d251E894aC732651be8B0E4e85001',
                wrapper='0x57faa0dec960ed774674a45d61ecfe738eb32052',
            ),
            Wrapper(
                name='usdc-weth',
                vault='0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9',
                wrapper='0x698c1d40574cd90f1920f61D347acCE60D3910af',
            ),
        ],
    ),
    Partner(
        name='frax',
        wrappers=[
            Wrapper(
                name='usdc',
                vault='0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9',
                wrapper='0xEE5825d5185a1D512706f9068E69146A54B6e076',
            ),
        ],
    ),
    Partner(
        name='pickle',
        wrappers=[
            Wrapper(
                name='usdc',
                vault='0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9',
                wrapper='0xEecEE2637c7328300846622c802B2a29e65f3919',
            ),
            Wrapper(
                name='lusd',
                vault='0x5fA5B62c8AF877CB37031e0a3B2f34A78e3C56A6',
                wrapper='0x699cF8fE0C1A6948527cD4737454824c6E3828f1',
            ),
        ],
    ),
    Partner(
        name='badger',
        wrappers=[
            Wrapper(
                name='wbtc',
                vault='0xA696a63cc78DfFa1a63E9E50587C197387FF6C7E',
                wrapper='0x4b92d19c11435614CD49Af1b589001b7c08cD4D5',
            ),
        ],
    ),
]
