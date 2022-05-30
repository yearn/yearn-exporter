import os
import grpc
import logging
from hexbytes import HexBytes
from web3.types import LogReceipt
from schema.schema_pb2 import GetLogsRequest, GetCodeRequest
from schema.schema_pb2_grpc import HashBrownieStub

from yearn.singleton import Singleton

logger = logging.getLogger(__name__)

class HashBrownie(metaclass=Singleton):
    SUPPORTED_METHODS = ["eth_getCode", "eth_getLogs"]

    def __init__(self, host=os.getenv("HASH_BROWNIE_HOST"), port=os.getenv("HASH_BROWNIE_PORT", 1337)):
        self._client = None
        if host and port:
            self._channel = self._open_channel(host, port)
            self._client = HashBrownieStub(self._channel)


    def _open_channel(self, host, port):
        use_tls = os.getenv("USE_TLS", "false").lower() == "true"
        if use_tls:
            cert_path = os.getenv("TLS_CERT", "tls/server-cert.pem")
            creds = grpc.ssl_channel_credentials(open(cert_path, "rb").read())
            return grpc.secure_channel(f"{host}:{port}", creds)
        else:
            return grpc.insecure_channel(f"{host}:{port}")


    def close_channel(self):
        if self._channel:
            self._channel.close()


    def get_client(self):
        return self._client


    def supports_method(self, method):
        return method in self.SUPPORTED_METHODS


    def get_rpc_processor(self, method, params):
        if method == "eth_getCode":
            return self._get_code(params)
        elif method == "eth_getLogs":
            return self._get_logs(params)


    def _get_code(self, params):
        block = params[1]
        if params[1] == "latest":
            block = None
        else:
            block = int(block, 16)

        request = GetCodeRequest(address=params[0], block=block)
        code = self.get_client().GetCode(request)
        response = HexBytes(code.results)
        return self._json_rpc_response(response)


    def _get_logs(self, params):
        param = params[0]
        from_block = 0
        if "fromBlock" in param:
            from_block = param["fromBlock"]

        request = GetLogsRequest(from_block=int(from_block, 16))
        if "toBlock" in param:
            request.to_block = int(param["toBlock"], 16)

        if "address" in param:
            addresses = param["address"]
            if isinstance(addresses, list):
                request.addresses[:] = addresses
            else:
                request.addresses[:] = [addresses]

        if "topics" in param:
            for t in param["topics"]:
                topic_entry = request.topics.add()
                if isinstance(t, str):
                    topic_entry.topics[:] = [t]
                elif isinstance(t, list):
                    topic_entry.topics[:] = t
        logs = self.get_client().GetLogs(request)
        response = [ self._format_log(log) for log in logs.entries ]
        return self._json_rpc_response(response)


    def _format_log(self, log):
        return LogReceipt({
            "address": log.address,
            "blockHash": HexBytes(log.blockHash),
            "blockNumber": int(log.blockNumber),
            "data": log.data,
            "logIndex": int(log.logIndex),
            "removed": log.removed,
            "topics": [HexBytes(b) for b in log.topics],
            "transactionHash": HexBytes(log.transactionHash),
            "transactionIndex": int(log.transactionIndex)
        })


    def _json_rpc_response(self, response):
        return {
            "jsonrpc": "2.0",
            "id": 1, #TODO pass id
            "result": response
        }
