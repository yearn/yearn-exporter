
from y.constants import CHAINID
from y.networks import Network

from yearn.treasury.accountant.classes import TopLevelTxGroup
from yearn.treasury.accountant.other_expenses import boost, bugs, general, revshare

OTHER_EXPENSE_LABEL = "Other Operating Expense"

other_expense_txgroup = TopLevelTxGroup(OTHER_EXPENSE_LABEL)

if CHAINID == Network.Mainnet:
    other_expense_txgroup.create_child("yAcademy Fellows Grant", general.is_yacademy_fellow_grant)
    other_expense_txgroup.create_child("Strategists' Buyout", general.is_strategist_buyout)
    other_expense_txgroup.create_child("Gitcoin Donation for Matching", general.is_gitcoin_matching_donation)
    other_expense_txgroup.create_child("YFI Story", general.is_yfi_story)
    other_expense_txgroup.create_child("Aztek Gas Subsidy", general.is_aztek_gas_subsidy)
    other_expense_txgroup.create_child("Devcon Event", general.is_devcon_event)
    other_expense_txgroup.create_child("EthGlobal", general.is_eth_global)
    other_expense_txgroup.create_child("veYFI Gas Subsidy", general.is_veyfi_gas)
    other_expense_txgroup.create_child("1 YFI for Signers", general.one_yfi_for_signers)
    other_expense_txgroup.create_child("Vesting Packages", general.is_vesting_packages)
    other_expense_txgroup.create_child("Strategist Buyout", general.is_strategist_buyout)
    other_expense_txgroup.create_child("New Stream Gas Subsidy", general.is_new_stream_gas_subsidy)
    other_expense_txgroup.create_child("Fix Temple Migration", general.is_fix_temple_migration)
    other_expense_txgroup.create_child("yChute", general.is_ychute)
    other_expense_txgroup.create_child("EthOnline Prizes", general.is_eth_online_prizes)
    other_expense_txgroup.create_child("4626 Alliance Grant", general.is_4626_alliance)
    other_expense_txgroup.create_child("yETH Bootstrap", general.is_yeth_bootstrap)
    other_expense_txgroup.create_child("Warroom Games 2023 Prizes", general.is_warroom_games)
    other_expense_txgroup.create_child("yfi.eth", general.is_yfi_dot_eth)
    other_expense_txgroup.create_child("Fund Vyper Compiler Audit Context", general.is_yyper_contest)
    other_expense_txgroup.create_child("Reimburse yETH Applications", general.is_reimburse_yeth_applications)
    other_expense_txgroup.create_child("dYFI Launch", general.is_dyfi_launch)
    other_expense_txgroup.create_child("dYFI Redemptions", general.is_dyfi_redemptions)
    other_expense_txgroup.create_child("veYFI Launch", general.is_veyfi_launch)
    other_expense_txgroup.create_child("Vyper Donation", general.is_vyper_donation)
    other_expense_txgroup.create_child("Unknown", general.is_unknown)
    other_expense_txgroup.create_child("yBudget Reward", general.is_ybudget_reward)
    other_expense_txgroup.create_child("EthDenver", general.is_eth_denver)
    other_expense_txgroup.create_child("Buying CRV For Boosties", boost.is_buying_crv_for_boost)

# Bugs
if CHAINID == Network.Mainnet:
    bug_reimbursements_txgroup = other_expense_txgroup.create_child("Bug Reimbursements")

    bug_reimbursements_txgroup.create_child("yDAI Fee Calculation Bug", bugs.is_double_fee_reimbursement)
    bug_reimbursements_txgroup.create_child("yDAI Fee Calculation Bug", bugs.is_ydai_fee_reimbursement)
    bug_reimbursements_txgroup.create_child("yYFI Fee Calculation Bug", bugs.is_yyfi_fee_reimbursement)
    bug_reimbursements_txgroup.create_child("yvCurve-IB Fee Calculation Bug", bugs.is_lossy_fee_reimbursement)
    bug_reimbursements_txgroup.create_child("Reimburse st-yCRV User", bugs.is_stycrv)
    bug_reimbursements_txgroup.create_child("Slippage Bug", bugs.is_slippage_bug_reimbursement)
    bug_reimbursements_txgroup.create_child("Reimburse Opti Zap Bug", bugs.is_opti_zap_bug)
    bug_reimbursements_txgroup.create_child("Reimburse Discord Link Bug", bugs.is_reimburse_discord_link_bug)
    bug_reimbursements_txgroup.create_child("Reimburse GUSD Vault Bug", bugs.is_gusd_vault_bug_reimbursement)
    bug_reimbursements_txgroup.create_child("Reimburse DAI Vault Bug", bugs.is_dai_vault_reimbursement)

if CHAINID == Network.Mainnet:
    revshare_txgroup = other_expense_txgroup.create_child("Revshare")

    revshare_txgroup.create_child("yAudit Revshare", revshare.is_yaudit_revshare)
    revshare_txgroup.create_child("yLockers Revshare", revshare.is_ylockers_revshare)