
from decimal import Decimal

from brownie import chain
from yearn.entities import TreasuryTx
from yearn.networks import Network
from yearn.treasury.accountant.classes import HashMatcher, TopLevelTxGroup
from yearn.treasury.accountant.ignore import (general, maker, passthru,
                                              rescue_missions, staking, vaults,
                                              ygov)
from yearn.treasury.accountant.ignore.swaps import (aave, buying_yfi, compound,
                                                    cowswap, curve, robovault,
                                                    synthetix, uniswap,
                                                    unwrapper, yla)
from yearn.utils import contract

IGNORE_LABEL = "Ignore"

ignore_txgroup = TopLevelTxGroup(IGNORE_LABEL)

def is_kp3r(tx: TreasuryTx) -> bool:
    contract_names = [
        'Keep3rEscrow',
        'OracleBondedKeeper',
        'Keep3rLiquidityManager',
    ]

    hashes = [
        '0x3efaafc34054dbc50871abef5e90a040688fbddc51ec4c8c45691fb2f21fd495'
    ]

    if tx._symbol == "kLP-KP3R/WETH" and tx._to_nickname == "Contract: Keep3r" and "LiquidityAddition" in tx._events:
        for event in tx._events['LiquidityAddition']:
            _, _, _, amount = event.values()
            if Decimal(amount) / tx.token.scale == tx.amount:
                return True

    try:
        return (
            (
                tx.to_address and tx.to_address.token and tx.to_address.token.symbol == 'KP3R'
            )
            or (
                tx.to_address and tx.to_address.is_contract
                and contract(tx.to_address.address)._build['contractName'] in contract_names
            )
            or (
                tx.from_address.is_contract
                and contract(tx.from_address.address)._build['contractName'] in contract_names
            )
            or HashMatcher(hashes).contains(tx)
        )
    except ValueError as e:
        if not str(e).endswith('has not been verified') and "Contract source code not verified" not in str(e):
            raise
        return False

def is_bridged(tx: TreasuryTx) -> bool:

    # Anyswap out - anyToken part
    if tx._symbol and tx._symbol.startswith("any") and "LogAnySwapOut" in tx._events:
        for event in tx._events["LogAnySwapOut"]:
            token, sender, receiver, amount, from_chainid, to_chainid = event.values()
            if from_chainid == chain.id and tx.token.address.address == token and Decimal(amount) / tx.token.scale == tx.amount:
                return True
    
    # Anyswap out - token part
    elif tx.to_address and tx.to_address.token and tx.to_address.token.symbol and tx.to_address.token.symbol.startswith("any") and "LogAnySwapOut" in tx._events:
        for event in tx._events["LogAnySwapOut"]:
            token, sender, receiver, amount, from_chainid, to_chainid = event.values()
            if from_chainid == chain.id and tx.token.address.address == contract(token).underlying() and Decimal(amount) / tx.token.scale == tx.amount:
                return True

    return tx in HashMatcher({
        Network.Mainnet: [
            "0x2dbd613f0047ee14fff45649a0b15d794b38f855117abaa2432f64e36e797928",
            "0xa33aac01e36b0e27d2a401e012f45870d75bfa2dedc99fc6d953c7462c709157",
            "0xe3d2212f27ece6d04249d8e46c5518194398a7cb95aedd0d1b1afd2b7524bc36",
            "0x3002fa18063bf659f74996b2d34fc6455bc9d2e4d812c5e539dd5c935ba8e11b",
        ],
        Network.Fantom: [
            "0xf6b3d70fed6a472dfda1926e1b509a478e29dcb6c481f32358cafb46d4a1c565",
            "0x034a36cc39d6e75f21ea9624602e503eee826a81e4a29639752c66a3f3e29dbc",
            "0x05005f57f125efc4eb3a7c0e8648ccd8b32e202367e8fc79bc6187eb21cbe51e",
            "0x38a480b47739d311cfb3904887b9f8bd5fcafe471e8dafd1bdbfdf9dfa6db9a4",
            "0xfe6055acfc47d3bedb8a96ff0f25b471c79f26ebea737f8484b4437aa902163a",
            "0xd0840f09e24a7bda2dbb69949dab58dbbf92a571ceb4a2e6180d1426ca59af13",
            "0xbdcc07695c64cd73f3d58a87e20c3a4d9e3353eef5bd31fa9d8d8ade6cfa27b7",
            "0x5a57b259fe5a1ecfea980e7302894ab5954f15eddf4cf075883cd0b6f1568f83",
            "0xebb141d6992dda4d50e12f2ccd9072f59606dca7310fbfd54ef08735dba662d9",
            "0x54d0a847c6789232385d15ec3f7fee9ef0956e0907a68fc8e58b26c9c06b28e6",
            "0x9444e895e2b9142282707150793b42aeb9a4f3d2ece12a642300493e60843964",
            "0xb5ce60d1eeeee6c7a8e93b58e4c275874bf183a1a904820d7544eaa9d79595c1",
            "0x295c026c967d6b1cb9a5309489c6c77fbb95febd6ffea2ac67af3ed6de15cc30",
            "0xb602341eae919f291d9da3d36ab4d412e95afcc76b9ffec443fb6a20eb8f6ccf",
            "0x53df09ce4c930ab941e135ba42f1e8b95338f090dc0fdb05ce5f7510f3be5e31",
            "0xcde638ff75129b49542ce082c0f62ae91e3afedc8ef151e7f512dc8478b40bb3",
            "0x684b5810fc450b76177631ce05f8293bc251e09f6d3a7e9cb536ceeb53802bc1",
            "0x7640eea4d3c43017093a7f77a6b2ac17922700f0bcebc3f08251c0f9522e0efa",
            "0xfe276ef6c9f4915c50623c2944c0bef37b99841a0adba251a0c6ecdf348f5e7b",
            "0xc3922feed46d566829360dc2c7d8a78b51ad1eea71969e5e39ae069bc3c135c2",
            "0xc1ffb3d9f2907e075bd2c79b09d4020843296b0ed7bbd6b865307f44ecf56235",
        ],
    }.get(chain.id, []))

