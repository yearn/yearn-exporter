
from typing import List, Optional

from brownie import chain
from pony.orm import db_session, select
from y import Contract

from yearn.constants import YCHAD_MULTISIG, YFI
from yearn.entities import Stream, Token, TxGroup
from yearn.events import decode_logs, get_logs_asap
from yearn.outputs.postgres.utils import token_dbid
from yearn.treasury.constants import BUYER

dai = "0x6B175474E89094C44Da98b954EedeAC495271d0F"

streams_dai = Contract('0x60c7B0c5B3a4Dc8C690b074727a17fF7aA287Ff2')
streams_yfi = Contract('0xf3764eC89B1ad20A31ed633b1466363FAc1741c4')

class YearnStreams:
    def __init__(self):
        assert chain.id == 1
        self.stream_contracts = [streams_dai, streams_yfi]
        self.skipped_events = ["PayerDeposit", "PayerWithdraw", "Withdraw"]
        self.handled_events = ["StreamCreated", "StreamCreatedWithReason", "StreamModified", "StreamPaused", "StreamCancelled"]
        self.get_streams()
            
    def __getitem__(self, key: str):
        if isinstance(key, bytes):
            key = key.hex()
        return Stream[key]

    def streams_for_recipient(self, recipient: str, at_block: Optional[int] = None) -> List[Stream]:
        if at_block is None:
            return list(select(s for s in Stream if s.to_address.address == recipient))
        return list(select(s for s in Stream if s.to_address.address == recipient and (s.end_block is None or at_block <= s.end_block)))
    
    def streams_for_token(self, token: str, include_inactive: bool = False) -> List[Stream]:
        streams = list(select(s for s in Stream if s.token.token_id == token_dbid(token)))
        if include_inactive is False:
            streams = [s for s in streams if s.is_alive]
        return streams

    def buyback_streams(self, include_inactive: bool = False) -> List[Stream]:
        streams = self.streams_for_recipient(BUYER)
        if include_inactive is False:
            streams = [s for s in streams if s.is_alive]
        return streams
    
    @db_session
    def dai_streams(self, include_inactive: bool = False) -> List[Stream]:
        return self.streams_for_token(dai, include_inactive=include_inactive)

    @db_session
    def yfi_streams(self, include_inactive: bool = False) -> List[Stream]:
        return self.streams_for_token(YFI, include_inactive=include_inactive)
    
    @db_session
    def streams(self, include_inactive: bool = False):
        if include_inactive is True:
            return list(select(s for s in Stream))
        return list(select(s for s in Stream if s.is_alive))

    @db_session
    def get_streams(self):
        for stream_contract in self.stream_contracts:
            logs = decode_logs(get_logs_asap([stream_contract.address]))

            for k in logs.keys():
                if k not in self.handled_events and k not in self.skipped_events:
                    raise NotImplementedError(f"We need to build handling for {k} events.")

            for log in logs['StreamCreated']:
                from_address, *_ = log.values()
                if from_address != YCHAD_MULTISIG:
                    continue
                Stream.get_or_create_entity(log)
            
            if "StreamCreatedWithReason" in logs:
                for log in logs['StreamCreatedWithReason']:
                    from_address, *_ = log.values()
                    if from_address != YCHAD_MULTISIG:
                        continue
                    Stream.get_or_create_entity(log)
            
            for log in logs['StreamModified']:
                from_address, _, _, old_stream_id, *_ = log.values()
                if from_address != YCHAD_MULTISIG:
                    continue
                self[old_stream_id].stop_stream(log.block_number)
                Stream.get_or_create_entity(log)

            if 'StreamPaused' in logs:
                for log in logs['StreamPaused']:
                    from_address, *_, stream_id = log.values()
                    if from_address != YCHAD_MULTISIG:
                        continue
                    self[stream_id].pause(log.block_number)
            
            if 'StreamCancelled' in logs:
                for log in logs['StreamCancelled']:
                    from_address, *_, stream_id = log.values()
                    if from_address != YCHAD_MULTISIG:
                        continue
                    self[stream_id].stop_stream(log.block_number)

        team_payments_txgroup = TxGroup.get(name = "Team Payments")
        for stream in self.yfi_streams(include_inactive=True):
            for stream in self.streams_for_recipient(stream.to_address.address):
                if stream.txgroup is None:
                    stream.txgroup = team_payments_txgroup
