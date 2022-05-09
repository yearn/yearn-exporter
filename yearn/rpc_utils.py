import os
import grpc
from hexbytes import HexBytes
from web3.datastructures import AttributeDict
from google.protobuf.json_format import MessageToDict
from brownie import Contract
from brownie.network.contract import _ContractBase, _DeployedContractBase
from schema.schema_pb2 import Abi, GetAbiRequest, GetLogsRequest
from schema.schema_pb2_grpc import HashBrownieStub

from yearn.singleton import Singleton

class HashBrownieClient(metaclass=Singleton):
    def __init__(self, host=os.getenv("HASH_BROWNIE_HOST"), port=1337):
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


class CachedContract(Contract):
    def __init__(self, address):
        request = GetAbiRequest(address=address)
        client = HashBrownieClient().get_client()
        abi = client.GetAbi(request)

        build = {
            "abi": _format_abi(abi),
            "address": address,
            "contractName": "yrpc-abi", # TODO fix name
            "type": "contract"
        }
        _ContractBase.__init__(self, None, build, {})  # type: ignore
        _DeployedContractBase.__init__(self, address, None, None)


def cached_logs(addresses, topics=None, start_block=None):
    request = GetLogsRequest(start_block=start_block)

    if isinstance(addresses, list):
        request.addresses[:] = addresses
    else:
        request.addresses[:] = [addresses]

    if topics:
        for t in topics:
            topic_entry = request.topics.add()
            topic_entry.topics[:] = t

    client = HashBrownieClient().get_client()
    logs = client.GetLogs(request)
    return [ _format_log(log) for log in logs.entries ]


def _format_log(log):
    return AttributeDict({
        "address": log.address,
        "topics": [HexBytes(b) for b in log.topics],
        "data": log.data,
        "blockNumber": int(log.blockNumber),
        "transactionHash": HexBytes(log.transactionHash),
        "transactionIndex": int(log.transactionIndex),
        "blockHash": HexBytes(log.blockHash),
        "logIndex": int(log.logIndex),
        "removed": log.removed
    })


def _format_abi(abi_message):
    asDict = MessageToDict(abi_message)
    for entry in asDict["entries"]:
        # fill inputs with empty defaults
        if "inputs" not in entry:
            entry["inputs"] = []
        # cast gas to int
        if "gas" in entry:
            entry["gas"] = int(entry["gas"])

        # fill outputs with empty defaults
        if "outputs" not in entry:
            entry["outputs"] = []

    return asDict["entries"]
