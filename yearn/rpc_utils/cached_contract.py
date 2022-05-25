import logging
from brownie import Contract
from brownie.network.contract import _ContractBase, _DeployedContractBase
from google.protobuf.json_format import MessageToDict
from schema.schema_pb2 import Abi, GetAbiRequest, PutAbiRequest
from yearn.rpc_utils.hash_brownie import HashBrownie

logger = logging.getLogger(__name__)

class CachedContract(Contract):
    def __init__(self, address, block_identifier=None):
        request = GetAbiRequest(address=address)
        if block_identifier:
            request.block = block_identifier
        client = HashBrownie().get_client()
        abi_message = client.GetAbi(request)
        abi = None

        # rpc cache does not have this abi yet
        if len(abi_message.entries) == 0:
            (abi_message, abi) = self._construct_abi_message(address)
            put_request = PutAbiRequest(address=address, abi=abi_message)
            client.PutAbi(put_request)

        if not abi:
            abi = self._format_abi(abi_message)

        build = {
            "abi": abi,
            "address": address,
            "contractName": abi_message.contract_name,
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


    def _construct_abi_message(self, address):
        abi = Abi()
        logger.info("constructing abi for %s", address)
        try:
            c = Contract(address)
        except:
            c = Contract.from_explorer(address)

        for a in c.abi:
            entry = abi.entries.add()
            abi.contract_name = c._build["contractName"]
            # handle top-level fields
            self._populate(
                a,
                entry,
                ["type", "name", "anonymous", "gas", "stateMutability", "constant", "payable"]
            )
            # handle inputs
            if "inputs" in a and a["inputs"]:
                for i in a["inputs"]:
                    input_entry = entry.inputs.add()
                    # handle nested input fields
                    self._populate_input_output(i, input_entry)
            # handle outputs
            if "outputs" in a and a["outputs"]:
                for o in a["outputs"]:
                    output_entry = entry.outputs.add()
                    self._populate_input_output(o, output_entry)

        return (abi, c.abi)


    def _populate_input_output(self, from_obj, to_obj):
        fields =  ["name", "type", "internalType", "indexed"]
        self._populate(from_obj, to_obj, fields)

        if from_obj["type"].startswith("tuple"):
            for c in from_obj["components"]:
                component_entry = to_obj.components.add()
                self._populate_input_output(c, component_entry)


    def _populate(self, from_obj, to_obj, fields):
        for f in fields:
            if f in from_obj and from_obj[f] != "":
                value = from_obj[f]
                if f == "gas":
                    value = int(value)
                setattr(to_obj, f, value)
            else:
                # This handles unnamed args in inputs/outputs with an empty value: "name": ""
                #
                # Empty strings as values for gRPC message fields are problematic,
                # as the entire field will be missing in the constructed gRPC message.
                # For the "name" field, this breaks the client when creating a contract from this ABI.
                #
                # hack: set the "name" field to "\0" which needs to be tranformed back to "" in the client.
                if f == "name":
                    setattr(to_obj, "name", "\0")
