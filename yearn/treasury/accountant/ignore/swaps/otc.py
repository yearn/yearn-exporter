
from y import Network
from y.constants import CHAINID

from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import HashMatcher, IterFilter


def is_otc(tx: TreasuryTx) -> bool:
    return CHAINID == Network.Mainnet and tx in _OTC_HASHES

_OTC_HASHES = HashMatcher(
    (
        "0xd59dfba383c0a7d5f0e30124888fa6d9c2c964755fb9bed8f22483feb292c1e9",
        "0xa00430b408c75dc432fcc0bbcabc5c3c63196addab532eecd233f6e80b295990",

        "0x3419d8378321b5cb59c69584693ef59a65aeee4591e7e96c31f31906bc9a627a",
        "0x30afed767aafd21696242c6a54576afc6598e976b969ffe50591360c729ef35a",

        # Emergency dump of yvUSDN
        "0xb22e345f58d7fe40257e41bac5d59ca74af8f6cc1e220aedf6f97113e4ace53a",
        "0xd6bcaf0f144201d5c6affd73746ae57a262dbf00b957534a7b22bc0473bd589b",

        # deprecated vault tokens
        "0xf60060f25ae9f7d377741cde14d374a665dc8f1bff44f6fb231a1d89ac403711",
        # ~8900 USDC sent back
        "0xce4a854560f5b8f5d1790b7828ce90147eafee2f75cfc4009581977eebff8d51",

        # "I moved them I moved them from yTrades to my EOA to dump since the liquidity was insanely small for OGV (mega price impact on cowswap) and there wasn't enough of VEC to justify cowswap"
        # "I sold them to eth over time in my deployer EOA and am just gonna use it for gas"
        "0x4713d14c624e0d4489980c91d3dc19fe468a9f0ad9c9b90fe4b7e55d9e67034e",

        # vault tokens sent to swapper msig
        ("0xae7d281b8a093da60d39179452d230de2f1da4355df3aea629d969782708da5d", IterFilter("log_index", (258, 262, 267, 272, 276))),
        # ~9136 crvUSD returned to treasury
        "0xac1f2a5e2960577e54c4a9cd096763cb6df614aa28eff221aeb4159097d9fa0f",
        # ~8112 USDC returned to treasury
        "0x015cdac2a021a44404c56600a96acfe2cb768e8789031b150be51db18874ec77",

        # one-off dumping 1INCH (on 1INCH not otc but this works)
        "0x037477c516652437004050e955edb6bc0de82a6b0f03e7665009e802c196516f",

        # not otc swap, but swapped by 0x444 so close enough
        ("0xd7e7abe600aad4a3181a3a410bef2539389579d2ed28f3e75dbbf3a7d8613688", IterFilter('log_index', (558, 559))),

        "0x5a65d5299864ae6db364ee6a459a4f50d19e6fa8892f4f4c0221372b6c9b3ca2",
        "0x71bd987e89940185b1131a6b73b981f5716c767ac12d106bf226a1aa8880f7c8",
    ),
)
