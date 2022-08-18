
from brownie import chain
from yearn.entities import TreasuryTx
from yearn.networks import Network
from yearn.treasury.accountant.classes import Filter, HashMatcher, IterFilter
from yearn.treasury.accountant.constants import treasury

hashes = {
    Network.Mainnet: {
        'brand identity': [
            "0xd7188e4e6e0191e599bcb479991c8a8df228b725795e437e4c23728819bde82e",
        ],
        'design': [
            "0x31ea090cc6b7acc25be6881a9daa82bd7b120a219c9f53f340a1ab166c1f4f9f"
        ],
        'website': {
            'ux': {
                'testing': [
                    ["0x57fd81a0a665324558ae91a927097e44febd89972136165f3ec6cd4d6f8bc749", IterFilter('log_index', [162, 163, 164])]
                ],
            },
        },
    },
}.get(chain.id, {})

def is_travel_reimbursement(tx: TreasuryTx) -> bool:
    hashes = [
        '0xb11d1f505bcdba152c25c80d2c8268a437b50c86fe0cde2f26d3e952aca4e2b3',
        '0x628b9973ed22a5ea300dc79abcaf0d390e2941f28bc804886801ae9f82544f49',
        '0x20520b219ba999df961139d88e992459d345010ca6cbae57726911921824e653',
        '0xf3ccaabce022b773d93a5d497d228c8cb75d7cd5bf181802276ab26afb8459c7',
        '0x9aa72f4a6179d69b05dd53bd92b0667bd9a89930455040d837e82d652963c454',
        ["0x08ef1aacdf7d0f16be5e6fd0a64ebd0ba3b0c3dd0a7884a9a470aa89a7fe1a06", Filter('log_index', 221)],
        ["0x7a9e8649fdd346f96aa979f2aae252af1eb7852ba61dec08510c1f217c180fca", Filter('log_index', 55)],
        ["0xba8e44da6c6b6a27d575657bf01110d77afcc5b7820023d1f2cb3034201b027f", Filter('log_index', 269)],
        ["0x4adad1e3cff3410d50fb11ca31fa7029d8533b79192f120c2a445e1241711320", Filter('_from_nickname', "Disperse.app")],
        ["0xde196619d5ba63655f8cb3c84f1e7b0e2a23231804d52661f37062ffa8d97a32", Filter('_symbol', "DAI")],
        ["0x36bae3823953df3d2eae7f504349554a04972a147bb837a5d8e2e8f9abfc5fa8", IterFilter('log_index', [74,75,76,78])],
        # This tx is for a budget request TODO curate the budget requests somewhere in this repo.
        "0xe5ff2368fae88c103f80cbbc10a2f32b91f562d83bcd34e94aba6e249a0f317a",
        # This was for travel planning but this is the most fitting category at this time.
        "0x7222e1ae42ed80dc0b0cbc90db23b1b5ccae356d045ddb039ce635fd5871643b",
    ]
    return tx in HashMatcher(hashes)

def is_sms_discretionary_budget(tx: TreasuryTx) -> bool:
    if tx.from_address.address in treasury.addresses and tx._to_nickname == "Yearn Strategist Multisig" and tx._symbol == "DAI" and tx.amount == 200_000.0:
        return True
