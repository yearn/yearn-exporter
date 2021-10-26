import json
from functools import lru_cache

import numpy as np
import pytest
import requests
from brownie import chain, multicall, web3
from tabulate import tabulate
from yearn.prices import curve
from yearn.prices.magic import PriceError
from yearn.utils import contract, contract_creation_block

pooldata = json.load(open('tests/fixtures/pooldata.json'))

registries = {
    'v1': '0x7D86446dDb609eD0F5f8684AcF30380a356b2B4c',
    'v2': '0x90E00ACe148ca3b23Ac1bC8C240C2a7Dd9c2d7f5',
}

meta_factories = {
    'v1': '0x0959158b6040D32d04c301A72CBFD6b39E21c9AE',
    'v2': '0xB9fC157394Af804a3578134A6585C0dc9cc990d4',
}

new_metapools = [
    "0x1F71f05CF491595652378Fe94B7820344A551B8E",
    "0xFD5dB7463a3aB53fD211b4af195c5BCCC1A03890",
    "0x8461A004b50d321CB22B7d034969cE6803911899",
    "0x19b080FE1ffA0553469D20Ca36219F17Fcf03859",
    "0x621F13Bf667207335C601F8C89eA5eC260bAdA9A",
    "0xED24FE718EFFC6B2Fc59eeaA5C5f51dD079AB6ED",
    "0x6c7Fc04FEE277eABDd387C5B498A8D0f4CB9C6A6",
    "0xDa5B670CcD418a187a3066674A8002Adc9356Ad1",
    "0x99AE07e7Ab61DCCE4383A86d14F61C68CdCCbf27",
    "0x6A274dE3e2462c7614702474D64d376729831dCa",
    "0x06cb22615BA53E60D67Bf6C341a0fD5E718E1655",
    "0x43b4FdFD4Ff969587185cDB6f0BD875c5Fc83f8c",
    "0xd632f22692FaC7611d2AA1C0D552930D43CAEd3B",
    "0xEd279fDD11cA84bEef15AF5D39BB4d4bEE23F0cA",
    "0x5a6A4D54456819380173272A5E8E9B9904BdF41B",
    "0x9D0464996170c6B9e75eED71c68B99dDEDf279e8",
    "0x5B3b5DF2BF2B6543f78e053bD91C4Bdd820929f1",
    "0x3CFAa1596777CAD9f5004F9a0c443d912E262243",
    "0x6d0Bd8365e2fCd0c2acf7d218f629A319B6c9d47",
    "0xAA5A67c256e27A5d80712c51971408db3370927D",
    "0x8818a9bb44Fbf33502bE7c15c500d0C783B73067",
    "0x3F1B0278A9ee595635B61817630cC19DE792f506",
    "0xD6Ac1CB9019137a896343Da59dDE6d097F710538",
    "0x9c2C8910F113181783c249d8F6Aa41b51Cde0f0c",
    "0xc8a7C1c4B748970F57cA59326BcD49F5c9dc43E3",
    "0x3Fb78e61784C9c637D560eDE23Ad57CA1294c14a",
]
old_metapools = [
    "0x9547429C0e2c3A8B88C6833B58FCE962734C0E8C",
    "0x43b4FdFD4Ff969587185cDB6f0BD875c5Fc83f8c",
    "0xd632f22692FaC7611d2AA1C0D552930D43CAEd3B",
    "0x11E0Ab0561Ee271967F70Ea0DA54Fd538ba7a6B0",
    "0xf5A95ccDe486B5fE98852bB02d8eC80a4b9422BD",
    "0xE0b99F540B3cD69f88b4666c8f39877c79072851",
    "0x592ae00d0DEE274d74faeDc6760302F54A5dB67e",
    "0x6f682319F4eE0320a53cc72341aC28408C4BeD19",
    "0x296B9FA08cf80138dfa6c3fcce497152662BC314",
    "0xe9Ab166bC03099d251170d0578FDFFb94bCDDe6F",
    "0x064841157BadDcB2704cA38901D7d754a59b80E8",
    "0x3252eFd4EA2d6c78091a1f43982ee2C3659cC3D1",
    "0xEcd5e75AFb02eFa118AF914515D6521aaBd189F1",
    "0x52EEEa483Ab7A801e2592a904Ad209C90e12E471",
    "0x52890A0c018fbab21794AD18e15f87fdb57fb975",
    "0x1Daf17e6d1d9ed6aa9Fe9910AE17Be98C2C4e6BA",
    "0x2B26239f52420d11420bC0982571BFE091417A7d",
    "0xBd184cD60AF678633b3072FD0B47b5D4b7a072f3",
    "0x9f6664205988C3bf4B12B851c075102714869535",
    "0xF9bE07E6E1f28890c1647612187Df8c6e4CC035b",
    "0x910A00594DC16dD699D579A8F7811d465Dfa2752",
    "0x6Df2B0855060439251fee7eD34952b87b68EeEd9",
    "0xf085c77B66cD32182f3573cA2B10762DF3Caaa50",
    "0xaC63c167955007D5166Fec43255AD5675EfC3102",
    "0x421CB018b91b4048FaAC1760Cee3B66026B940f2",
    "0x4AcE85cF348F316384A96b4739A1ab58f5123E7a",
    "0x23078d5BC3AAD79aEFa8773079EE703168F15cF5",
    "0xaFcc5DADcDcFc4D353Ab2d36fbd57b80513a34e6",
    "0xE764Fb1f870D621a197951F1A27aaC6d4F930329",
    "0xaF47f0877A9b26FfF12ec8253E07f92F89c6805D",
    "0x273AfbF6E257aae160749a61D4b83E06A841c3eB",
    "0xfB51e37CebC5D6f1569004206629BB7e47b6843f",
    "0x152d13e62952a7c74c536bb3C8b7BD91853F076A",
    "0xf01E56475ea4081e6640914b2310E1Aa8F09d2E1",
    "0xbe735E6dd6c47d86BF8510D3c36Cba1a359B8dDc",
    "0xd97f71Bc0Ecb40B105dBACF5225d847d9c2334F8",
    "0x2009f19A8B46642E92Ea19adCdFB23ab05fC20A6",
    "0xEd279fDD11cA84bEef15AF5D39BB4d4bEE23F0cA",
    "0xA46649Ffe1860d79DBE777930aF8e802B8b48AC4",
    "0x4807862AA8b2bF68830e4C8dc86D0e9A998e085a",
    "0x87ca9AC842905628A83df72a23aa480091BB682e",
    "0x51714B15aB2C2172914A005f4f2889f16Af7003c",
    "0x92719D8b48795CBccD7eC68114ea7a2Db8065140",
    "0xf5C511E559342087d30a793705228bFEB881c325",
    "0xB0c6CE798da73F455c2ac4d669C9F4106c251193",
    "0xdCB5BE55674ceC407D8A6D28aE2098FEdDf2c296",
    "0xcf2be480d37777E6eE846e935E57Aaae1fd466F4",
    "0xf5E2e90952d3Bdf8e9ACA1Fb38Fa195F0A108a9D",
    "0xda3B4449E055C76a740dC5796aFC7bE2A535a70F",
    "0x1E20205cd346CD8e5FcA92fCEa34Ead4057e4AE5",
    "0x11fbFe3a6c183Dcd6Fd9BaA42Fe39206174a6C00",
    "0xF9ef8A8dE38ceA3196a4E009aD7A7aF6F5A3d776",
    "0x9d7ee35a38952bd5Ad36dB0BF435a298363ac1Aa",
    "0x4EB0Bb03A246b955D36316a96BE314885c23a1B0",
    "0xDa3028f415374dE92cD5A7C64F865a6B1AAbf804",
    "0x0750da0ED0a4448eD516c326d702e7Fee88F4aD9",
    "0xe69fC18b2252f5c3Cf8b8C35CE06AF0Bb461d476",
    "0x3c7Ac391Ad242c7C2Cfbf004ed72C0bDf9d620cc",
    "0x883F7d4B6B24F8BF1dB980951Ad08930D9AEC6Bc",
    "0xD5c91b8161924F389A33E97FC8624431a53858F5",
    "0xDD577F3c26e322d6e790947D5e56362c3F99Cc6d",
    "0x9231dfF16BE1020dcE7dd6F48d565FDA123c11C8",
    "0xAf7c2Fb62ea78Bd5bE98F716de55B480C354f17B",
    "0x5c277D5CC9b258Ca957FF83Ec41d153c4DF7619A",
    "0x3EaC18b3e7A4663d38cb6EDB6024cad9d5E76a49",
    "0x6448113F6c31F738B7c6b24c1b4A1Cf23c6133f2",
    "0xE75916b70c0E1C58bB605948066151EA449561F4",
    "0x5400234516485A8e474A6f1c34DBed940a1A866E",
    "0x1E556F647f79e734530F2B354FBf339553fB1f6E",
    "0xC55834C9cDf6e92e0ceB181fd07f6243eAC0f598",
    "0xf6b657Cb19A4cB2AF427D50F3054104871100D52",
    "0x56680FDEbDd3e31f79938fa1222bFea4706a0758",
    "0x0212133321479B183637e52942564162bCc37C1D",
    "0x8e49801018361aBb1EDe67D5B12907A5F895C623",
    "0x46f5ab27914A670CFE260A2DEDb87f84c264835f",
    "0x2206cF41E7Db9393a3BcbB6Ad35d344811523b46",
    "0xC3134cCB0810418Dcc2540c7df6E4995a9966d4e",
    "0x0043Fcb34e7470130fDe28198571DeE092c70Bd7",
    "0x439bfaE666826a7cB73663E366c12f03d0A13B49",
    "0xBc984294CedABE05d7317CC55BCdA241a7222615",
    "0x0457E0ed628143b6A6A39f6e3458153f96abB26a",
    "0x3c9aEEb08be0c10cA4135e981F2C73dF8a28F8a0",
    "0xDc0b9c549809BD4BDe021BD35A99f612D472d827",
    "0x8aEe2e72ff7e34fC15dcAD5BbAa6AB2dF1bdEb1c",
    "0x620E3C54d8c6efCA7476D657c57dA5Eb144d3f81",
    "0x8B93c5727fF8c0e4CD16f8ae8dFe4DAc8730C4BE",
    "0xd752B367B1d5998446daA6E9Eb90d05D12d9f263",
    "0x5a6A4D54456819380173272A5E8E9B9904BdF41B",
    "0x20955CB69Ae1515962177D164dfC9522feef567E",
    "0xEAF21e096793d92A1028Bb6F2570846d79165B48",
    "0xF420cdabD89a40D98541df39014576CeAB01cdc7",
    "0xC3018Fc8B7aC3a01c1fAdb3292B50e6faC417486",
    "0x4dF9E1A764Fb8Df1113EC02fc9dc75963395b508",
    "0xeb20b6Dda329685863c7193d8C3b13D3DEf9a02F",
    "0x3279827b8233Ab455ba6F6bcB9804ee601Bf725B",
    "0x0c46aC7dC6a06Fa5de5a6e74c0726F96c0319900",
    "0x80Bb24b127b96f8C6637acF3BAcAE4F5F860F08c",
    "0xfE97D8f55884186E50AeDba306Ad553911a26A24",
    "0x5e94A7EE56a168B06C79E5fd972AE0C35cB36FEa",
    "0x2a1E73bf81941630869c125194fBF8f5Ec060Ff0",
    "0x67d9eAe741944D4402eB0D1cB3bC3a168EC1764c",
    "0x8CAdb80062D6EA09b6d480cB3F955cb7F915b2C7",
    "0x6E386F8E746af332d18f5c21F3369835C9c5DB16",
    "0x57EB6fbE61216d9f8c7c09Ad1EE5a3023747244b",
    "0x87650D7bbfC3A9F10587d7778206671719d9910D",
    "0x6eC80df362d7042c50D4469bcfbc174C9dd9109a",
]

