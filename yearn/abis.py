
# This module is used to ensure necessary contracts with frequent issues are correctly defined in brownie's deployments.db

from typing import Dict, List

from brownie import interface
from y import Contract, ContractNotVerified, Network
from y.constants import CHAINID
from y.prices.lending import compound


class IncorrectABI(Exception):
    pass

# {non_verified_contract_address: verified_contract_address}
non_verified_contracts: Dict[str,str] = {
    Network.Fantom: {
        "0x154eA0E896695824C87985a52230674C2BE7731b": "0xbcab7d083Cf6a01e0DdA9ed7F8a02b47d125e682",
    },
}.get(CHAINID,{})

def _fix_problematic_abis() -> None:
    __force_non_verified_contracts()
    __validate_unitroller_abis()
    __set_abis_with_interfaces()

def __force_non_verified_contracts():
    for non_verified_contract, verified_contract in non_verified_contracts.items():
        try:
            Contract(non_verified_contract)
        except Exception:
            verified_contract = Contract(verified_contract)
            Contract.from_abi(
                verified_contract._build['contractName'],
                non_verified_contract,
                verified_contract.abi,
            )

def __validate_unitroller_abis() -> None:
    '''
    Ensure correct abi for comptrollers.
    This might not always work. If it fails and your script doesn't require the `price` module, you should be fine.
    If this fails and your script does require the `price` module, you will need to manually cache the correct abi in `deployments.db`.
    '''
    good: List[Contract] = []
    bad: List[Contract] = []
    for troller in compound.trollers.values():
        address = troller.address
        # We use `Contract` instead of `contract` here so
        #  we don't cache any incorrect ABIs into memory.
        try:
            unitroller = Contract(address)
        except ContractNotVerified:
            pass
        except ValueError as e:
            if not str(e).startswith("Unknown contract address: "):
                raise e
            unitroller = Contract.from_explorer(address)

        if hasattr(unitroller,'getAllMarkets'):
            good.append(unitroller)
        else:
            bad.append(unitroller)
        
    if not bad:
        return

    if not good:
        fixed: List[int] = []
        for i, unitroller in enumerate(bad):
            unitroller = Contract.from_explorer(unitroller.address)
            if hasattr(unitroller,'getAllMarkets'):
                good.append(unitroller)
                fixed.append(i)
        fixed.sort(reverse=True)
        for i in fixed:
            bad.pop(i)
        
    if not good:
        raise IncorrectABI('''
            Somehow, none of your unitrollers have a correct abi.
            You will need to manually cache one or more abi into brownie
            using `brownie.Contract.from_abi` in order to use this module.''')
    
    for unitroller in bad:
        # Force update the in-memory cache with the correct object
        Contract.from_abi(unitroller._build['contractName'], unitroller.address, good[0].abi)
        Contract._ChecksumAddressSingletonMeta__instances.pop(unitroller.address)
        Contract(unitroller.address)

abis_to_fix = {
    Network.Mainnet: {
        # These are now using some weird non-verified proxy
        "0x098256c06ab24F5655C5506A6488781BD711c14b": interface.ATokenVault,  # waDAI
        "0xa7E0e66F38b8ad8343CFF67118C1f33e827D1455": interface.ATokenVault,  # waUSDT
        "0x57d20c946A7A3812a7225B881CdcD8431D23431C": interface.ATokenVault,  # waUSDC
    },
}

def __set_abis_with_interfaces():
    for address, interface in abis_to_fix.get(CHAINID, {}).items():
        Contract.from_abi(interface._name, address, interface.abi)