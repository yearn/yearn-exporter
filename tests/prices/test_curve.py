import json
from functools import lru_cache

import numpy as np
import pytest
import requests
from brownie import ZERO_ADDRESS, chain, multicall, web3
from tabulate import tabulate
from y.contracts import contract_creation_block
from y.exceptions import PriceError
from y.networks import Network
from y.prices.magic import get_price

from yearn.utils import contract

if chain.id == Network.Mainnet:
    pooldata = json.load(open('tests/fixtures/pooldata.json'))
else:
    pooldata = {}

registries = {
    Network.Mainnet: {
        'v1': '0x7D86446dDb609eD0F5f8684AcF30380a356b2B4c',
        'v2': '0x90E00ACe148ca3b23Ac1bC8C240C2a7Dd9c2d7f5',
    },
}.get(chain.id, {})

# contract(address_provider).get_address(3)
meta_factories = { 
    Network.Mainnet: {
        'v1': '0x0959158b6040D32d04c301A72CBFD6b39E21c9AE',
        'v2': '0xB9fC157394Af804a3578134A6585C0dc9cc990d4',
    },
    Network.Fantom: {
        'v2': '0x686d67265703D1f124c45E33d47d794c566889Ba',
    }
}.get(chain.id, {})

new_metapools = {
    Network.Mainnet: [
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
    ],
    Network.Fantom: [
        '0x03fa4c23bA3a7BC0BeC18789CE29c7857324bD22',
        '0x075C1D1d7E9E1aF077B0b6117C6eA06CD0a260b5',
        '0x0F5e1fC301437b344271c14Ffb52431a97CE4113',
        '0x11093B0F9780ACcdb6322959a45d749Ca3789257',
        '0x115266f936B2ea12eBb5cf5eB2D35f9c46614436',
        '0x12cb0687B95158340287D8391D0Ca5314c10532D',
        '0x138CCfE5d99c139B9c4918AcE02a082cA67693bB',
        '0x1484Ae179657e01dE76C0Dc95A5838B1e797eB81',
        '0x16E0bf935e696E0652CDB3EfA10b6A00C162d135',
        '0x170eAAeBd5D398003A42A7414B704e13E1744c3a',
        '0x1c7FA28E7BFa396a4B044cC939daFF51674d852B',
        '0x1cb5C03d0585333A6D0578D47a5F9de66C80fD5A',
        '0x1dc3F42f9E598999a784498D00f360F305A5B4D2',
        '0x24699312CB27C26Cfc669459D670559E5E44EE60',
        '0x259303442a9772222856C9Ae5212051048Bd3D9D',
        '0x261036923F4aAF1322a3173921fCBdaE51352CAe',
        '0x262a70f82df61a94F3E6fCD17895A25d6bEb07F6',
        '0x27E611FD27b276ACbd5Ffd632E5eAEBEC9761E40',
        '0x28368D7090421Ca544BC89799a2Ea8489306E3E5',
        '0x2dd7C9371965472E5A5fD28fbE165007c61439E1',
        '0x34033F0227C48bc3577aE5C6923A3DEEF3E36670',
        '0x36586206bFc13ED520597b3DAE1313C8b1496388',
        '0x38D0dD9d036ce6f291442c258F1cc2FC0d10e682',
        '0x43EC4106b3A09b17f8669E268f36Cc5cdd5F356f',
        '0x43a9f7d71F59DA647E367a713b2c2534A3938047',
        '0x46F5ea3B7867b451Eb1568FA820a6e89c5492795',
        '0x4cd4786426eD34DBd96ba64e4a7B676FAD25D71C',
        '0x57F24a2E740516a351E2357d74215d235eE725FE',
        '0x5AAC39FD59300f913096afafaa7b8E0be143f1b0',
        '0x64a4CDc2c96146f8588dfB16DD3660Eb6Ea4109B',
        '0x674E594A71464DDc55737ebfba37062B9044f9F4',
        '0x68dde7344a302394845097E96E83cDdFe6D4d76e',
        '0x6EF78ad4a40E9A6c81B9229de3eCc33ce591bC34',
        '0x6d304d364B461Aab0496bf696A23F44a55fc43b6',
        '0x7673F9226C8Ce29a86ED6Ad1C1D8574BB1d201e4',
        '0x78AE5704B6664a07f14c7d3a14a98e7d6DfC80aa',
        '0x7a656B342E14F745e2B164890E88017e27AE7320',
        '0x7c79acC9aEf46E4d55BD05d06C24E79C35183241',
        '0x7e4143Ed63635E5f53f0272c307eac4A5238037a',
        '0x83A503780983bbaBd6ACab577FbA2c5A3DcAa57f',
        '0x84f21b7ceb64906320E2b62cF73Ff03dcFd137dC',
        '0x859009D02F0f609E585Be78e4427599FfaD4Ca14',
        '0x872686B519E06B216EEf150dC4914f35672b0954',
        '0x8B63F036F5a34226065bC0a7B0aE5bb5eBA1fF3D',
        '0x8cD8Ab34189ee11A60c17Fb8bd394e4702De11fb',
        '0x9171aaa40AD493fa6B6DACf60265272Cc58E49d0',
        '0x92D5ebF3593a92888C25C0AbEF126583d4b5312E',
        '0x9452699E70b648A3A499FA044bA0e58dEcB21A5a',
        '0x96059756980fF6ced0473898d26F0EF828a59820',
        '0x96817E9E47419dd66346AB64811e0f43aB75fEC8',
        '0x9834766a92135DBd03b987Bf423aB89A18656194',
        '0x9F83dbD9dBE351e3575a65dF04Ce34d3426e5B06',
        '0x9a1394f9f9F2d600A4F4062190B941b036865FF1',
        '0x9dc516a18775d492c9f061211C8a3FDCd476558d',
        '0x9e85a45772F1078f3CaFf4B8c0FB43de4CA776E2',
        '0xA58F16498c288c357e28EE899873fF2b55D7C437',
        '0xA7CC236F81b04c1058e9bfb70E0Ee9940e271676',
        '0xA7d2Ac1D5A1cFba7e3e21B68e76c48dd16348592',
        '0xA8B3C9f298877dD93F30E8Ed359956faE10E8797',
        '0xAD0FB83a110c3694faDa81e8B396716a610c4030',
        '0xAD6D5548c45b1b198A4A563Cba1C3D384AFc44C6',
        '0xB3045222d3F3725C4bEB1047f6C54514b3333ed7',
        '0xB407481462ec40b706DF0D22e11d8BEFbc2Adf54',
        '0xBe26e1858faFbF2de92fdd717AC098E34d9e526A',
        '0xC1A2D9341135c7e3f00EDBED51F9C7acab7c7B3F',
        '0xC822FC64AaD7b04B2eddE961c0704AB80F9D217B',
        '0xCc0F443c62229f8944379d87a853f1898e682214',
        '0xD5B51BA080F815446646a61039fBbFef5A12A4CF',
        '0xD73a2802697263fb84cb06bBCe9501A2d33dc880',
        '0xDC371bB71dE3a8E50683E7eb596690Db9D0365Cc',
        '0xDE535Ee3999470286178B736e6A8D976a6822A3E',
        '0xE8117F058A37367d6bf70a8E56B569d7fd5e2A8B',
        '0xEEf1f7F11c3728100737c6355EEfD40Cacd6B506',
        '0xEf3A4Fa40Fda4Eff051f14828dCe1C47d17488B3',
        '0xF24f1061ee2C116D8dB1d0F6C791bCB741F9f08a',
        '0xF427A0BE7524B022f89742EAf2F52EA433280aC3',
        '0xF95ab97a4d41bA67A8F7298a3C9245C293855659',
        '0xFa6Ddd52738FbEC9Ed649986AA1b74236B83aEbd',
        '0xa1F70A0515BDc2954508125aDd49f72d01ee74c0',
        '0xa3500EEC27bfD7d0000982DB3290a2c79143ed80',
        '0xa5FAE68615010EFE0F22E98C48c75BFBB6141718',
        '0xaD9c5054CC31f8AA822AEb9247298D2Ecf48c5cf',
        '0xad71Fc10Fca8Ce6a98843A64b95E0C63516CA7F3',
        '0xb17DeFAB9Da9A48F2712B92db8dA7c4EDb2D1c0a',
        '0xbcC30798BBC4cDe6011a2C8cB7e5C21e5f0D0e35',
        '0xbd05dF58eD93560457aD2Bc8d1Fe69Aa45Bbd636',
        '0xc1ccCec6FC0D23B471E1c3877cb7558442D35Df5',
        '0xc687e9038d7aCECF4842fD06D1b8d2d8CEF8e790',
        '0xc87dc1E718E5dAbB438e69E8F3A1a6979dd46868',
        '0xc955b79959aca2895AC8667A418849e4C218A708',
        '0xd3f83ec4BB684712D9CA8519eDAfbb910470F77C',
        '0xe1bA291eED6Ed14A4e65dCbe6a4936Fe15B3A1a4',
        '0xe38e2c6361c14a17219f7c00bDD93DCc945f096A',
        '0xeCf64ba816C75e595fF212391E80B5CD9071E7D5',
        '0xee6Cc45B3c937DdBa9FAdD44eBA3Ea4dcceE05f1',
    ],
}.get(chain.id, [])

