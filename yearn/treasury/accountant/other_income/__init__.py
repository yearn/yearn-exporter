from y import Network
from y.constants import CHAINID

from yearn.treasury.accountant.classes import TopLevelTxGroup
from yearn.treasury.accountant.other_income import (airdrop, atoken, dust,
                                                    other, robovault)

OTHER_INCOME_LABEL = "Other Income"

other_income_txgroup = TopLevelTxGroup(OTHER_INCOME_LABEL)

other_income_txgroup.create_child("Airdrop", airdrop.is_airdrop)
if CHAINID == Network.Mainnet:
    other_income_txgroup.create_child("Tessaract Refund", other.is_tessaract_refund)
    other_income_txgroup.create_child("Portals Fees", other.is_portals_fees)
    other_income_txgroup.create_child("Lido Grant", other.is_lido_grant)
    other_income_txgroup.create_child("Cowswap Gas Reimbursement", other.is_cowswap_gas_reimbursement)
    other_income_txgroup.create_child("yvUSDN Shutdown", other.is_usdn_shutdown)
    other_income_txgroup.create_child("USDS Referral Code", other.is_usds_referral_code)
    other_income_txgroup.create_child("Other", other.is_other)
    other_income_txgroup.create_child("aToken Yield", atoken.is_atoken_yield)
    other_income_txgroup.create_child("yETH Application Fee", other.is_yeth_application_fee)
elif CHAINID == Network.Fantom:
    other_income_txgroup.create_child("RoboVault Thank You", robovault.is_robovault_share)
    other_income_txgroup.create_child("Dust from Positive Slippage", dust.is_dust_from_positive_slippage)
