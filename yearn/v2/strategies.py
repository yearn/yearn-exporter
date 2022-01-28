import logging
import threading
import time
from typing import List
from yearn.apy import StrategyApy

from brownie import Contract, chain
from eth_utils import encode_hex, event_abi_to_log_topic

from yearn.utils import safe_views, contract
from yearn.multicall2 import fetch_multicall
from yearn.events import create_filter, decode_logs

SECONDS_IN_YEAR = 31557600

STRATEGY_VIEWS_SCALED = [
    "maxDebtPerHarvest",
    "minDebtPerHarvest",
    "totalDebt",
    "totalGain",
    "totalLoss",
    "estimatedTotalAssets",
    "lentTotalAssets",
    "balanceOfPool",
    "balanceOfWant",
]

STRATEGY_EVENTS = ["Harvested"]

logger = logging.getLogger(__name__)


class Strategy:
    def __init__(self, strategy, vault, watch_events_forever):
        self.strategy = contract(strategy)
        self.vault = vault
        try:
            self.name = self.strategy.name()
        except ValueError:
            self.name = strategy[:10]
        self._views = safe_views(self.strategy.abi)
        self._harvests = []
        self._harvests_data = []
        self._topics = [
            [
                encode_hex(event_abi_to_log_topic(event))
                for event in self.strategy.abi
                if event["type"] == "event" and event["name"] in STRATEGY_EVENTS
            ]
        ]
        self._watch_events_forever = watch_events_forever
        self._done = threading.Event()
        self._thread = threading.Thread(target=self.watch_events, daemon=True)

    @property
    def unique_name(self):
        if [strategy.name for strategy in self.vault.strategies].count(self.name) > 1:
            return f'{self.name} {str(self.strategy)[:8]}'
        else:
            return self.name

    def __repr__(self) -> str:
        return f"<Strategy {self.strategy} name={self.name}>"

    def __eq__(self, other):
        if isinstance(other, Strategy):
            return self.strategy == other.strategy

        if isinstance(other, str):
            return self.strategy == other

        raise ValueError("Strategy is only comparable with [Strategy, str]")

    def watch_events(self):
        start = time.time()
        self.log_filter = create_filter(str(self.strategy), topics=self._topics)
        for block in chain.new_blocks(height_buffer=12):
            logs = self.log_filter.get_new_entries()
            events = decode_logs(logs)
            self.process_events(events)
            if not self._done.is_set():
                self._done.set()
                logger.info("loaded %d harvests %s in %.3fs", len(self._harvests), self.name, time.time() - start)
            if not self._watch_events_forever:
                break
            time.sleep(300)

    def process_events(self, events):
        for event in events:
            if event.name == "Harvested":
                block = event.block_number
                logger.debug("%s harvested on %d", self.name, block)
                self._harvests.append(block)
                self._harvests_data.append({"block_number": block, "event": event})

    def load_harvests(self):
        if not self._thread._started.is_set():
            self._thread.start()
        self._done.wait()

    @property
    def harvests(self) -> List[int]:
        if len(self._harvests) == 0:
            self.load_harvests()
        return self._harvests
        
    @property
    def harvests_data(self):
        if len(self._harvests) == 0:
            self.load_harvests()
        sorted_harvests = sorted(self._harvests_data, key=lambda k: k['block_number'], reverse=True)
        return sorted_harvests

    @property
    def debt_ratio(self):
        return self.vault.vault.strategies(self.strategy.address).dict()['debtRatio'] / 1e4

    @property
    def apy(self) -> StrategyApy:
        harvests = self.harvests_data

        # Find at least two profitable harvests
        profitable_harvests_count = 0
        for idx, harvest in enumerate(harvests):
            profit = harvest['event']['profit']
            if profit > 0:
                profitable_harvests_count += 1
                if profitable_harvests_count == 1:
                    latest_harvest_with_profit_idx = idx
                elif profitable_harvests_count == 2:
                    second_latest_harvest_with_profit_idx = idx
                    break

        # Not enough profitable harvests
        if profitable_harvests_count < 2:
            return StrategyApy(0, 0)

        # Not enough data
        have_enough_data = second_latest_harvest_with_profit_idx + 1 < len(harvests)
        if have_enough_data == False:
            return StrategyApy(0, 0)

        # Latest profitable harvest
        latest_harvest_with_profit_current = harvests[latest_harvest_with_profit_idx]
        second_latest_harvest_with_profit_current = harvests[latest_harvest_with_profit_idx + 1]
        harvest_profit_current = latest_harvest_with_profit_current['event']['profit']
        seconds_between_harvests_current = chain[latest_harvest_with_profit_current['block_number']]['timestamp'] - chain[second_latest_harvest_with_profit_current['block_number']]['timestamp']
        block_before_profitable_harvest_current = latest_harvest_with_profit_current['block_number'] - 1
        vault = self.vault.vault
        strategy = self.strategy
        strategy_debt_current = vault.strategies(strategy.address, block_identifier=block_before_profitable_harvest_current).dict()['totalDebt']
        if strategy_debt_current == 0:
            current_apr = 0
        else:
            current_apr = harvest_profit_current / strategy_debt_current * (SECONDS_IN_YEAR / seconds_between_harvests_current)    

        # Second latest profitiable harvest
        latest_harvest_with_profit_previous = harvests[second_latest_harvest_with_profit_idx]
        second_latest_harvest_with_profit_previous = harvests[second_latest_harvest_with_profit_idx + 1]
        harvest_profit_previous = latest_harvest_with_profit_previous['event']['profit']
        seconds_between_harvests_previous = chain[latest_harvest_with_profit_previous['block_number']]['timestamp'] - chain[second_latest_harvest_with_profit_previous['block_number']]['timestamp']
        block_before_profitable_harvest_previous = latest_harvest_with_profit_previous['block_number'] - 1
        strategy_debt_previous = vault.strategies(strategy.address, block_identifier=block_before_profitable_harvest_previous).dict()['totalDebt']
        if strategy_debt_previous == 0:
            previous_apr = 0
        else:
            previous_apr = harvest_profit_previous / strategy_debt_previous * (SECONDS_IN_YEAR / seconds_between_harvests_previous)    

        # Account for new vault use case
        if previous_apr == 0 and current_apr > 0:
            apr = current_apr
        # Account for early withdrawal edge case
        elif current_apr > previous_apr * 2  or current_apr * 2 < previous_apr:
            apr = previous_apr
        # Account for sunshine use case
        else:
            apr = current_apr

        # Determine fees
        strategy_performance_fee = vault.strategies(strategy.address).dict()['performanceFee'] / 1e4
        vault_performance_fee = vault.performanceFee() / 1e4
        performance_fee = vault_performance_fee + strategy_performance_fee
        management_fee = vault.managementFee() / 1e4 if hasattr(vault, "managementFee") else 0
        
        # Subtract fees
        apr_minus_fees = apr * (1 - performance_fee) - management_fee

        # assume we are compounding every week on mainnet, daily on sidechains
        if chain.id == 1:
            compounding = 52
        else:
            compounding = 365.25
        
        # Convert APR to annualized estimated APY
        net_apy = (1 + (apr_minus_fees / compounding)) ** compounding - 1

        # Return estimated APY
        return StrategyApy(apr, net_apy)

    def describe(self, block=None):
        results = fetch_multicall(
            *[[self.strategy, view] for view in self._views],
            [self.vault.vault, "strategies", self.strategy],
            block=block,
        )
        info = dict(zip(self._views, results))
        info.update(results[-1].dict())
        for view in STRATEGY_VIEWS_SCALED:
            if view in info:
                info[view] = (info[view] or 0) / self.vault.scale
        # unwrap structs
        for view in info:
            if hasattr(info[view], '_dict'):
                info[view] = info[view].dict()

        return info
