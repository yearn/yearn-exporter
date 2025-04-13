from brownie import chain
from pony.orm import commit
from y.networks import Network

from yearn.entities import TreasuryTx
from yearn.treasury.accountant.classes import _FROM_DISPERSE_APP, Filter, HashMatcher


strategist_gas_hashes = {
    Network.Mainnet: [
        '0x407d6ad61cbab79133ae53483bc2b2b12c2d0f4e1978558ed7c8073a3822caed',
        '0x80f7fbef821811d80674a0c9a85c52f386b73fc21cb4efa987a53f422cdf8f08',
        '0xd479074b20b9e48e403c84dd66da9f7aab1263c45c21da42b53cdfee03f2d523',
        '0x0bd71c844a10cc1f12d547e83f6465cbdd2e8618eeab614781a18464b03168ad',
        '0x3b30ead8fe9be3c7f5a32d1b5f3efd4a38c1410539db4c17aee49b725e9efd56',
        '0x08499992f6f6bf5a11edce89af4259c941a1b257f79902fb4b8dca49fba5643d',
        '0x10601dab5e982ca671135a283d91cef0388c16de3fbbb00c87f6226f5041f870',
        '0x396117cd539920c38e6520dfe546bb07f9058ae82bb9db270af6fbec0505758e',
        '0xe350027531bca82204118429b5f966a0596079d9d771ea166ad8f76ba1837334',
        '0x70aa54bf69d8881fbecffe4d4c0107f25cbf460574a501f8deca008528c79b2e',
        '0x8319cab95a1c74629a5dfc0eb5c6614311e65bdc7fa540e81212edbca57670a3',
        '0x828808782814342418d24d284ee6338993120d9c4144b87b8f8199c078389221',
        '0xbede300b44aca7a02f9b4738112c15089b5f81d6e34ee2c4e9d3348a8fecf73e',
        '0x1bd363b2af4a7508d797bb6c9cc66da34d02aeb52da4f3e90c9e3ce9762360f7',
        '0x43e48d3f6cacf6a27c4b382444ae1df09a33472ef46c3740cbf54ae48b1688e0',
        '0xed5a29b64df4b6faba6c1c7bc4480eae9c537c4bdcad48516cfd78b1cf458b06',
        '0x1157e684a387153c6d4fce716dda0d707c41474f93317a7c170975e576773bcf',
        '0x570d7b194c4d47f2c7d2faba57847523e33f72d8361b9ff781d16c0898861e42',
        '0x202d249537ca47864d29f6bca500c9161b77711e681fcb72b86ea2756f259dbf',
        '0x446bb882cf7769cdddd1481deef432a0bf74e53e7db7653f098536e4a3d81f59',
        '0xd6f577adaac039e72d3737b5aeeaca6d434d5140487fd2f414ef9e66589fefad',
        '0x25ded1c0ed0af0ca386709fcb808ebe5bbf0eb675b4c136b47fb51c1adfb2650',
        '0xa2d63dd5c8f80c0796ed6e0d3a06a60b85beced6273c2e8cc7816ca7a9514eae',
        '0xe966e3a8bbc99f29c78e2c461f6c1e7ce1b64fa092bee364a27b1ad437507648',
        '0xc9c4b4103751bef92a23e1d4671e392021a6464d61153473dcc9a14d74504e7e',
        '0xc3bb4642c21a810a22d0bd4e17f12f920031a7bb960ab48faee3e7c549048d90',
        '0xc76d45b2c4a94bbf45548732f61f4c656ae5a49a580bd2913ff16b04850a65ad',
        '0x09561098e79641a2e3c0f118993eed0febfea9858138ddb3e45480de164f2210',
        '0x46ea28a06892eeada4ae351f0776250bc4658299375cb35a9cba24b9807fbcb9',
        '0xb5a946ee557b646580ff319c2e073f8d2a99e1cdc636362d62c4af5c104cf0f7',
        '0x0dacd763125214bc7e38ab420522eabdc018a34e78fbf117346f21a2422cc662',
        '0x3835de76c872b61973c4d957b6a06d222fc5c9766646f3e15693788d738d65ab',
        '0xdcd38bd068e15f6b25de6602409206a9a87658bbbe4b6e1206aec47d9b907d82',
        '0xf5e65bd0baf2c48280d4779629b6c6755c5f63ed38e1af6362e005a20ea5ce63',
        '0xf2c05c9e9acd7c59c4b884592bc2a8e8a04bd97d23c5afe056b9a7fe063e3086',
        '0xd786627bdc8ccfc1b103b4fada5176b6d3144b55874cfcb46c2a2e4941be2558',
        '0x181a4b264bc193186097d195f1096b87b482d3cbcc0baab016ce910bd9745cc0',
        '0xedbebe235ef62e126f2dc701badb77f3557a6f32a0fa362e2431715db71ddf4e',
        '0x6afdc3367e28b1388f875fc5ddcc3536d983dfda4897c0f6b206a8b460205e2e',
        '0xbc158f9efed2f1d9b1baa13a150a8eb734b9652b4fda842da4f3d2a2f5781f0c',
        '0x67e11775ca149fd2f8d865a142237786f04ee75c18ad6ba7675c0ab2d33ac9cb',
        '0xed1852fd4685eb81f756c7ff9dfa0b97a4372c3f71dfff95123d16b2a80bece3',
        '0x8414887aa252dd1c9834189c502a8679452cba314f7ca1a8a817419031625e15',
        '0x3c0799c6b0ca62ad3d868359eb00f95bfd54349c4f7422f1ab186f0e18ed3a52',
        '0xa78a7efe4200c22ea20419f606f2cb280e2d4f7a32e92c0c7b8fbe02a96b3f75',
        '0x6a9c40b8d78d9e09849a48be204f2c3072144c75cf6ca75cd39e3d78d2f4c352',
        "0x6e32e36b13bce4c4838fc083516f1e780e303b55a26a45c0e79acf0c17e2b05f",
        "0xd700344511719054e95d260f5494266cdd950825bf577160cf5acb02d87f5a63",
        "0xb8c71e4491a692c8d293f13e37bf03aa8487ad5306f3db8fc4e83c406f8c0746",
        "0x96be538314a6547063a5b81ded9bda38a067528d4bcfc558eee976a684e5b44a",
        ["0xebfff9a2fd6103d73f417c675db2dc43742bdb6f496f04d3cfd1938046001d70", Filter("_symbol", "ETH")],
        "0x269bcda1327da47fc0be53e044540f199ffb4c3f15146e0cb61348093b43b66e",
        "0x54c0a1c6fa29f1886ca8d307b06a93bd3fd9d86b62b301cadc8d4665f86715f5",
        "0x51202f9e8a9afa84a9a0c37831ca9a18508810175cb95ab7c52691bbe69a56d5",
        # NOTE: don't think we need these filters due to the if check at the first line in `is_strategist_gas`. 
        # TODO: refactor out
        ["0x96728585c7b1720f2e94a3a2ff339ed6433bd6687cd680dd2534e6837271111a", _FROM_DISPERSE_APP],
        ["0xecbc1474610b31046124aa6323863f47d6e348385056ab80c3cc1f6b963f5d68", _FROM_DISPERSE_APP],
        ["0x5fb3320fdc41aba54743559cd4248e5cdfd8ffc67bd329c13cd3b66ce4976144", _FROM_DISPERSE_APP],
        ["0x7afceac28536b9b2c177302c3cfcba449e408b47ff2f0a8a3c4b0e668a4d5d4e", _FROM_DISPERSE_APP],
        ["0xb8bb3728fdfb49d7c86c08dba8e3586e3761f13d2c88fa6fab80227b6a3f4519", _FROM_DISPERSE_APP],
        ["0x76635bffdf8ee07736bf6953611cd93b5f6f10ef9a59f2504661047e834ea4d6", _FROM_DISPERSE_APP],
        "0x76cec8d40341ed064b636530a6ccfdb9fcc0855f6716b592d286e579d6eab433",
        "0x9c9c342186bfc7232b28a11d3ecea32e6cb417b3c7b41e67e1f5c06ff32c0d9c",
        "0x038aeb3351b762bc92c5e4274c01520ae08dc314e2282ececc2a19a033d994a8",
        "0x49a930eeb2a709e162d05d29a5d19b6f71aa5fb63a369395ca869e1961a3bb27",
        "0x6169de8578935f15e24b1dc0e22c5670c5240505425ab4d71283026d96538381",
        "0x3d3b714d3cacef6dca14b8abff10d882af62209d389d4225761e461f10b47e39",
        "0x3efe08a7dc37ad120d61eb52d7ffcec5e2699f62ee1bd9bd55ece3dfb7ec4441",
    ],
}.get(chain.id, ())

