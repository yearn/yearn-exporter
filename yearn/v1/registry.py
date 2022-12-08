import asyncio
import logging
from functools import cached_property
from typing import Dict, List, Optional

from brownie import chain, interface, web3
from dank_mids.brownie_patch import patch_contract
from y.contracts import contract_creation_block_async
from y.networks import Network
from y.utils.dank_mids import dank_w3

from yearn.exceptions import UnsupportedNetwork
from yearn.multicall2 import fetch_multicall_async
from yearn.typing import Block
from yearn.utils import contract
from yearn.v1.vaults import VaultV1

logger = logging.getLogger(__name__)


class Registry:
    def __init__(self) -> None:
        if chain.id != Network.Mainnet:
            raise UnsupportedNetwork("Vaults V1 registry is only available on Mainnet.")

        self.registry = patch_contract(interface.YRegistry(web3.ens.resolve("registry.ychad.eth")), dank_w3)
    
    @cached_property
    def vaults(self) -> List[VaultV1]:
        addresses_provider = contract("0x9be19Ee7Bc4099D62737a7255f5c227fBcd6dB93")
        addresses_generator_v1_vaults = contract(addresses_provider.addressById("ADDRESSES_GENERATOR_V1_VAULTS"))

        # NOTE: we assume no more v1 vaults are deployed
        return [VaultV1(vault_address, *self.registry.getVaultInfo(vault_address)) for vault_address in addresses_generator_v1_vaults.assetsAddresses()]
            
    def __repr__(self) -> str:
        return f"<Registry V1 vaults={len(self.vaults)}>"

    async def describe(self, block: Optional[Block] = None) -> Dict[str, Dict]:
        vaults = await self.active_vaults_at(block)
        share_prices = await fetch_multicall_async(*[[vault.vault, "getPricePerFullShare"] for vault in vaults], block=block)
        vaults = [vault for vault, share_price in zip(vaults, share_prices) if share_price]
        data = await asyncio.gather(*[vault.describe(block=block) for vault in vaults])
        return {vault.name: desc for vault, desc in zip(vaults, data)}

    async def total_value_at(self, block: Optional[Block] = None) -> Dict[str, float]:
        vaults = await self.active_vaults_at(block)
        balances = await fetch_multicall_async(*[[vault.vault, "balance"] for vault in vaults], block=block)
        # skip vaults with zero or erroneous balance
        vaults = [(vault, balance) for vault, balance in zip(vaults, balances) if balance]
        prices = await asyncio.gather(*[vault.get_price(block) for (vault, balance) in vaults])
        return {vault.name: balance * price / 10 ** vault.decimals for (vault, balance), price in zip(vaults, prices)}

    async def active_vaults_at(self, block: Optional[Block] = None) -> List[VaultV1]:
        if block:
            blocks = await asyncio.gather(*[contract_creation_block_async(str(vault.vault)) for vault in self.vaults])
            return [vault for vault, deploy_block in zip(self.vaults, blocks) if deploy_block < block]
        return self.vaults
