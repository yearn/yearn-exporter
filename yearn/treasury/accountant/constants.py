
from brownie import chain
from yearn.networks import Network
from yearn.treasury.treasury import YearnTreasury
from yearn.v1.registry import Registry as RegistryV1
from yearn.v2.registry import Registry as RegistryV2

treasury = YearnTreasury()

v1 = RegistryV1() if chain.id == Network.Mainnet else None
v2 = RegistryV2()

PENDING_LABEL = "Categorization Pending"

DISPERSE_APP = {
    Network.Mainnet: "0xD152f549545093347A162Dce210e7293f1452150",
    Network.Fantom:  "0xD152f549545093347A162Dce210e7293f1452150"
}.get(chain.id, None)

""" This wallet is an EOA that has been used to assist in bridging tokens across chains. """
BRIDGE_ASSISTOOOR = "0x5FcdC32DfC361a32e9d5AB9A384b890C62D0b8AC"
