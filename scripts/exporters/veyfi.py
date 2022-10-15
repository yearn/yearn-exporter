import json
import logging
from datetime import datetime, timezone
from time import time

import sentry_sdk
from brownie import Contract, chain
from yearn.multicall2 import fetch_multicall
from yearn.networks import Network
from yearn.utils import contract, safe_views

sentry_sdk.set_tag('script','vaults_exporter')

logger = logging.getLogger('yearn.vaults_exporter')

def main():
    # 0xd281F1C9f8B7A673D0556d5b44edE0e54CD27074 == veyfi
    try:
        results = fetch_multicall(*[[contract('0xd281F1C9f8B7A673D0556d5b44edE0e54CD27074'), view] for view in _views()])
        info = dict(zip(_views, results))
        print(info)
    except ValueError as e:
        info = {"strategies": {}}
    # yearn = Yearn()
    # for block in chain.new_blocks(height_buffer=1):
    #     start_time = time.time()
    #     yearn.export(block.number, block.timestamp)
    #     duration = time.time() - start_time
    #     output_duration.export(duration, 1, "forwards", block.timestamp)
    #     time.sleep(sleep_interval)

# todo move the _views to veyfi contract
def _views():
    voting: Contract = Contract.from_abi(
            name='VotingYFI',
            address='0xd281F1C9f8B7A673D0556d5b44edE0e54CD27074',
            abi=json.load(open('interfaces/veyfi/VotingYFI.json'))
        ) 
    views = safe_views(voting.abi)
    print(views)
    return views
# @time_tracking
# def export_snapshot(snapshot, ts):
#     start = time()
#     from yearn.yearn import _yearn
#     block = closest_block_after_timestamp(ts, wait_for=True)
#     assert block is not None, "no block after timestamp found"
#     _yearn().export(block, ts)
#     logger.info("exported vaults snapshot %s took %.3fs", snapshot, time() - start)
