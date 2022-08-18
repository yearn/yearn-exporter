
from brownie import chain
from yearn.networks import Network
from yearn.treasury.accountant.classes import Filter, HashMatcher, TopLevelTxGroup
from yearn.treasury.accountant.expenses import (general, infrastructure,
                                                people, security)

OPEX_LABEL = "Operating Expenses"

expenses_txgroup = TopLevelTxGroup(OPEX_LABEL)

if chain.id == Network.Mainnet:
    team = expenses_txgroup.create_child("Team Payments", people.is_team_payment)
    team.create_child("Replenish Streams", people.is_stream_replenishment)

    expenses_txgroup.create_child("Coordinape", people.is_coordinape)
    expenses_txgroup.create_child("The 0.03%", people.is_0_03_percent)
    expenses_txgroup.create_child("SMS Discretionary Budget", general.is_sms_discretionary_budget)
    expenses_txgroup.create_child("Travel Reimbursements", general.is_travel_reimbursement)

    security_txgroup = expenses_txgroup.create_child("Security")
    security_txgroup.create_child("Bug Bounty", security.is_bug_bounty)
    security_txgroup.create_child("Anti-Spam Discord Bot", security.is_antispam_bot)
    audit_txgroup = security_txgroup.create_child("Audit")
    audit_txgroup.create_child("yAcademy", security.is_yacademy_audit)
    audit_txgroup.create_child("ChaiSec", security.is_chaisec_audit)
    audit_txgroup.create_child("StateMind", security.is_statemind_audit)
    audit_txgroup.create_child("Unspecified Audit", security.is_other_audit)


    grants = expenses_txgroup.create_child("Grants")

    brand = grants.create_child("Brand Identity", HashMatcher(general.hashes['brand identity']).contains)
    design = grants.create_child("Design", HashMatcher(general.hashes["design"]).contains)
    
    website = grants.create_child("Website")
    ux = website.create_child("UX")
    testing = ux.create_child("Testing", HashMatcher(general.hashes["website"]["ux"]["testing"]).contains)

    grants.create_child("Vault Management Dashboard", HashMatcher(["0xc59b692bff01c3a364d9a1fc629dfd743c1e421f7eaee7efdca86f23d0a8a7ad"]).contains) # These is also a stream for these guys TODO figure out how to account for streams as they stream
    grants.create_child("V3 Support", HashMatcher([["0x213979422ec4154eb0aa0db4b03f48e1669c08fa055ab44e4006fa7d90bb8547", Filter('log_index', 534)]]).contains) # These is also a stream for these guys TODO figure out how to account for streams as they stream
    grants.create_child("Frontend Support", people.is_frontend_support)
    grants.create_child("yGift Team Grant", people.is_ygift_grant)
    grants.create_child("Other Grants", people.is_other_grant)
    grants.create_child("2021 Bonus", HashMatcher(people.eoy_bonus_hashes).contains)

    infrastructure_txgroup = expenses_txgroup.create_child("Infrastructure")
    infrastructure_txgroup.create_child("Server Costs", infrastructure.is_servers)
    infrastructure_txgroup.create_child("Tenderly Subscription", infrastructure.is_tenderly)
    infrastructure_txgroup.create_child("Unspecified Infra", infrastructure.is_generic)
