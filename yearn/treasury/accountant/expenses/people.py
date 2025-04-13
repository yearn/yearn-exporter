
from contextlib import suppress
from typing import Iterator, List, Optional

from brownie import convert
from dank_mids.helpers import lru_cache_lite
from msgspec import UNSET, Struct
from pony.orm import commit
from y import Address, Contract

from yearn.constants import YFI
from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import _FROM_DISPERSE_APP, Filter, HashMatcher, IterFilter


# TODO: add rejected BRs
_budget_requests = {}

class BudgetRequest(Struct):
    number: int = 0
    dai: Optional[float] = UNSET
    yfi: Optional[float] = UNSET
    usdc: Optional[float] = UNSET
    
    def __post_init__(self) -> None:
        if self.number:
            _budget_requests[self.number] = self
    
    def __contains__(self, symbol: str) -> bool:
        """Returns True if there is a portion of comp denominated in token `symbol` for this BR, False otherwise."""
        return hasattr(self, symbol.lower()) and getattr(self, symbol.lower()) != UNSET

    def __getitem__(self, symbol: str) -> float:
        with suppress(AttributeError):
            retval = getattr(self, symbol.lower())
            if retval != UNSET:
                return retval
        raise KeyError(symbol)
    
    @property
    def url(self) -> str:
        if not self.number:
            raise ValueError(f"{self}.no is unassigned")
        return f"https://github.com/yearn/budget/issues/{self.number}"


TransactionHash = str

@lru_cache_lite
def get_scale(token: Address):
    token = Contract(token)
    return 10**token.decimals()

@lru_cache_lite
def get_symbol(token: Contract):
    return token.symbol()

def is_v2(token: Contract) -> bool:
    return hasattr(token, 'token')

def is_v3(token: Contract) -> bool:
    return hasattr(token, 'asset')

def get_underlying(token: Contract) -> Contract:
    if is_v3(token):
        return Contract(token.asset())
    elif is_v2(token):
        return Contract(token.token())

class yTeam(Struct):
    label: str
    address: str
    brs: List[BudgetRequest] = []
    refunds: List[TransactionHash] = []
    """If a team sent funds back for any reason put the hash here"""
    
    def __post_init__(self) -> None:
        self.address = convert.to_address(self.address)
    
    @property
    def txgroup_name(self) -> str:
        # TODO: BR numbers
        return f"{self.label} [BR#xxx]"

    def brs_for_token(self, symbol: str) -> Iterator[BudgetRequest]:
        for br in self.brs:
            if symbol in br:
                yield br
        
    def is_team_comp(self, tx: TreasuryTx) -> bool:
        if tx.to_address == self.address:
            # TODO: build hueristics for this if it keeps happening
            if tx.hash == "0xa113223ee1cb2165b4cc01ff0cea0b98b94e3f93eec57b117ecfbac5eea47916":
                return True
            elif (brs_for_token := list(self.brs_for_token(tx._symbol))):
                return any(float(tx.amount) == br[tx._symbol] for br in brs_for_token)
        elif self.refunds and tx.from_address == self.address and tx in HashMatcher(self.refunds):
            if tx.amount > 0:
                tx.amount *= -1
            if tx.value_usd > 0:
                tx.value_usd *= -1
            return True
        return self.is_team_vest(tx)

    def is_team_vest(self, tx: TreasuryTx) -> bool:
        "checks for vesting contracts deployed via 0x200C92Dd85730872Ab6A1e7d5E40A067066257cF"

        if "VestingEscrowCreated" not in tx._events:
            return False
        
        for vest in tx._events["VestingEscrowCreated"]:
            if vest.address == "0x200C92Dd85730872Ab6A1e7d5E40A067066257cF":
                funder, token, recipient, escrow, amount, *_ = vest.values()
                if not (
                    tx.from_address == funder
                    and recipient == self.address 
                    and tx.to_address == escrow
                    and tx.token == token
                ):
                    continue
            elif vest.address == "0x850De8D7d65A7b7D5bc825ba29543f41B8E8aFd2":
                # YFI Liquid Locker Vesting Escrow Factory
                token = "0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e"  # YFI
                funder, recipient, index, amount, *_ = vest.values()
                print(f"funder: {funder}")
                print(f"recipient: {recipient}")
                print(f"amount: {amount}")
                if not (
                    tx.from_address == funder
                    and recipient == self.address
                    and tx.token == token
                ):
                    continue
            else:
                continue

            if tx.amount != amount / get_scale(token):
                continue

            # token sent raw
            if any(float(tx.amount) == br[tx._symbol] for br in self.brs_for_token(tx._symbol)):
                return True
            
            token = Contract(token)
            underlying = get_underlying(token)
            
            if is_v3(token):
                underlying_amount = token.convertToAssets(amount, block_identifier=tx.block) / get_scale(underlying)
            elif is_v2(token):
                underlying_amount = amount * token.pricePerShare(block_identifier=tx.block) / get_scale(underlying)
            else:
                return False
            
            print(f"token: {token}")
            symbol = get_symbol(token)
            underlying_amount = float(underlying_amount)
            for br in self.brs_for_token(symbol):
                # TODO: should we debug this rounding? I think its fine
                if underlying_amount * 0.999 <= br[symbol] <= underlying_amount * 1.001:
                    return True
        return False


