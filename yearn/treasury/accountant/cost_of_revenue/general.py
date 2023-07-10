
import logging

from brownie import chain, convert
from y.networks import Network

from yearn import constants
from yearn.entities import TreasuryTx
from yearn.partners.partners import partners
from yearn.treasury.accountant.classes import Filter, HashMatcher, IterFilter

logger = logging.getLogger(__name__)

hashes = {
    Network.Mainnet: {
        'thegraph': [
            '0x33a50699c95fa37e2cc4032719ed6064bbd892b0992dde01d4ef9b3470b9da0b',
        ],
        'yswap': [
            ['0xc66a60d1578ad80f9f1bfb29293bd9f8699c3d61b237a7cf8c443d00ffb3809e', Filter('from_address.nickname',"Disperse.app")],
            ['0xd45f5cf3388cea2a684ae124bac7bccb010442862cc491fdb4fc06d57c6aab5d', Filter('log_index',None)],
        ],
        'ychad': [
            ['0x1ba68f5f52b27e9b6676b952c08d29e2fe29f8ddffd7427911046915db5b4966', Filter('from_address.nickname',"Disperse.app")],
        ],
        'ymechs': [
            '0x1ab9ff3228cf25bf2a7c1eac596e836069f8c0adc46acd46d948eb77743fbb96',
            '0xe2a6bec23d0c73b35e969bc949072f8c1768767b06d57e5602b2b95eddf41a66',
            ["0xeed864c87f01996ead5a8315cccd0b3f22f384ef3b4e272e4751065f909b4d3d", Filter('to_address.address', "0x966Fa7ACF1b6c732458e4d3264FD2393aec840bA")]
        ],
        'ykeeper': [
            '0x1ab9ff3228cf25bf2a7c1eac596e836069f8c0adc46acd46d948eb77743fbb96',
            '0xe2a6bec23d0c73b35e969bc949072f8c1768767b06d57e5602b2b95eddf41a66',
            '0x140246e693445b448f8e9baaad1872fe44f3982cba44e7d652bf1c2235c7ac4a',
        ],
    }
}.get(chain.id, {})

def is_partner_fees(tx: TreasuryTx) -> bool:
    if tx.from_address.address == constants.YCHAD_MULTISIG and tx.to_address:
        for partner in partners:
            if not (
                tx.to_address.address == convert.to_address(partner.treasury) or
                (hasattr(partner, 'retired_treasuries') and tx.to_address.address in partner.retired_treasuries)
            ):
                continue
            if any(tx.token.address.address == convert.to_address(wrapper.vault) for wrapper in partner.flat_wrappers):
                return True
            else:
                logger.warn(f'look at {tx}, seems odd')
    
    # DEV figure out why these weren't captured by the above
    hashes = {
        Network.Mainnet: [
            # Thought we automated these... why aren't they sorting successfully? 
            ["0x590b0cc67ba42dbc046b8cbfe2d314fbe8da82f11649ef21cdacc61bc9752d83", IterFilter('log_index',[275,276,278])],
            ["0xd1b925ad7fdd9abdd31460a346d081d6afe9f6cb1c1b0cd5f6129885edf318da", IterFilter('log_index',[174,177])],
            ["0xe11b4e3ece520c1818ffe821c038779f87c293aa32c26115265b6b8fb23c30bd", Filter('log_index', 154)],
            ["0xdc4e0045901cfd5ef4c6327b846a8bd229abdbf289547cd0e969874b47124342", Filter('log_index', 116)],
            ["0x9681276a8668f5870551908fc17be3553c82cf6a9fedbd2fdb43f1c05385dca1", Filter('log_index', 173)],
            ["0xa12c99e2f4e5ffec9d280528968d615ab3d58483b37e8b021865163655892ea0", IterFilter('log_index', [223, 228])]
        ],
    }.get(chain.id, [])

    if tx in HashMatcher(hashes):
        return True
    return False
