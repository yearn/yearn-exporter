

from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import Filter, HashMatcher, IterFilter


def is_team_payment(tx: TreasuryTx) -> bool:
    hashes = [
        "0x0704961379ad0ee362c9a2dfd22fdfa7d9a2ed5a94a99dbae1f83853a2d597bc",
        "0x78f39093239242c68f77dee8912546189adf2447264e8340d3a4982b9474a159",
        ["0x3249dac3b85f6dd9e268b4440322b2e437237d6b8a264286bd6fe97575804b00", IterFilter('log_index', [249,251,255,257,259,263,265])],
        ["0x38dbe0e943d978483439d4dec9e29f71fc4690e790261661ef3b2d179dee26b9", Filter('log_index', 165)],
        "0x53fbd564acf39e0694773b5228d31d32623aa249b73a9989a2a43d8b7b8484af",
    ]

    disperse_app_hashes = [
        '0x4ec75aaff09c386722c50828f7c210aac417d8b36569b158f6b4f8cb83b222c8',
        '0x343e84cf1d870006eea95e49699f0e025909ed99bc8b543a1d108683b8e5c9fe',
        '0xe1790d408e4625a0a907ba3d016d9d0ee4cb1ac291840754879057a5063f83f1',
        '0xb2b9ddd836e6d15cb27230e9d0582c0b58524f869d5a3f7558105bfe7109301a',
        '0x39d4eb8c7ffa495fc7e6c91f23333ea1373fd30fd9e67363194be7453e13824f',
        '0x90194b9939603020090a203916c542fe0aa9cddebfe224e7322eaad2760c5f8e',
        '0x28e0ee2a748a7a6b0431ae8daa1cb96b54405faba4792056a71ffd995faee0b7',
        '0x4fb589aecc969ee0dec6fd3d89fcf72a9b2e33352a28494c0ea318e8bf0c184f',
        '0xa041b3b7ea27b51676f68e1c192364ec1774ac3c0bb6fa9aeb5f1d81178278e8',
        '0xafeff2ad505e000b8c41705d4324f954b5d396a32fc5556a06878938f49b1982',
        '0x0704961379ad0ee362c9a2dfd22fdfa7d9a2ed5a94a99dbae1f83853a2d597bc',
        '0xab20db7cea64bf6c3dcb1a934c9b4911da0f68385e489062a2f2435410be3115',
        '0x236b7816a4ede2a48bf24715d8857f8f4d99e08cd7c50765103d6691e9437969',
        '0x5b1ff4f7990ba9d15a88b638986250e1e21d3555a1710eab7a27ceae64e2119b',
        '0x9d8fc48fe2f552a424fa2e4fa35f2ddbe73eb9f1eae33bb3b7b27466b8dbb62f',
        '0x21db6975146cfe40e0db6db3acd1f061958f0722ebc2b1018a01f00d013a9b05',
    ]

    if tx.hash == '0x91656eb3246a560498e808cbfb00af0518ec12f50effda42fc1496d0b0fb080a' and tx.log_index == 421:
        return False

    llamapay_hashes = [
        "0xd268946b6937df798e965a98b3f9348f7fc8519a2df9ba124210e4ce6c3fecaf",
        "0x9d8fc48fe2f552a424fa2e4fa35f2ddbe73eb9f1eae33bb3b7b27466b8dbb62f",
        "0x7979a77ab8a30bc6cd12e1df92e5ba0478a8907caf6e100317b7968668d0d4a2",
        "0x91656eb3246a560498e808cbfb00af0518ec12f50effda42fc1496d0b0fb080a",
        "0x16c193b8891af35ec811ebe8416f25addc0c4ffe39e074b5820577f1d8be72ec",
    ]

    zerox_splits_hashes = [
        "0x38dbe0e943d978483439d4dec9e29f71fc4690e790261661ef3b2d179dee26b9"
    ]

    if tx in HashMatcher(hashes):
        return True
    elif tx in HashMatcher(disperse_app_hashes) and tx._from_nickname == 'Disperse.app':
        return True
    elif tx in HashMatcher(llamapay_hashes) and tx._to_nickname == "Contract: LlamaPay":
        return True
    elif tx in HashMatcher(zerox_splits_hashes) and tx._to_nickname == "Non-Verified Contract: 0x426eF4C1d57b4772BcBE23979f4bbb236c135e1C":
        return True
    return False