# TODO: add BR numbers
yteams = [
    yTeam(
        "V3 Development", 
        "0x3333333368A1ed686392C1534e747F3e15CA286C", 
        brs=[
            BudgetRequest(dai=35_000, yfi=1.5),
            # 2nd request
            BudgetRequest(dai=40_000, yfi=1.5),
            # extra fundus # TODO: figure out a better way to handle these
            BudgetRequest(dai=25_000),
            BudgetRequest(usdc=65_000),
        ]
    ),
    yTeam("V3 Development", "0x33333333D5eFb92f19a5F94a43456b3cec2797AE", brs=[BudgetRequest(200, dai=120_000), BudgetRequest(222, dai=105_000)], refunds=["0xf0410c1eaf2048a9d5472151cf733be41ba9c995d0825bb5d1629f9062a16f85"]),
    yTeam("S2 Team", "0x00520049162aa47AdA264E2f77DA6749dfaa6218", brs=[BudgetRequest(dai=39_500, yfi=2.25)]),
    yTeam("yCreative", "0x402449F51afbFC864D44133A975980179C6cD24C", brs=[BudgetRequest(dai=15_500, yfi=1.65), BudgetRequest(dai=46_500, yfi=4.95)]),
    yTeam("Corn", "0xF6411852b105042bb8bbc6Dd50C0e8F30Af63337", brs=[BudgetRequest(dai=10_000, yfi=1.5), BudgetRequest(dai=30_000, yfi=4.5)]),
    # NOTE: can I do this double? 
    yTeam("Corn", "0x8973B848775a87a0D5bcf262C555859b87E6F7dA", brs=[BudgetRequest(199, usdc=60_000), BudgetRequest(221, dai=60_000)]),
    yTeam("ySecurity", "0x4851C7C7163bdF04A22C9e12Ab77e184a5dB8F0E", brs=[BudgetRequest(dai=20_667, yfi=2.5)]),
    yTeam("Zootroop", "0xBd5CA40C66226F53378AE06bc71784CAd6016087", brs=[BudgetRequest(dai=34_500, yfi=1.5), BudgetRequest(dai=36_500, yfi=2), BudgetRequest(202, dai=172_500), BudgetRequest(224, dai=162_000)]),
    yTeam("yETH", "0xeEEEEeeeEe274C3CCe13f77C85d8eBd9F7fd4479", brs=[BudgetRequest(dai=20_000, yfi=4.5)]),
    yTeam("yLockers", "0xAAAA00079535300dDba84A89eb92434250f83ea7", brs=[BudgetRequest(dai=20_600, yfi=2), BudgetRequest(dai=60_500, yfi=6)], refunds=["0xa9613960b6c657b3ebc67798b5bb4b3b51c5d4b3bbbde2eb8f6a61a9ab4657c4"]),
    yTeam("yLockers", "0x4444AAAACDBa5580282365e25b16309Bd770ce4a", brs=[BudgetRequest(195, dai=35_000), BudgetRequest(205, dai=35_000), BudgetRequest(206, dai=90_840), BudgetRequest(226, dai=120_840)]),
    yTeam("yDiscount", "0x54991866A907891c9B85478CC1Fb0560B17D2b1D", brs=[BudgetRequest(yfi=1)]),
    yTeam("Dudesahn", "0x4444AAAACDBa5580282365e25b16309Bd770ce4a", brs=[BudgetRequest(179, dai=15_000), BudgetRequest(196, dai=15_000)]),
    # NOTE: not sure if this works with the existing ySupport matcher... lets see...
    # NOTE: it does not. do some refactoring here
    yTeam(
        "ySupport", 
        "0xbd7B3Bc2C4581Fd173362c830AE45fB9506B3dA5", 
        brs=[
            BudgetRequest(yfi=1.14), 
            BudgetRequest(194, dai=18_375),
            BudgetRequest(212, dai=24_000),
            # This was 1 br in 2 pmts
            BudgetRequest(dai=2_000),
            BudgetRequest(dai=4_000),
            # These were actually the same BR but one payment got rounded
            BudgetRequest(yfi=0.92307692),
            BudgetRequest(yfi=0.923077),
        ],
    ),
    yTeam("1Up", "0x572b0675b0A815d1970C1310fE4AA8884FEaaaCc", brs=[BudgetRequest(yfi=42)]),
    yTeam("Korin", "0x66bDEfA7Abf210d1240C9EC00000AafcFc80a235", brs=[BudgetRequest(yfi=40)]),
    yTeam("Schlag", "0x88a3354e5e7A34A7901e1b64557992E85Aa1B5eb", brs=[BudgetRequest(yfi=40)]),
    yTeam("DevDocs", "0x88c868B1024ECAefDc648eb152e91C57DeA984d0", brs=[BudgetRequest(204, dai=7_500, yfi=0.3), BudgetRequest(223, dai=21_900, yfi=1.2)]),
    yTeam("Tapir", "0x80c9aC867b2D36B7e8D74646E074c460a008C0cb", brs=[BudgetRequest(217, dai=36_000)]),
    yTeam("yRoboTreasury", "0xABCDEF0028B6Cc3539C2397aCab017519f8744c8", brs=[BudgetRequest(215, 30_000)]),
    yTeam("yReporting", "0x28eD70032Adc7575d45A0869CfDcCEcdE88C1a74", brs=[BudgetRequest(dai=63_000)]),
    yTeam("CatHerder", "0x63E02F93622541CfE41aFedCF96a114DB71Ba4EE", brs=[BudgetRequest(213, dai=30_000)]),
    yTeam("MOM", "0x789330A9F15bbC61B524714528C1cE72237dC731", brs=[BudgetRequest(225, dai=365_250)]),
    yTeam("SAM", "0xe5e2Baf96198c56380dDD5E992D7d1ADa0e989c0", brs=[BudgetRequest(218, dai=78_000)]),
    yTeam("veYFI", "0x555555550955A916D9bF6DbCeA0e874cDfE77c70", brs=[BudgetRequest(220, dai=10_000)])
]

