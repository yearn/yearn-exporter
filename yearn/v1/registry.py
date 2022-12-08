import logging

from brownie import chain, interface, web3
from dank_mids.brownie_patch import patch_contract
from multicall.utils import gather
from y.utils.dank_mids import dank_w3
from yearn.exceptions import UnsupportedNetwork
from yearn.multicall2 import fetch_multicall_async
from yearn.networks import Network
from yearn.utils import contract, contract_creation_block, run_in_thread
from yearn.v1.vaults import VaultV1

logger = logging.getLogger(__name__)


class Registry:
    def __init__(self):
        if chain.id != Network.Mainnet:
            raise UnsupportedNetwork("Vaults V1 registry is only available on Mainnet.")

        self.registry = patch_contract(interface.YRegistry(web3.ens.resolve("registry.ychad.eth")), dank_w3)
        addresses_provider = contract("0x9be19Ee7Bc4099D62737a7255f5c227fBcd6dB93")
        addresses_generator_v1_vaults = contract(addresses_provider.addressById("ADDRESSES_GENERATOR_V1_VAULTS"))

        # NOTE: we assume no more v1 vaults are deployed
        self.vaults = [VaultV1(vault_address, *self.registry.getVaultInfo(vault_address)) for vault_address in addresses_generator_v1_vaults.assetsAddresses()]
            
    def __repr__(self) -> str:
        return f"<Registry V1 vaults={len(self.vaults)}>"

    async def describe(self, block=None):
        vaults = self.active_vaults_at(block)
        share_prices = await fetch_multicall_async(*[[vault.vault, "getPricePerFullShare"] for vault in vaults], block=block)
        vaults = [vault for vault, share_price in zip(vaults, share_prices) if share_price]
        data = await gather(vault.describe(block=block) for vault in vaults)
        return {vault.name: desc for vault, desc in zip(vaults, data)}

    async def total_value_at(self, block=None):
        vaults = await run_in_thread(self.active_vaults_at, block)
        balances = await fetch_multicall_async(*[[vault.vault, "balance"] for vault in vaults], block=block)
        # skip vaults with zero or erroneous balance
        vaults = [(vault, balance) for vault, balance in zip(vaults, balances) if balance]
        prices = await gather(vault.get_price(block) for (vault, balance) in vaults)
        #prices = Parallel(8, "threading")(delayed(vault.get_price)(block) for (vault, balance) in vaults)
        return {vault.name: balance * price / 10 ** vault.decimals for (vault, balance), price in zip(vaults, prices)}

    def active_vaults_at(self, block=None):
        vaults = list(self.vaults)
        if block:
            vaults = [vault for vault in vaults if contract_creation_block(str(vault.vault)) < block]
        return vaults