def is_coordinape(tx: TreasuryTx) -> bool:
    hashes = [
        '0x0b7159645e66c3b460efeb3e1e3c32d5e4eb845a2f2230b28b388ad34a36fcc3',
        '0xb23d189ac94acb68d457e5a21b765fd0affd73ac1cd5afbe9fb57db8c3f95c30',
        '0x5cf6a4c70ec2de7cd25a627213344deae28f11ba9814d5cc1b00946f356ed5bf',
        '0x2a7c60bb7dd6c15a6d0351e6a2b9f01e51fa6e7df9d1e5f02a3759640211ee56',
        '0x371b6a601da36382067a20236d41f540fc77dc793d64d24fc1bdbcd2c666db2b',
        '0x514591e6f8dcac50b6deeabce8a819540cc7caecc182c39dfb93280abb34d3d6',
        '0x8226b3705657f34216483f5091f8bd3eeea385a64b6da458eeaff78521596c28',
        '0x38201edb06e8fd3b9aa9d4142594d28cb73768770fdcb68a4da24d8cb0742cfc',
        '0x4d404a04bf46b80721f03ad6b821c6d82312c53331d8e7425fb68100116d8b98',
        '0xa3627513c8c3e838feaf9ab1076be01df11c5be5a83597626950c3ac38124bba',
        '0x0a9e0f2cadb5dc3209bad74ada2fe71f2cbc0e9e2f16a4de1a29ea663e325798',
        '0xb3aab771a5581df5b1c8e6faefedcc88d91b8820c5ae5eaf9c9283014288dda2',
        '0x1391d6de1f0b5469627da1e23ddd0f892bf7d182780bc2fb807b6bf1e2d0acf1',
        '0x8ed57eff8f4a61cd40d109223c5054f87e35a6f0a5c85b65b1a7afe5b6e308da',
        '0xa121fd9717d0fb4ac72a223db638f4e59094547ddee253e5ba011a5bb0c67126',
        '0xf401d432dcaaea39e1b593379d3d63dcdc82f5f694d83b098bb6110eaa19bbde',
    ]

    if tx._from_nickname == "Disperse.app" and tx._symbol in ["YFI", "yvYFI"] and tx in HashMatcher(hashes):
        return True
    
    return tx in HashMatcher(["0xfd83d667c278a74f0ad9507b8d159e43f893c5067dbd47c05c80e229ec6c3cd4"])

def is_ygift_grant(tx: TreasuryTx) -> bool:
    """ Yearn used to use yGift to send team grants but that ended up being too expensive. """
    if tx._to_nickname == "Contract: yGift" and tx._symbol == "yyDAI+yUSDC+yUSDT+yTUSD":
        return True
    return False

def is_frontend_support(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        ["0x213979422ec4154eb0aa0db4b03f48e1669c08fa055ab44e4006fa7d90bb8547", IterFilter('log_index', [535,536])] 
    ])

def is_other_grant(tx: TreasuryTx) -> bool:
    hashes = [
        "0x34714d6056c44b907fb28eec3638b58f57178dbde180d4019d04447ef2f780da",
        ["0x57fd81a0a665324558ae91a927097e44febd89972136165f3ec6cd4d6f8bc749", IterFilter('log_index', [157,159,160,161])],
        ["0x3baa6dd5f5db014e04af9d73dc4fa83d54f9803a5cc32140801fe2571e866831", Filter('_from_nickname', 'Disperse.app')],
        ["0x3249dac3b85f6dd9e268b4440322b2e437237d6b8a264286bd6fe97575804b00", IterFilter('log_index', [243,245,247,253,261,267,269,271,273,275,277])],
        # "May 2022 grant" ?
        ["0xca372ad75b957bfce7e7fbca879399f46f923f9ca17299e310150da8666703b9", Filter('log_index', 515)],
    ]
    disperse_hashes = [
        "0x1e411c81fc83abfe260f58072c74bfa91e38e27e0066da07ea06f75d9c8f4a00",
        "0xfb2cd663228bb3823445b11e05c4b38b2fcd333230facdb388d403a9d1d8c869",
    ]
    if tx._from_nickname == "Disperse.app":
        return tx in HashMatcher(disperse_hashes)
    return tx in HashMatcher(hashes)

def is_stream_replenishment(tx: TreasuryTx) -> bool:
    pass

def is_0_03_percent(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([["0xe56521d79b0b87425e90c08ed3da5b4fa3329a40fe31597798806db07f68494e", Filter('_from_nickname', 'Disperse.app')]])

eoy_bonus_hashes = [
    "0xcfc2a4e538584c387ac1eca638de783f1839c2a3b0520352828b309564e23dca",
    "0x4a3716b7730ea086e5d9417bc8330808081e74862e0d9d97221a317f68d5ce43",
]