def is_strategist_gas(tx: TreasuryTx) -> bool:
    if tx._from_nickname == "Disperse.app":
        return tx in HashMatcher(strategist_gas_hashes)
    
    # Returned gas
    if tx in HashMatcher({
        Network.Mainnet: (
            '0x86fee63ec8efb0e7320a6d48ac3890b1089b77a3d9ed74cade389f512471c299',
            '0xa77c4f7596968fef96565a0025cc6f9881622f62cc4c823232f9c9000ba5f981',
            '0xac2253f1d8f78680411b353d65135d58bc880cdf9507ea7848daf05925e1443f',
            '0xd27d4a732dd1a9ac93c7db1695a6d2aff40e007627d710da91f328b246be44bc',
            '0x5a828e5bde96cd8745223fe32daefaa9140a09acc69202c33f6f789228c8134b',
            '0x110ef82ec16eb53bf71b073aca4a37d4fbfaa74166c687a726211392a02f0059',
            '0xaad012505975dd13a57599a28d33c979f72084ae56ccba76997f05822a5497f5',
        ),
    }.get(chain.id, ())):
        tx.amount *= -1
        tx.value_usd *= -1
        commit()
        return True
        
    return tx in HashMatcher({
        Network.Mainnet: (
            "0x420cfbc7856f64e8949d4dd6d4ce9570f8270def1380ebf381376fbcd0b0d5bf",
            "0xc7bca93dc6bfa37e45bebb030a2ce1198fc402176ba0b3a5553a0580299df5e7",
        ),
    }.get(chain.id, ()))

def is_multisig_reimbursement(tx: TreasuryTx) -> bool:
    return tx._symbol == "ETH" and tx in HashMatcher([
        ["0x19bcb28cd113896fb06f17b2e5efa86bb8bf78c26e75c633d8f1a0e48b238a86", Filter('_from_nickname', 'Yearn yChad Multisig')]
    ])

def is_other_gas(tx: TreasuryTx) -> bool:
    return tx._symbol == "ETH" and tx in HashMatcher([
        # Reimbursement for testing
        ["0x57bc99f6007989606bdd9d1adf91c99d198de51f61d29689ee13ccf440b244df", Filter('to_address', '0xB1d693B77232D88a3C9467eD5619FfE79E80BCCc')]
    ])

def is_yearn_harvest(tx: TreasuryTx) -> bool:
    # NOTE define hueristics for this if it occurs freuently
    return tx in HashMatcher([
        "0xb05494705ce91cc5e5db259ded8acaf80b645c655556ee40a85097fd9054d9b6",
    ])
