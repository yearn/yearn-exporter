from bisect import bisect_right
from dataclasses import dataclass

from brownie import chain, web3
from joblib.parallel import Parallel, delayed
from toolz import unique
from tqdm import tqdm
from web3._utils.abi import filter_by_name
from web3._utils.events import construct_event_topic_set

from yearn.events import create_filter, decode_logs, get_logs_asap, logs_to_balance_checkpoints
from yearn.prices import magic
from yearn.utils import contract_creation_block
from yearn.v2.vaults import Vault
import pandas as pd

OPEX = 0.35
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


@dataclass
class Affiliate:
    name: str
    vault: str
    wrapper: str
    treasury: str = None


affiliates = [
    Affiliate(
        name='inverse-dai-wbtc',
        vault='0x19D3364A399d251E894aC732651be8B0E4e85001',
        wrapper='0xB0B02c75Fc1D07d351C991EBf8B5F5b48F24F40B',
        treasury=None,
    ),
    Affiliate(
        name='inverse-dai-weth',
        vault='0x19D3364A399d251E894aC732651be8B0E4e85001',
        wrapper='0x57faa0dec960ed774674a45d61ecfe738eb32052',
        treasury=None,
    ),
    Affiliate(
        name='inverse-usdc-weth',
        vault='0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9',
        wrapper='0x698c1d40574cd90f1920f61D347acCE60D3910af',
        treasury=None,
    ),
    Affiliate(
        name='frax-usdc',
        vault='0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9',
        wrapper='0xEE5825d5185a1D512706f9068E69146A54B6e076',
        treasury=None,
    ),
    Affiliate(
        name='alchemix-dai',
        vault='0x19D3364A399d251E894aC732651be8B0E4e85001',
        wrapper='0x014dE182c147f8663589d77eAdB109Bf86958f13',
        treasury=None,
    ),
]


def get_checkpoints(vault: Vault):
    from_block = contract_creation_block(str(vault))
    to_block = chain.height
    logs = get_logs_asap(str(vault), [vault.topics['Transfer']], from_block, to_block)
    checkpoints = logs_to_balance_checkpoints(logs)
    return checkpoints


def process_affilliate(affiliate: Affiliate):
    v = Vault.from_address(affiliate.vault)
    from_block = contract_creation_block(affiliate.vault)
    to_block = chain.height

    print('1. fetch rewards addresses')
    logs = get_logs_asap(affiliate.vault, [v.vault.topics['UpdateRewards']], from_block, to_block)
    rewards = list(unique(log['rewards'] for log in decode_logs(logs)))

    print('2. fetch all payouts')
    abi = filter_by_name('Transfer', v.vault.abi)[0]
    topics = construct_event_topic_set(abi, web3.codec, {'sender': affiliate.vault, 'receiver': rewards})
    logs = get_logs_asap(affiliate.vault, topics, from_block, to_block)
    fees = decode_logs(logs)
    blocks = [int(log.block_number) for log in fees]
    fees = [log['value'] / v.scale for log in fees]

    print('3. fetch affiliate balances')

    def get_balance(block):
        return v.vault.balanceOf(affiliate.wrapper, block_identifier=block) / v.scale

    balances = Parallel(10, 'threading')(delayed(get_balance)(block) for block in blocks)
    print(sum(fees), 'fees')
    print(len(logs), 'logs')
    print(max(balances), 'max bal')

    print('4. get total supplies')

    def total_supply(block):
        return v.vault.totalSupply(block_identifier=block) / v.scale

    supplies = Parallel(10, 'threading')(delayed(total_supply)(block) for block in blocks)
    print(max(supplies), 'max supply')

    print('5. fetching prices')
    prices = Parallel(10, 'threading')(delayed(magic.get_price)(affiliate.vault, block=block) for block in blocks)

    print('6. calculating tiers')
    tiers = [get_tier(balance * price) for balance, price in zip(balances, prices)]

    print('7. calculating payouts')
    shares = [balance / supply for balance, supply in zip(balances, supplies)]
    print(max(shares), 'max share')
    payouts = [fee * share * tier * (1 - OPEX) for fee, share, tier in zip(fees, shares, tiers)]
    print(sum(payouts), 'to pay')

    df = pd.DataFrame({
        'block': blocks,
        'fee': fees,
        'balance': balances,
        'supply': supplies,
        'price': prices,
        'tier': tiers,
        'share': shares,
        'payout': payouts,
    }).set_index('block')
    df.to_csv(f'research/affiliates/{affiliate.name}.csv')
    return df