metapools = new_metapools + old_metapools


@pytest.fixture(scope='session')
def convex_gauge_map():
    booster = contract('0xF403C135812408BFbE8713b5A23a04b3D48AAE31')
    with multicall:
        pools = [booster.poolInfo(i) for i in range(booster.poolLength())]

    return {pool['lptoken']: pool['gauge'] for pool in pools}


@pytest.fixture(scope='session')
@lru_cache
def curve_tvl_api():
    data = requests.get('https://api.curve.fi/api/getTVL').json()
    return {
        web3.toChecksumAddress(pool['pool_address']): pool['balance']
        for pool in data['data']['allPools']
    }


@pytest.mark.parametrize('name', pooldata)
def test_curve_pool_from_lp_token(name):
    lp_token = pooldata[name]['lp_token_address']
    pool = curve.curve.get_pool(lp_token)
    assert pool == pooldata[name]['swap_address']


@pytest.mark.parametrize('pool', range(len(metapools)))
def test_curve_metapool_from_lp_token(pool):
    # metapool are both swap and lp
    assert metapools[pool] == curve.curve.get_pool(metapools[pool])


def test_curve_pool_from_lp_token_invalid():
    assert not curve.curve.get_pool('0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e')


@pytest.mark.parametrize('pool', range(len(metapools)))
def test_curve_registry_get_factory(pool):
    assert curve.curve.get_factory(metapools[pool]) in meta_factories.values()


