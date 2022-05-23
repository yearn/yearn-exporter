import os
import grpc
from hexbytes import HexBytes
from web3.datastructures import AttributeDict
from google.protobuf.json_format import MessageToDict
from brownie import Contract
from brownie.network.contract import _ContractBase, _DeployedContractBase
from schema.schema_pb2 import Abi, GetAbiRequest, GetLogsRequest, GetCodeRequest
from schema.schema_pb2_grpc import HashBrownieStub

from yearn.singleton import Singleton

class CachedContract(Contract):
    def __init__(self, address, block_identifier=None):
        request = GetAbiRequest(address=address)
        if block_identifier:
            request.block = block_identifier
        client = HashBrownieClient().get_client()
        abi = client.GetAbi(request)

        build = {
            "abi": _format_abi(abi),
            "address": address,
            "contractName": abi.contract_name,
            "type": "contract"
        }
        _ContractBase.__init__(self, None, build, {})  # type: ignore
        _DeployedContractBase.__init__(self, address, None, None)


class HashBrownieClient(metaclass=Singleton):
    SUPPORTED_METHODS = ["eth_getCode", "eth_getLogs"]

    def __init__(self, host=os.getenv("HASH_BROWNIE_HOST"), port=1337):
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
            return _get_code(params)
        elif method == "eth_getLogs":
            return _get_logs(params)


    def _get_code(self, params):
        request = GetCodeRequest(address=params[0], block=int(params[1]))
        code = self.get_client().GetCode(request)
        response = MessageToDict(code.results)
        return self._json_rpc_response(response)


    def _get_logs(self, params):
        param = params[0]
        from_block = 0
        if "fromBlock" in param:
            from_block = param["from_block"]

        request = GetLogsRequest(from_block=from_block)
        if "toBlock" in param:
            request.to_block = param["toBlock"]

        addresses = param["addresses"]
        if isinstance(addresses, list):
            request.addresses[:] = addresses
        else:
            request.addresses[:] = [addresses]

        if "topics" in param:
            for t in param["topics"]:
                topic_entry = request.topics.add()
                topic_entry.topics[:] = t

        logs = self.get_client().GetLogs(request)
        response = MessageToDict(logs.entries)
        return self._json_rpc_response(response)


    def _json_rpc_response(self, response):
        return {
            "jsonrpc": "2.0",
            "id": 1, #TODO pass id
            "result": response
        }


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

        for input_entry in entry["inputs"]:
            if "name" in input_entry:
                if input_entry["name"] == "\0":
                    input_entry["name"] = ""
        for output_entry in entry["outputs"]:
            if "name" in output_entry:
                if output_entry["name"] == "\0":
                    output_entry["name"] = ""

    return asDict["entries"]
