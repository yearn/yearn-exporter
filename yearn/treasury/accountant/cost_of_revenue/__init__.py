
from yearn.treasury.accountant.classes import HashMatcher, TopLevelTxGroup
from yearn.treasury.accountant.cost_of_revenue import general, gas


COR_LABEL = "Cost of Revenue"

cost_of_revenue_txgroup = TopLevelTxGroup(COR_LABEL)

cost_of_revenue_txgroup.create_child("Yearn Partners", general.is_partner_fees)

gas_txgroup = cost_of_revenue_txgroup.create_child("Gas")
gas_txgroup.create_child("Strategists", gas.is_strategist_gas)
gas_txgroup.create_child("TheGraph", HashMatcher(general.hashes.get('thegraph',[])).contains)
gas_txgroup.create_child("yChad", HashMatcher(general.hashes.get('ychad',[])).contains)
gas_txgroup.create_child("yMechs", HashMatcher(general.hashes.get('ymechs',[])).contains)
gas_txgroup.create_child("yKeeper", HashMatcher(general.hashes.get('ykeeper',[])).contains)
gas_txgroup.create_child("YearnHarvest", gas.is_yearn_harvest)
gas_txgroup.create_child("Other Gas", gas.is_other_gas)
multisig_txgroup = gas_txgroup.create_child("Multisig Reimbursement", gas.is_multisig_reimbursement)
multisig_txgroup.create_child("ySwap Signers", HashMatcher(general.hashes.get('yswap',[])).contains)