@pytest.mark.parametrize('name', pooldata)
def test_curve_gauge_curve_registry(name):
    if not pooldata[name]['gauge_addresses']:
        return
    pool = pooldata[name]['swap_address']
    assert curve.curve.get_gauge(pool) == pooldata[name]['gauge_addresses'][0]


@pytest.mark.parametrize('name', pooldata)
def test_curve_gauge_convex(name, convex_gauge_map):
    if not pooldata[name]['gauge_addresses'] or name in ['link']:
        pytest.xfail('known unsupported pool')
    convex_gauge = convex_gauge_map[pooldata[name]['lp_token_address']]
    assert convex_gauge == pooldata[name]['gauge_addresses'][0]


@pytest.mark.parametrize('pool', range(len(new_metapools)))
def test_curve_meta_gauge(pool):
    if pool in [0, 4, 5, 6, 7, 9, 16, 17, 18, 24, 25]:
        pytest.xfail('no gauge')
    pool = new_metapools[pool]
    gauge = curve.curve.get_gauge(pool)
    print(pool, gauge)
    assert gauge


@pytest.mark.parametrize('name', pooldata)
def test_curve_balances_from_registry(name):
    pool = pooldata[name]['swap_address']
    tvl = curve.curve.get_tvl(pool)
    print(tvl)
    assert tvl


