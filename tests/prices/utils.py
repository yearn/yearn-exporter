import tokenlists


def get_tokens():
    manager = tokenlists.TokenListManager()
    name = 'Uniswap Default List'
    if name not in manager.available_tokenlists():
        manager.install_tokenlist('https://gateway.ipfs.io/ipns/tokens.uniswap.org')
    return [
        token.address
        for token in manager.get_tokenlist(name).tokens
        if token.chainId == 1
    ]


tokens = get_tokens()
