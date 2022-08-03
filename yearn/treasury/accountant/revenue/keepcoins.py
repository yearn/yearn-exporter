
# keepCOINS: excludes keepCRV as the CRV are locked forever.

from brownie import chain
from yearn.entities import TreasuryTx
from yearn.networks import Network
from yearn.treasury.accountant.constants import treasury

angle_strats_with_non_specific_names = {
    Network.Mainnet: [
        "0x2CB390212b0e5091a3c0D0331669c1419165CF80",
        "0x7C2b9DB2Ae5aCC6fAC2Fd6cE9b01A5EB4bDD1309",
    ],
}.get(chain.id, [])

def is_keep_angle(tx: TreasuryTx) -> bool:
    if tx._symbol == "ANGLE" and tx.to_address and tx.to_address.address in treasury.addresses:
        if tx._from_nickname == "Contract: StrategyAngleUSDC":
            return True
        return tx.from_address.address in angle_strats_with_non_specific_names
        
    return False

def is_keep_bal(tx: TreasuryTx) -> bool:
    strats = [
        "SSBv3 DAI staBAL3",
        "SSBv3 USDC staBAL3",
        "SSBv3 USDT staBAL3",
        "SSBv3 WETH B-stETH-STABLE",
        "SSBv3 WBTC staBAL3-BTC",
    ]

    # Contract: Strategy (unhelpful name, we can use address though)
    _strats = [
        "0x960818b3F08dADca90b840298721FE7B419fBE12",
        "0x074620e389B5715f7ba51Fc062D8fFaf973c7E02",
        "0xB0F8b341951233BF08A5F15a838A1a85B016aEf9",
        "0x034d775615d50D870D742caA1e539fC8d97955c2",
        "0xe614f717b3e8273f38Ed7e0536DfBA60AD021c85",
    ]

    if (
        tx._symbol == "BAL" and
        
        tx.to_address and tx.to_address.address in treasury.addresses and
        (any(f"Contract: {strat}" == tx._from_nickname for strat in strats) or (any(strat.address == tx.from_address.address) for strat in _strats))
    ):
        return True
    return False

def is_keep_beets(tx: TreasuryTx) -> bool:
    if tx._symbol == "BEETS" and tx.to_address and tx.to_address.address in treasury.addresses and tx.hash != "0x1e997aa8c79ece76face8deb8fe7df4cea4f6a1ef7cd28501013ed30dfbe238f":
        return True
    return False

def is_keep_pool(tx: TreasuryTx) -> bool:
    if tx._symbol == "POOL" and tx._from_nickname == "Contract: StrategyPoolTogether" and tx.to_address and tx.to_address.address in treasury.addresses:
        return True
    return False