# old
# TODO refactor all of this
def is_team_payment(tx: TreasuryTx) -> bool:
    hashes = (
        "0x0704961379ad0ee362c9a2dfd22fdfa7d9a2ed5a94a99dbae1f83853a2d597bc",
        "0x78f39093239242c68f77dee8912546189adf2447264e8340d3a4982b9474a159",
        ("0x3249dac3b85f6dd9e268b4440322b2e437237d6b8a264286bd6fe97575804b00", IterFilter('log_index', (249,251,255,257,259,263,265))),
        ("0x38dbe0e943d978483439d4dec9e29f71fc4690e790261661ef3b2d179dee26b9", Filter('log_index', 165)),
        "0x53fbd564acf39e0694773b5228d31d32623aa249b73a9989a2a43d8b7b8484af",
    )

    disperse_app_hashes = (
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
    )

    if tx.hash == '0x91656eb3246a560498e808cbfb00af0518ec12f50effda42fc1496d0b0fb080a' and tx.log_index == 421:
        return False

    zerox_splits_hashes = (
        "0x38dbe0e943d978483439d4dec9e29f71fc4690e790261661ef3b2d179dee26b9",
    )

    if tx in HashMatcher(hashes):
        return True
    elif tx._from_nickname == 'Disperse.app' and tx in HashMatcher(disperse_app_hashes):
        return True
    elif tx._to_nickname == "Non-Verified Contract: 0x426eF4C1d57b4772BcBE23979f4bbb236c135e1C" and tx in HashMatcher(zerox_splits_hashes):
        return True
    return False