def is_keep_crv(tx: TreasuryTx) -> bool:
    """ keepCRV is not considered income as 100% of the CRV is locked forever and the benefits go to yveCRV holders."""
    if not (chain.id == Network.Mainnet and tx._symbol == "CRV"):
        return False
    # keepCRV received
    if tx._from_nickname == "Contract: StrategyCurveYCRVVoter" and tx._to_nickname == "Yearn Treasury":
        return True
    # keepCRV locked
    if tx._from_nickname == "Yearn yChad Multisig" and tx._to_nickname == "Contract: CurveYCRVVoter":
        return True
    return False

# Keep these in order blz
ignore_txgroup.create_child("Zero Amount", general.has_amount_zero)
ignore_txgroup.create_child("Internal Transfer", general.is_internal_transfer)
ignore_txgroup.create_child("keepCRV", is_keep_crv)

# Vaults
ignore_txgroup.create_child("Vault Deposit", vaults.is_vault_deposit)
ignore_txgroup.create_child("Vault Withdrawal", vaults.is_vault_withdrawal)

ignore_txgroup.create_child("DOLA Fed Withdrawal", vaults.is_dolla_fed_withdrawal)

ignore_txgroup.create_child("Bonding KP3R", is_kp3r)
ignore_txgroup.create_child("Gnosis Safe Execution", general.is_gnosis_execution)
ignore_txgroup.create_child("Bridged to Other Chain", is_bridged)
ignore_txgroup.create_child("Wrapping/Unwrapping Gas Tokens", general.is_weth)
ignore_txgroup.create_child("Scam Airdrop", general.is_scam_airdrop)
if chain.id == Network.Mainnet:
    ignore_txgroup.create_child("Transfer to yGov (Deprecated)", ygov.is_sent_to_ygov)
    ignore_txgroup.create_child("Maker CDP Deposit", maker.is_yfi_cdp_deposit)
    ignore_txgroup.create_child("Maker CDP Withdrawal", maker.is_yfi_cdp_withdrawal)
