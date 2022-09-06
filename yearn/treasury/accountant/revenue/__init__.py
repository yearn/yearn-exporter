
from brownie import chain
from yearn.networks import Network
from yearn.treasury.accountant.classes import TopLevelTxGroup
from yearn.treasury.accountant.revenue import farming, fees, keepcoins

REVENUE_LABEL = "Protocol Revenue"
revenue_txgroup = TopLevelTxGroup(REVENUE_LABEL)

fees_txgroup = revenue_txgroup.create_child("Fees")
fees_txgroup.create_child("Vaults V1", fees.is_fees_v1)
fees_txgroup.create_child("Vaults V2", fees.is_fees_v2)
fees_txgroup.create_child("Vaults V3", fees.is_fees_v3)

fees_txgroup.create_child("YearnFed Fees", fees.is_yearn_fed_fees)
fees_txgroup.create_child("TempleDAO Private Vault Fees", fees.is_temple)


keepcoins_txgroup = revenue_txgroup.create_child("keepCOINS")
# keepCRV is not included here as all of the CRV from keepCRV are locked in yveCRV-DAO
if chain.id == Network.Mainnet:
    keepcoins_txgroup.create_child("KeepANGLE", keepcoins.is_keep_angle)
    keepcoins_txgroup.create_child("KeepBAL", keepcoins.is_keep_bal)
    keepcoins_txgroup.create_child("KeepPOOL", keepcoins.is_keep_pool)
elif chain.id == Network.Fantom:
    keepcoins_txgroup.create_child("KeepBEETS", keepcoins.is_keep_beets)

farming_txgroup = revenue_txgroup.create_child("Treasury Farming")
if chain.id == Network.Mainnet:
    farming_txgroup.create_child("COMP Farming", farming.is_comp_rewards)
elif chain.id == Network.Fantom:
    farming_txgroup.create_child("SCREAM Farming", farming.is_scream_rewards)
    farming_txgroup.create_child("SOLID Farming", farming.is_solid)
    farming_txgroup.create_child("SEX Farming", farming.is_sex)
    farming_txgroup.create_child("SOLIDsex Farming", farming.is_solidsex)