old_metapools = {
    Network.Mainnet: [
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
    ],
}.get(chain.id, [])

metapools = new_metapools + old_metapools

eur_usd_crypto_pool_tokens = {
    Network.Mainnet: [
        "0x3b6831c0077a1e44ED0a21841C3bC4dC11bCE833",
        "0x3D229E1B4faab62F621eF2F6A610961f7BD7b23B"
    ],
}.get(chain.id, [])


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


@pytest.mark.parametrize('i', range(len(metapools)))
def test_curve_metapool_from_lp_token(i):
    # metapool are both swap and lp
    pool = metapools[i]
    assert pool == curve.curve.get_pool(pool)


def test_curve_pool_from_lp_token_invalid():
    assert not curve.curve.get_pool('0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e')


@pytest.mark.parametrize('i', range(len(metapools)))
def test_curve_registry_get_factory(i):
    pool = metapools[i]
    print(pool)
    try:
        assert curve.curve.get_factory(pool) in meta_factories.values()
    except AssertionError:
        # If we can't fetch factory, can we fetch registry?
        assert curve.curve.get_registry(pool) == "0x0f854EA9F38ceA4B1c2FC79047E9D0134419D5d6"


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


@pytest.mark.parametrize('i', range(len(new_metapools)))
def test_curve_meta_gauge(i):
    # NOTE This list might need updating once in a while if gauges are added for exiting pools.
    no_gauge = {
        Network.Mainnet: [0, 4, 5, 6, 7, 17, 18, 24],
        Network.Fantom: [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94]
    }

    pool = new_metapools[i]
    if i in no_gauge[chain.id]:
        assert not curve.curve.get_gauge(pool)
    else:
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

    abnormal_start_blocks = {
        # `pool.get_virtual_price` will revert before these blocks.
        '0x845838DF265Dcd2c412A1Dc9e959c7d08537f8a2': 9567758,  # cDAI+cUSDC
        '0xDE5331AC4B3630f94853Ff322B66407e0D6331E8': 11445709, # pBTC/sbtcCRV
        '0x194eBd173F6cDacE046C53eACcE9B953F28411d1': 11485492, # eursCRV
    }
    start_block = deploy if token not in abnormal_start_blocks else abnormal_start_blocks[token]

    # sample 10 blocks over the pool lifetime
    blocks = [int(block) for block in np.linspace(start_block + 10000, chain.height, 10)]
    prices = []
    for block in blocks:
        try:
            prices.append(curve.curve.get_price(token, block))
        except PriceError:
            prices.append(None)

    virtual_prices = [curve.curve.get_virtual_price(curve.curve.get_pool(token),block) for block in blocks]

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
    if contract_creation_block(pool) > registry_deploy:
        pytest.skip('not applicable to pools deployed after test block')
    if curve.curve.get_factory(pool):
        pytest.skip('not applicable to metapools')
    print(name, curve.curve.get_balances(pool, block=registry_deploy))


@pytest.mark.parametrize('i', range(len(eur_usd_crypto_pool_tokens)))
def test_crypto_pool_eur_usd_assets(i):
    lp_token = eur_usd_crypto_pool_tokens[i]
    pool = curve.curve.get_pool(lp_token)
    coins = curve.curve.get_coins(pool)
    non_zero_coins = list(filter(lambda coin: coin != ZERO_ADDRESS, coins))
    underlying_coin_prices = map(lambda coin: get_price(coin), non_zero_coins)
    summed_coin_prices = sum(underlying_coin_prices)

    price = curve.curve.get_price(lp_token)
    # the price of the crypto pool token should be approximately equal to the sum of the
    # underlying coins, provided they are roughly equally balanced in the pool
    assert price == pytest.approx(summed_coin_prices, rel=2e-1)
