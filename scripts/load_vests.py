
# TODO: Fit this better into the rest of the exporter so it runs in tandem with treasury txs exporter

# TODO: Currently all vests are "Other Grants", we will want to sort them by budget reuest

from pony.orm import db_session
from y.utils.events import decode_logs, get_logs_asap

from yearn.entities import VestingEscrow, TxGroup

vesting_escrow_factory = '0xB93427b83573C8F27a08A909045c3e809610411a'
ychad = '0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52'

@db_session
def main():
    factory_events = decode_logs(get_logs_asap(vesting_escrow_factory, None))
    for escrow in [VestingEscrow.get_or_create_entity(event) for event in factory_events['VestingEscrowCreated'] if event['funder'] == ychad]:
        escrow.amortize_vested_funds()
        escrow.txgroup = TxGroup.get(name="Other Grants")

