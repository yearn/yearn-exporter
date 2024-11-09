
from brownie import chain, web3
from eth_portfolio._ydb.token_transfers import InboundTokenTransfers
from msgspec import json
from y.utils.events import Events, LogFilter

treasury = '0x93A62dA5a14C80f265DAbC077fCEE437B1a0Efde'
from_block = 19_000_000

itt = InboundTokenTransfers(treasury, from_block=from_block)

def main():
    events = []
    for event in LogFilter(topics=itt.topics, from_block=from_block).logs(chain.height):
        block = event.block_number if hasattr(event, 'block_number') else event.blockNumber
        if block == 20205291:
            print(event)
        print(block)
        events.append(event)
    print(len(events))

    from_filter = list(web3.eth.filter({'topics': itt.topics, 'fromBlock': from_block}).get_all_entries())
    print(len(from_filter))
    for event in from_filter:
        if event.blockNumber == 20205291:
            print(event)
            #print(event.blockNumber)

        
    print(f"Logs: {len(events)}")
    print(f"from_filter: {len(from_filter)}")

    print(itt.topics)
    print(json.encode(itt.topics))
