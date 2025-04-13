
from y.constants import CHAINID
from y.networks import Network

from yearn.treasury.accountant.classes import TopLevelTxGroup
from yearn.treasury.accountant.revenue import (bribes, dinobots, farming, fees,
                                               keepcoins, seasolver, yteams)

REVENUE_LABEL = "Protocol Revenue"
revenue_txgroup = TopLevelTxGroup(REVENUE_LABEL)

fees_txgroup = revenue_txgroup.create_child("Fees")
if CHAINID == Network.Mainnet:
    fees_txgroup.create_child("Vaults V1", fees.is_fees_v1)
fees_txgroup.create_child("Vaults V2", fees.is_fees_v2)
#fees_txgroup.create_child("Factory Vaults V2", fees.is_factory_fees_v2)
fees_txgroup.create_child("Vaults V3", fees.is_fees_v3)

fees_txgroup.create_child("YearnFed Fees", fees.is_yearn_fed_fees)
fees_txgroup.create_child("DOLAFRAXBP Fees", fees.is_dolafraxbp_fees)
fees_txgroup.create_child("TempleDAO Private Vault Fees", fees.is_temple)

seasolver_txgroup = revenue_txgroup.create_child("SeaSolver")
seasolver_txgroup.create_child("Positive Slippage", seasolver.is_seasolver_slippage_revenue)
seasolver_txgroup.create_child("CowSwap Incentives", seasolver.is_cowswap_incentive)

dinobots_txgroup = revenue_txgroup.create_child("Dinobots", dinobots.is_dinobots_rev)

bribes_txgroup = revenue_txgroup.create_child("Bribes")
bribes_txgroup.create_child("yCRV Bribes", check=bribes.is_ycrv_bribe)
bribes_txgroup.create_child("yBribe Fees", check=bribes.is_ybribe_fees)

keepcoins_txgroup = revenue_txgroup.create_child("keepCOINS")
# keepCRV is not included here as all of the CRV from keepCRV are locked in yveCRV-DAO
if CHAINID == Network.Mainnet:
    keepcoins_txgroup.create_child("KeepANGLE", keepcoins.is_keep_angle)
    keepcoins_txgroup.create_child("KeepBAL", keepcoins.is_keep_bal)
    keepcoins_txgroup.create_child("KeepPOOL", keepcoins.is_keep_pool)
elif CHAINID == Network.Fantom:
    keepcoins_txgroup.create_child("KeepBEETS", keepcoins.is_keep_beets)

farming_txgroup = revenue_txgroup.create_child("Treasury Farming")
if CHAINID == Network.Mainnet:
    farming_txgroup.create_child("COMP Farming", farming.is_comp_rewards)
elif CHAINID == Network.Fantom:
    farming_txgroup.create_child("SCREAM Farming", farming.is_scream_rewards)
    farming_txgroup.create_child("SOLID Farming", farming.is_solid)
    farming_txgroup.create_child("SEX Farming", farming.is_sex)
    farming_txgroup.create_child("SOLIDsex Farming", farming.is_solidsex)

if CHAINID == Network.Mainnet:
    revenue_txgroup.create_child("yTeam Rev Share", yteams.is_yteam_rev_share)
