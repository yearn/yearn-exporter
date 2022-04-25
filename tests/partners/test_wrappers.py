from brownie import chain
from tests.fixtures.decorators import mainnet_only
from toolz import concat
from yearn.networks import Network
from yearn.partners import snapshot


def test_wildcard_wrapper_unwrap_single():
    test_details = {
        Network.Mainnet: {
            "name": "gb1",
            "wrapper": "0x6965292e29514e527df092659FB4638dc39e7248",
            "len": 17
        },
        Network.Fantom: {
            "name": "beethovenx",
            "wrapper": "0x20dd72Ed959b6147912C2e529F0a0C651c33c9ce",
            "len": 7,
        },
    }[chain.id]

    wild = snapshot.WildcardWrapper(
        name=test_details["name"],
        wrapper=test_details["wrapper"],
    )
    contents = wild.unwrap()
    assert len(contents) >= test_details["len"]


@mainnet_only
def test_wildcard_wrapper_unwrap_multiple():
    """ This test only runs on Mainnet because the only partner with multiple WildcardWrappers (basketdao) is on Mainnet. """
    wrappers = [
        '0x0309c98B1bffA350bcb3F9fB9780970CA32a5060',
        '0x0aC00355F80E289f53BF368C9Bdb70f5c114C44B',
    ]
    # pull as single
    single = [snapshot.WildcardWrapper('basketdao', addr) for addr in wrappers]
    contents_from_single = list(concat(wild.unwrap() for wild in single))

    # pull as matrix
    multi = snapshot.WildcardWrapper(
        name='basketdao',
        wrapper=wrappers,
    )
    contents_from_multi = multi.unwrap()

    assert contents_from_single == contents_from_multi
    assert len(contents_from_multi) >= 13


@mainnet_only
def test_yapeswap_factory_wrapper():
    factory = snapshot.YApeSwapFactoryWrapper(
        'yapeswap', '0x46aDc1C052Fafd590F56C42e379d7d16622835a2'
    )
    contents = factory.unwrap()
    print(contents, len(contents))

    assert len(contents) >= 15