_COORDINAPE_HASHES = HashMatcher((
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
))

_COORDINAPE_HASHES_2 = HashMatcher(("0xfd83d667c278a74f0ad9507b8d159e43f893c5067dbd47c05c80e229ec6c3cd4"))

def is_coordinape(tx: TreasuryTx) -> bool:
    if tx._from_nickname == "Disperse.app" and tx._symbol in ("YFI", "yvYFI") and tx in _COORDINAPE_HASHES:
        return True
    return tx in _COORDINAPE_HASHES_2

def is_ygift_grant(tx: TreasuryTx) -> bool:
    """ Yearn used to use yGift to send team grants but that ended up being too expensive. """
    return tx._to_nickname == "Contract: yGift" and tx._symbol == "yyDAI+yUSDC+yUSDT+yTUSD"

def is_frontend_support(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([
        ["0x213979422ec4154eb0aa0db4b03f48e1669c08fa055ab44e4006fa7d90bb8547", IterFilter('log_index', [535,536])],
        ["0x57bc99f6007989606bdd9d1adf91c99d198de51f61d29689ee13ccf440b244df", Filter('log_index', 80)],
        "0x9323935229a0f1fcbfbd95da7eea5eb7fe151da8ac62a21e9f38b29d5abde044",
        ["0xf7244399cbea44a32e3e5a40f9c4f42836eca4035a710af549a76c4c9ade234e", IterFilter('log_index', [218, 219, 220])],
        ["0x996b5911a48319133f50f72904e70ed905c08c81e2c03770e0ccc896be873bd4", IterFilter('log_index', [257, 258, 259])],
        ["0x7afceac28536b9b2c177302c3cfcba449e408b47ff2f0a8a3c4b0e668a4d5d4e", IterFilter('log_index', [31, 32, 33])],
    ])

def is_ydaemon_grant(tx: TreasuryTx) -> bool:
    return tx in HashMatcher([["0x996b5911a48319133f50f72904e70ed905c08c81e2c03770e0ccc896be873bd4", Filter('log_index', 260)]])

def is_other_grant(tx: TreasuryTx) -> bool:
    hashes = [
        "0x34714d6056c44b907fb28eec3638b58f57178dbde180d4019d04447ef2f780da",
        ["0x57fd81a0a665324558ae91a927097e44febd89972136165f3ec6cd4d6f8bc749", IterFilter('log_index', [157,159,160,161])],
        ["0x3baa6dd5f5db014e04af9d73dc4fa83d54f9803a5cc32140801fe2571e866831", _FROM_DISPERSE_APP],
        ["0x3249dac3b85f6dd9e268b4440322b2e437237d6b8a264286bd6fe97575804b00", IterFilter('log_index', [243,245,247,253,261,267,269,271,273,275,277])],
        # "May 2022 grant" ?
        ["0xca372ad75b957bfce7e7fbca879399f46f923f9ca17299e310150da8666703b9", Filter('log_index', 515)],
        ["0x9681276a8668f5870551908fc17be3553c82cf6a9fedbd2fdb43f1c05385dca1", Filter('log_index', 181)],
        "0xa96246a18846cd6966fc87571313a2021d8e1e38466132e2b7fe79acbbd2c589",
        ["0x47bcb48367b5c724780b40a19eed7ba4f623de619e98c30807f52be934d28faf", Filter('_symbol', "DAI")],
        ["0xa0aa1d29e11589350db4df09adc496102a1d9db8a778fc7108d2fb99fb40b6d0", IterFilter("log_index", [391, 394])],
        "0xf8fe392a865b36b908bd8a4247d7d40a3d8cfef13da9e8bc657aee46bd82f9dd",
        ["0xfc07ee04d44f8e481f58339b7b8c998d454e4ec427b8021c4e453c8eeee6a9b9", Filter('_symbol', "ETH")],
        ["0xfc07ee04d44f8e481f58339b7b8c998d454e4ec427b8021c4e453c8eeee6a9b9", Filter('log_index', 218)],
        ["0x925d77f797779f087a44b2e871160fb194f9cdf949019b5c3c3617f86a0d97fb", IterFilter('log_index', [150, 151])],
        "0x4bda2a3b21ff999a2ef1cbbaffaa21a713293f8e175adcc4d67e862f0717d6ef",
    ]
    
    if tx._from_nickname == "Disperse.app":
        disperse_hashes = [
            "0x1e411c81fc83abfe260f58072c74bfa91e38e27e0066da07ea06f75d9c8f4a00",
            "0xfb2cd663228bb3823445b11e05c4b38b2fcd333230facdb388d403a9d1d8c869",
        ]
        return tx in HashMatcher(disperse_hashes)
    if tx in HashMatcher(hashes):
        return True
    
    # Grant overages reimbursed to yearn
    if tx in HashMatcher([
        "0xbe856983c92200982e5fce3b362c91805886422ae858391802a613dc329e7c9b",
        "0xf63d61ae6508d9b44e3dca4edf35282ef88341b76229b0dfa121bdc0dd095457",
        "0xd9f528e15a93cfacfbcaacbfe01110083fc7d7787e94d4cae4c09b174eef543f",
        "0xa1c1635bdd4786361b3cb39322bc78ba4511986fb517f1709ef04c7b3bfa9244",
    ]):
        # Since we want to negate an expense instead of record income, we just multiply amount and value by -1.
        tx.amount *= -1
        tx.value_usd *= -1
        commit()
        return True
    return False

THE_0_03_PERCENT = HashMatcher((("0xe56521d79b0b87425e90c08ed3da5b4fa3329a40fe31597798806db07f68494e", _FROM_DISPERSE_APP)))

eoy_bonus_hashes = (
    "0xcfc2a4e538584c387ac1eca638de783f1839c2a3b0520352828b309564e23dca",
    "0x4a3716b7730ea086e5d9417bc8330808081e74862e0d9d97221a317f68d5ce43",
)

def is_ycrv_grant(tx: TreasuryTx) -> bool:
    return tx in HashMatcher((
        "0x116a44242ffafd12a8e40a7a2dbc9f6a98580ca4d72e626ddb60d09417cab15d",
    ))

IS_DOCS_GRANT = HashMatcher(("0x99f8e351a15e7ce7f0acbae2dea52c56cd93ef97b0a5981f79a68180ff777f00"))
"""https://github.com/yearn/budget/issues/105"""

def is_yearn_exporter(tx: TreasuryTx) -> bool:
    if tx.to_address == "0xcD63C69f08bdDa7Fe96a87A2Ca3f56f3a6990a75":
        if tx._symbol == "YFI" and tx.amount == 2.25:
            return True
        elif tx._symbol == "DAI" and tx.amount == 23_025:
            return True
    if tx.hash == "0x1dc86ccdeb96d8d3d314eb2c1fdad0f4dd11c9ea54dfddedcc9340e71f98aa9e":
        tx.amount *= -1
        return True        
    return False

def is_xopowo(tx: TreasuryTx) -> bool:
    if tx.to_address == "0x4F909396A75FE9d59F584156A851B3770f3F438a":
        if tx._symbol == "YFI":
            return float(tx.amount) == 5.1 or tx in HashMatcher([
                # usual amount chunked in two parts
                "0x699887b634006c45a5a0ccd66cdc0f5396e82635dd17e7e4e0934014d454d81c",
                "0xfc07ee04d44f8e481f58339b7b8c998d454e4ec427b8021c4e453c8eeee6a9b9",
            ])
        elif tx._symbol == "DAI" and tx.amount == 71_500:
            return True
    return False


# TODO: Refactor this whole thing

def is_tapir(tx: TreasuryTx) -> bool:
    return tx.to_address == "0x80c9aC867b2D36B7e8D74646E074c460a008C0cb" and tx._symbol == "DAI" and tx.amount == 4_000

def is_hipsterman(tx: TreasuryTx) -> bool:
    if tx.to_address == "0xE53D3f2B99FE0Ed6C05977bC0547127836f0D78d" and tx._symbol == "DAI" and tx.amount in [3_500, 7000]:
        return True
    elif tx.hash == "0xfe0ce0947c405f22c99eab63f7e529d95eab4274f2c468deaa1da50adaeb4450":
        tx.value_usd *= -1
        return True
    return False

def is_worms(tx: TreasuryTx) -> bool:
    return tx.to_address == "0xB1d693B77232D88a3C9467eD5619FfE79E80BCCc"

def is_ysecurity_2(tx: TreasuryTx) -> bool:
    return tx.to_address == "0x4851C7C7163bdF04A22C9e12Ab77e184a5dB8F0E"

def is_ydiscount(tx: TreasuryTx) -> bool:
    return tx.to_address == "0x54991866A907891c9B85478CC1Fb0560B17D2b1D"

def is_ybudget(tx: TreasuryTx) -> bool:
    return tx.to_address == "0x5E97104F602648aDcB9f75F5F3B852CAc2Dc4576" or tx in HashMatcher((
        ("0xb01305e2d2c34f1da600d64aea79034b63248a76437e30de986445a9347e554f", IterFilter('log_index', range(327, 334))),
    ))

"""# TODO: delete this once we're sure it works
def is_ysupport(tx: TreasuryTx) -> bool:
    '''BR #194 and some earlier stuff'''
    return (
        tx.to_address == "0xbd7B3Bc2C4581Fd173362c830AE45fB9506B3dA5"
        # also include payment to this vest contract for #194
        #or tx.to_address == "0x031a6Ae2a336cc838aab4501B32e5C08fA2b23BB"
    )"""

def is_rantom(tx: TreasuryTx) -> bool:
    return tx.to_address == "0x254b42CaCf7290e72e2C84c0337E36E645784Ce1"

def is_tx_creator(tx: TreasuryTx) -> bool:
    return tx.to_address == "0x4007c53A48DefaB0b9D2F05F34df7bd3088B3299" and tx._symbol == "DAI" and tx.amount == 5_000

def is_dinobots(tx: TreasuryTx) -> bool:
    # NOTE: refactor this out
    if tx.token.symbol == "DAI" and tx._from_nickname == "Yearn yChad Multisig" and tx._to_nickname == "yMechs Multisig" and int(tx.amount) == 47_500:
        return True
    # br 198
    elif tx.hash == "0xb01305e2d2c34f1da600d64aea79034b63248a76437e30de986445a9347e554f" and tx.log_index == 307:
        return True
    # br 214
    elif tx.hash == "0xc269f6fb016a48fe150f689231a73532b631877d1376608df639dad79514904b" and tx.log_index == 349:
        return True
    # br 219?
    elif tx.hash == "0xd7e7abe600aad4a3181a3a410bef2539389579d2ed28f3e75dbbf3a7d8613688" and tx.log_index == 547:
        return True
    # br 249
    elif tx.hash == "0xd55f6cedd7a08d91f99e8ceb384ffd0892f3dbee450879af33d54dda5bd18915" and tx.log_index == 33:
        return True
    return False
