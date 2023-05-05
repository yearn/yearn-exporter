
# This module is used to ensure necessary contracts with frequent issues are correctly defined in brownie's deployments.db

from typing import Dict, List

from brownie import Contract, chain
from y.networks import Network

from yearn.utils import contract


class IncorrectABI(Exception):
    pass

# {non_verified_contract_address: verified_contract_address}
non_verified_contracts: Dict[str,str] = {
    Network.Fantom: {
        "0x154eA0E896695824C87985a52230674C2BE7731b": "0xbcab7d083Cf6a01e0DdA9ed7F8a02b47d125e682",
    },
}.get(chain.id,{})

def _fix_problematic_abis() -> None:
    __force_non_verified_contracts()
    __validate_unitroller_abis()

def __force_non_verified_contracts():
    for non_verified_contract, verified_contract in non_verified_contracts.items():
        try:
            contract(non_verified_contract)
        except:
            verified_contract = contract(verified_contract)
            build_name = verified_contract._build['contractName']
            abi = verified_contract.abi
            Contract.from_abi(build_name,non_verified_contract,abi)

def __validate_unitroller_abis() -> None:
    '''
    Ensure correct abi for comptrollers.
    This might not always work. If it fails and your script doesn't require the `price` module, you should be fine.
    If this fails and your script does require the `price` module, you will need to manually cache the correct abi in `deployments.db`.
    '''
    # we can't just import the list of unitrollers, the import will fail if one of their abi definitions are messed up
    unitrollers: List[str] = {
        Network.Mainnet: [
            "0x3d9819210A31b4961b30EF54bE2aeD79B9c9Cd3B",
            "0x3d5BC3c8d13dcB8bF317092d84783c2697AE9258",
            "0xAB1c342C7bf5Ec5F02ADEA1c2270670bCa144CbB",
        ],
    }.get(chain.id, [])

    good: List[Contract] = []
    bad: List[Contract] = []
    for address in unitrollers:
        # We use `Contract` instead of `contract` here so
        #  we don't cache any incorrect ABIs into memory.
        try:
            unitroller = Contract(address)
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
        Contract.from_abi(
            unitroller._build['contractName'],
            unitroller.address,
            good[0].abi)

    raise IncorrectABI(f"""
        Re-cached Comptroller {address} that was misdefined in brownie's db.
        Restarting to ensure the in-memory `contract('{address}')` cache is correct.
        If you were running your script manually, please restart. 
        Everything will run fine upon restart.""")