@pytest.mark.parametrize('name', pooldata)
def test_curve_lp_price_oracle(name):
    token = pooldata[name]['lp_token_address']
    price = curve.curve.get_price(token)
    print(price)
    assert price


@pytest.mark.parametrize('name', pooldata)
def test_curve_lp_price_oracle_historical(name):
    if name in ['linkusd']:
        pytest.xfail('no active market')

    token = web3.toChecksumAddress(pooldata[name]['lp_token_address'])
    swap = web3.toChecksumAddress(pooldata[name]['swap_address'])
    deploy = contract_creation_block(swap)
    # sample 10 blocks over the pool lifetime
    blocks = [int(block) for block in np.linspace(deploy + 10000, chain.height, 10)]
    prices = []
    for block in blocks:
        try:
            prices.append(curve.curve.get_price(token, block))
        except (PriceError, TypeError):
            prices.append(None)

    virtual_prices = [contract(swap).get_virtual_price(block_identifier=block) / 1e18 for block in blocks]

    print(tabulate(list(zip(blocks, prices, virtual_prices)), headers=['block', 'price', 'vp']))


@pytest.mark.parametrize('name', pooldata)
def test_curve_total_value(name, curve_tvl_api):
    if name in ['linkusd']:
        pytest.xfail('no active market')

    pool = web3.toChecksumAddress(pooldata[name]['swap_address'])
    tvl = curve.curve.get_tvl(pool)
    print(name, tvl)
    assert tvl

    # FIXME pending curve api update
    # assert tvl == pytest.approx(curve_tvl_api[pool], rel=2e-2)


@pytest.mark.parametrize('name', pooldata)
def test_get_balances_fallback(name):
    registry_deploy = 12195750
    pool = web3.toChecksumAddress(pooldata[name]['swap_address'])
    if curve.curve.get_factory(pool):
        pytest.skip('not applicable to metapools')
    print(name, curve.curve.get_balances(pool, block=registry_deploy))
