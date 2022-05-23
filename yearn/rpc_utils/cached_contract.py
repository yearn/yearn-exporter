import logging
from brownie import Contract
from brownie.network.contract import _ContractBase, _DeployedContractBase
from google.protobuf.json_format import MessageToDict
from schema.schema_pb2 import Abi, GetAbiRequest
from yearn.rpc_utils.hash_brownie import HashBrownie

logger = logging.getLogger(__name__)

class CachedContract(Contract):
    def __init__(self, address, block_identifier=None):
        request = GetAbiRequest(address=address)
        if block_identifier:
            request.block = block_identifier
        client = HashBrownie().get_client()
        abi = client.GetAbi(request)

        build = {
            "abi": self._format_abi(abi),
            "address": address,
            "contractName": abi.contract_name,
            "type": "contract"
        }
        _ContractBase.__init__(self, None, build, {})  # type: ignore
        _DeployedContractBase.__init__(self, address, None, None)


    def _format_abi(self, abi_message):
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
