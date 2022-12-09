import json
from datetime import datetime, timezone
from pathlib import Path

import requests
import sentry_sdk
from multicall.utils import await_awaitable
from semantic_version import Version
from tokenlists import TokenInfo, TokenList
from toolz import unique
from y.contracts import contract_creation_block
from y.time import get_block_timestamp

from yearn.multicall2 import multicall_matrix
from yearn.utils import contract
from yearn.yearn import Yearn

sentry_sdk.set_tag('script','tokenlist')


def main():
    yearn = Yearn()
    excluded = {
        "0xBa37B002AbaFDd8E89a1995dA52740bbC013D992",
        "0xe2F6b9773BF3A015E2aA70741Bde1498bdB9425b",
        "0xBFa4D8AA6d8a379aBFe7793399D3DdaCC5bBECBB",
    }
    resp = requests.get("https://raw.githubusercontent.com/iearn-finance/yearn-assets/master/icons/aliases.json").json()
    aliases = {item["address"]: item for item in resp}
    tokens = []

    # Token derived by products
    for product in yearn.registries:
        # v1 is property v2 is async property. TODO refactor this
        vaults = yearn.registries[product].vaults
        if hasattr(vaults, "__await__"):
            vaults = await_awaitable(vaults)
        vaults = [item.vault for item in vaults if str(item.vault) not in excluded]
        metadata = multicall_matrix(vaults, ["name", "symbol", "decimals"])
        for vault in vaults:
            tokens.append(
                TokenInfo(
                    chainId=1,
                    address=str(vault),
                    name=aliases.get(str(vault), metadata[vault])["name"],
                    decimals=metadata[vault]["decimals"],
                    symbol=aliases.get(str(vault), metadata[vault])["symbol"],
                    logoURI=f"https://raw.githubusercontent.com/yearn/yearn-assets/master/icons/tokens/{vault}/logo.svg",
                    tags=[product],
                )
            )

    # Token from special / side projects
    special = [
        contract("0xD0660cD418a64a1d44E9214ad8e459324D8157f1") # WOOFY
    ]
    metadata = multicall_matrix(special, ["name", "symbol", "decimals"])
    for token in special:
        tokens.append(
            TokenInfo(
                chainId=1,
                address=str(token),
                name=aliases.get(str(token), metadata[token])["name"],
                decimals=metadata[token]["decimals"],
                symbol=aliases.get(str(token), metadata[token])["symbol"],
                logoURI=f"https://raw.githubusercontent.com/yearn/yearn-assets/master/icons/tokens/{token}/logo.svg",
                tags=["special"],
            )
        )

    deploy_blocks = {token.address: contract_creation_block(token.address) for token in tokens}
    tokens = unique(tokens, key=lambda token: token.address)
    tokens = sorted(tokens, key=lambda token: deploy_blocks[token.address])
    version = Version(major=1, minor=len(tokens), patch=0)
    timestamp = datetime.fromtimestamp(get_block_timestamp(max(deploy_blocks.values())), timezone.utc).isoformat()
    logo = "https://raw.githubusercontent.com/yearn/yearn-assets/master/icons/tokens/0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e/logo.svg"

    print(f"{version=}\n{timestamp=}")
    tokenlist = TokenList("Yearn", timestamp, version, tokens, logoURI=logo)
    for token in tokenlist.tokens:
        assert len(token.symbol) <= 20, f"{token.symbol} > 20 chars, uniswap is unhappy"

    path = Path("static/tokenlist.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(tokenlist.to_dict(), separators=(",", ":")))
    print(f"saved to {path}")
