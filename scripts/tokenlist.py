import json
from datetime import datetime, timezone
from pathlib import Path

from semantic_version import Version
from tokenlists import TokenInfo, TokenList

from yearn.multicall2 import multicall_matrix
from yearn.utils import contract_creation_block, get_block_timestamp
from yearn.yearn import Yearn


def main():
    yearn = Yearn(load_strategies=False)
    excluded = {"0xBa37B002AbaFDd8E89a1995dA52740bbC013D992"}
    tokens = []
    for product in yearn.registries:
        vaults = [item.vault for item in yearn.registries[product].vaults if str(item.vault) not in excluded]
        metadata = multicall_matrix(vaults, ["name", "symbol", "decimals"])
        for vault in vaults:
            tokens.append(
                TokenInfo(
                    chainId=1,
                    address=str(vault),
                    name=metadata[vault]["name"],
                    decimals=metadata[vault]["decimals"],
                    symbol=metadata[vault]["symbol"],
                    logoURI=f"https://raw.githubusercontent.com/yearn/yearn-assets/master/icons/tokens/{vault}/logo.svg",
                    tags=[product],
                )
            )

    # remove token = bump major, add token = bump minor
    version = Version(major=0, minor=len(tokens), patch=0)
    deploy_blocks = {token.address: contract_creation_block(token.address) for token in tokens}
    tokens = sorted(tokens, key=lambda token: deploy_blocks[token.address])
    timestamp = datetime.fromtimestamp(get_block_timestamp(max(deploy_blocks.values())), timezone.utc).isoformat()

    print(f"{version=}")
    print(f"{timestamp=}")

    tokenlist = TokenList("Yearn", timestamp, version, tokens)

    path = Path("static/tokenlist.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(tokenlist.to_dict(), separators=(",", ":")))
    print(f"saved to {path}")
