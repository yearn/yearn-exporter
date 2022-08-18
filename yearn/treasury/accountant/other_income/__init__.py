
from brownie import chain
from yearn.networks import Network
from yearn.treasury.accountant.classes import TopLevelTxGroup
from yearn.treasury.accountant.other_income import robovault, dust, other, airdrop


OTHER_INCOME_LABEL = "Other Income"

other_income_txgroup = TopLevelTxGroup(OTHER_INCOME_LABEL)

other_income_txgroup.create_child("Airdrop", airdrop.is_airdrop)
if chain.id == Network.Mainnet:
    other_income_txgroup.create_child("Tessaract Refund", other.is_tessaract_refund)
elif chain.id == Network.Fantom:
    other_income_txgroup.create_child("RoboVault Thank You", robovault.is_robovault_share)
    other_income_txgroup.create_child("Dust from Positive Slippage", dust.is_dust_from_positive_slippage)
