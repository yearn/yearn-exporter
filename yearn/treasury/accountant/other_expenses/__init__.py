
from brownie import chain
from yearn.networks import Network
from yearn.treasury.accountant.classes import TopLevelTxGroup
from yearn.treasury.accountant.other_expenses import bugs, general

OTHER_EXPENSE_LABEL = "Other Operating Expense"

other_expense_txgroup = TopLevelTxGroup(OTHER_EXPENSE_LABEL)

if chain.id == Network.Mainnet:
    other_expense_txgroup.create_child("yAcademy Fellows Grant", general.is_yacademy_fellow_grant)
    other_expense_txgroup.create_child("Strategists' Buyout", general.is_strategist_buyout)
    other_expense_txgroup.create_child("Gitcoin Donation for Matching", general.is_gitcoin_matching_donation)
    other_expense_txgroup.create_child("YFI Story", general.is_yfi_story)

# Bugs
if chain.id == Network.Mainnet:
    bug_reimbursements_txgroup = other_expense_txgroup.create_child("Bug Reimbursements")

    bug_reimbursements_txgroup.create_child("yDAI Fee Calculation Bug", bugs.is_double_fee_reimbursement)
    bug_reimbursements_txgroup.create_child("yDAI Fee Calculation Bug", bugs.is_ydai_fee_reimbursement)
    bug_reimbursements_txgroup.create_child("yYFI Fee Calculation Bug", bugs.is_yyfi_fee_reimbursement)
