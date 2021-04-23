import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from semantic_version import Version
from tokenlists import TokenInfo, TokenList

from yearn.multicall2 import multicall_matrix
from yearn.utils import contract_creation_block, get_block_timestamp
from yearn.yearn import Yearn


def main():
    yearn = Yearn(load_strategies=False)
    excluded = {"0xBa37B002AbaFDd8E89a1995dA52740bbC013D992"}
    resp = requests.get("https://raw.githubusercontent.com/iearn-finance/yearn-assets/master/icons/aliases.json").json()
    aliases = {item["address"]: item for item in resp}
    tokens = []
    for product in yearn.registries:
        vaults = [item.vault for item in yearn.registries[product].vaults if str(item.vault) not in excluded]
        metadata = multicall_matrix(vaults, ["name", "symbol", "decimals"])
        for vault in vaults:
            tokens.append(
                TokenInfo(
                    chainId=1,
                    address=str(vault),
                    name=aliases.get(str(vault), metadata[vault]["name"]),
                    decimals=metadata[vault]["decimals"],
                    symbol=aliases.get(str(vault), metadata[vault]["symbol"]),
                    logoURI=f"https://raw.githubusercontent.com/yearn/yearn-assets/master/icons/tokens/{vault}/logo.svg",
                    tags=[product],
                )
            )

    # remove token = bump major, add token = bump minor
    version = Version(major=0, minor=len(tokens), patch=0)
    deploy_blocks = {token.address: contract_creation_block(token.address) for token in tokens}
    tokens = sorted(tokens, key=lambda token: deploy_blocks[token.address])
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