elif chain.id == Network.Fantom:
    ignore_txgroup.create_child("OTCTrader", general.is_otc_trader)

ignore_txgroup.create_child("Sent thru Disperse.app", general.is_disperse_dot_app)

# Pass-Thru to vaults
passthru_txgroup = ignore_txgroup.create_child("Pass-Thru to Vaults", passthru.is_pass_thru)
passthru_txgroup.create_child("Curve Bribes for yveCRV", passthru.is_curve_bribe)
if chain.id == Network.Mainnet:
    passthru_txgroup.create_child("Cowswap Migration", passthru.is_cowswap_migration)
    passthru_txgroup.create_child("Single Sided IB", passthru.is_single_sided_ib)
    passthru_txgroup.create_child("StrategyConvex3CrvRewardsClonable", passthru.is_cvx)
    passthru_txgroup.create_child("stkAAVE", passthru.is_stkaave)
    passthru_txgroup.create_child("yvBoost INCOMPLETE", passthru.is_buying_yvboost)
    passthru_txgroup.create_child("yvBoost from elsewhere INCOMPLETE", passthru.is_yvboost_from_elsewhere)
elif chain.id == Network.Fantom:
    passthru_txgroup.create_child("IB", passthru.is_ib)
    passthru_txgroup.create_child("yvUSDC STABEET", passthru.is_usdc_stabeet)
# other pass-thru
if chain.id == Network.Mainnet:
    passthru_txgroup.create_child("Inverse-earned YearnFed Fees", passthru.is_inverse_fees_from_yearn_fed)


# Rescue Missions
if chain.id == Network.Fantom:
    ignore_txgroup.create_child("scDAI Salvage Mission", rescue_missions.is_scdai_salvage)

# Swaps
swaps_txgroup = ignore_txgroup.create_child("Swaps")
swaps_txgroup.create_child("Add Curve Liquidity", curve.is_curve_deposit)
swaps_txgroup.create_child("Remove Curve Liquidity", curve.is_curve_withdrawal)
swaps_txgroup.create_child("Curve Swap", curve.is_curve_swap)

swaps_txgroup.create_child("Add Uniswap Liquidity", uniswap.is_uniswap_deposit)
swaps_txgroup.create_child("Remove Uniswap Liquidity", uniswap.is_uniswap_withdrawal)
swaps_txgroup.create_child("Uniswap Swap", uniswap.is_uniswap_swap)

swaps_txgroup.create_child("Compound Deposit", compound.is_compound_deposit)
swaps_txgroup.create_child("Compound Withdrawal", compound.is_compound_withdrawal)

swaps_txgroup.create_child("Aave Deposit", aave.is_aave_deposit)
swaps_txgroup.create_child("Aave Withdrawal", aave.is_aave_withdrawal)

swaps_txgroup.create_child("Synthetix Swap", synthetix.is_synthetix_swap)

if chain.id == Network.Mainnet:
    swaps_txgroup.create_child("ySwaps Swap", cowswap.is_cowswap_swap)
    swaps_txgroup.create_child("YLA", yla.is_yla_withdrawal)
    swaps_txgroup.create_child("Unwrapper", unwrapper.is_unwrapper)
elif chain.id == Network.Fantom:
    swaps_txgroup.create_child("Reaper Vault Withdrawl", robovault.is_reaper_withdrawal)

staking_txgroup = ignore_txgroup.create_child("Staking")
staking_txgroup.create_child("Curve Gauges", staking.is_curve_gauge)
if chain.id == Network.Fantom:
    staking_txgroup.create_child("Solidex", staking.is_solidex_staking)

buying_yfi_txgroup = swaps_txgroup.create_child("Buying YFI")
buying_yfi_txgroup.create_child("OTC", HashMatcher(buying_yfi.otc_hashes).contains)
buying_yfi_txgroup.create_child("Swap", HashMatcher(buying_yfi.non_otc_hashes).contains)
buying_yfi_txgroup.create_child("Top-up Buyer Contract", buying_yfi.is_buyer_top_up)
buying_yfi_txgroup.create_child("Buyer Contract", buying_yfi.is_buying_with_buyer)
