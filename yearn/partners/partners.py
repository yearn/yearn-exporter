from datetime import date

from brownie import chain

from yearn.networks import Network
from yearn.partners.snapshot import (BentoboxWrapper, DegenboxWrapper,
                                     DelegatedDepositWildcardWrapper,
                                     ElementWrapper, GearboxWrapper, Partner,
                                     WildcardWrapper, Wrapper,
                                     YApeSwapFactoryWrapper)

partners = {
    Network.Mainnet: [
        Partner(
            name='popcorndao',
            start_date=None,
            treasury='0x403d41e72308b5D89a383C3F6789EDD7D3576Ee0',
            wrappers=[
                WildcardWrapper(
                    name='btr',
                    wrapper='0x109d2034e97ec88f50beebc778b5a5650f98c124',
                ),
            ],
        ),
        Partner(
            name='tempus',
            start_date=None,
            treasury='0xab40a7e3cef4afb323ce23b6565012ac7c76bfef',
            wrappers=[
                Wrapper(
                    name='yvUSDC Tempus Pool',
                    vault='0xa354F35829Ae975e850e23e9615b11Da1B3dC4DE',
                    wrapper='0x443297DE16C074fDeE19d2C9eCF40fdE2f5F62C2',
                ),
                Wrapper(
                    name='yvDAI Tempus Pool',
                    vault='0xdA816459F1AB5631232FE5e97a05BBBb94970c95',
                    wrapper='0x7e0fc07280f47bac3D55815954e0f904c86f642E',
                )
            ]
        ),
        Partner(
            name='coinomo',
            start_date=None,
            treasury='0xd3877d9df3cb52006b7d932e8db4b36e22e89242',
            wrappers=[
                Wrapper(
                    name='yvUSDC',
                    vault='0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9',
                    wrapper='0xd3877d9df3cb52006b7d932e8db4b36e22e89242',
                ),
            ],
        ),
        Partner(
            name='alchemix',
            start_date=None,
            treasury='0x8392F6669292fA56123F71949B52d883aE57e225',
            wrappers=[
                Wrapper(
                    name='dai 0.3.0',
                    vault='0x19D3364A399d251E894aC732651be8B0E4e85001',
                    wrapper='0x014dE182c147f8663589d77eAdB109Bf86958f13',
                ),
                Wrapper(
                    name='dai 0.3.0 transmuter',
                    vault='0x19D3364A399d251E894aC732651be8B0E4e85001',
                    wrapper='0x491EAFC47D019B44e13Ef7cC649bbA51E15C61d7',
                ),
                Wrapper(
                    name='dai 0.4.3',
                    vault='0xdA816459F1AB5631232FE5e97a05BBBb94970c95',
                    wrapper='0xb039eA6153c827e59b620bDCd974F7bbFe68214A',
                ),
                Wrapper(
                    name='dai 0.4.3 transmuter',
                    vault='0xdA816459F1AB5631232FE5e97a05BBBb94970c95',
                    wrapper='0x6Fe02BE0EC79dCF582cBDB936D7037d2eB17F661',
                ),
                Wrapper(
                    name='weth 0.4.2',
                    vault='0xa258C4606Ca8206D8aA700cE2143D7db854D168c',
                    wrapper='0x546E6711032Ec744A7708D4b7b283A210a85B3BC',
                ),
                Wrapper(
                    name='weth 0.4.2 transmuter',
                    vault='0xa258C4606Ca8206D8aA700cE2143D7db854D168c',
                    wrapper='0x6d75657771256C7a8CB4d475fDf5047B70160132',
                ),
                Wrapper(
                    name='V2 ydai',
                    vault='0xdA816459F1AB5631232FE5e97a05BBBb94970c95',
                    wrapper='0x5C6374a2ac4EBC38DeA0Fc1F8716e5Ea1AdD94dd',
                ),
                Wrapper(
                    name='V2 yusdc',
                    vault='0xa354F35829Ae975e850e23e9615b11Da1B3dC4DE',
                    wrapper='0x5C6374a2ac4EBC38DeA0Fc1F8716e5Ea1AdD94dd',
                ),
                Wrapper(
                    name='V2 yusdt',
                    vault='0x7Da96a3891Add058AdA2E826306D812C638D87a7',
                    wrapper='0x5C6374a2ac4EBC38DeA0Fc1F8716e5Ea1AdD94dd',
                ),
                Wrapper(
                    name='V2 yweth',
                    vault='0xa258C4606Ca8206D8aA700cE2143D7db854D168c',
                    wrapper='0x062Bf725dC4cDF947aa79Ca2aaCCD4F385b13b5c',
                ),
            ],
        ),
        Partner(
            name='inverse',
            start_date=None,
            treasury='0x926dF14a23BE491164dCF93f4c468A50ef659D5B',
            wrappers=[
                Wrapper(
                    name='dai-wbtc',
                    vault='0x19D3364A399d251E894aC732651be8B0E4e85001',
                    wrapper='0xB0B02c75Fc1D07d351C991EBf8B5F5b48F24F40B',
                ),
                Wrapper(
                    name='dai-yfi',
                    vault='0x19D3364A399d251E894aC732651be8B0E4e85001',
                    wrapper='0xbE21650b126b08c8b0FbC8356a8B291010ee901a',
                ),
                Wrapper(
                    name='dai-weth',
                    vault='0x19D3364A399d251E894aC732651be8B0E4e85001',
                    wrapper='0x57faa0dec960ed774674a45d61ecfe738eb32052',
                ),
                Wrapper(
                    name='usdc-weth',
                    vault='0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9',
                    wrapper='0x698c1d40574cd90f1920f61D347acCE60D3910af',
                ),
                Wrapper(
                    name='dola-stabilizer',
                    vault='0x19D3364A399d251E894aC732651be8B0E4e85001',
                    wrapper='0x973F509c695cffcF355787456923637FF8A34b29',
                ),
                Wrapper(
                    name='anYvCrvDOLA',
                    vault='0xd88dBBA3f9c4391Ee46f5FF548f289054db6E51C',
                    wrapper='0x3cFd8f5539550cAa56dC901f09C69AC9438E0722',
                ),
                Wrapper(
                    name='anYvDAI',
                    vault='0xdA816459F1AB5631232FE5e97a05BBBb94970c95',
                    wrapper='0xD79bCf0AD38E06BC0be56768939F57278C7c42f7',
                ),
                Wrapper(
                    name='anYvUSDT',
                    vault='0x7Da96a3891Add058AdA2E826306D812C638D87a7',
                    wrapper='0x4597a4cf0501b853b029cE5688f6995f753efc04',
                ),
                Wrapper(
                    name='anYvUSDC',
                    vault='0xa354F35829Ae975e850e23e9615b11Da1B3dC4DE',
                    wrapper='0x7e18AB8d87F3430968f0755A623FB35017cB3EcA',
                ),
                Wrapper(
                    name='anYvYFI',
                    vault='0xdb25cA703181E7484a155DD612b06f57E12Be5F0',
                    wrapper='0xE809aD1577B7fF3D912B9f90Bf69F8BeCa5DCE32',
                ),
                Wrapper(
                    name='anYvWETH',
                    vault='0xa258C4606Ca8206D8aA700cE2143D7db854D168c',
                    wrapper='0xD924Fc65B448c7110650685464c8855dd62c30c0',
                ),
                Wrapper(
                    name='anYvCrvCVXETH',
                    vault='0x1635b506a88fBF428465Ad65d00e8d6B6E5846C3',
                    wrapper='0xa6F1a358f0C2e771a744AF5988618bc2E198d0A0',
                ),
            ],
        ),
        Partner(
            name='frax',
            start_date=None,
            treasury='0x8d0C5D009b128315715388844196B85b41D9Ea30',
            wrappers=[
                Wrapper(
                    name='usdc',
                    vault='0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9',
                    wrapper='0xEE5825d5185a1D512706f9068E69146A54B6e076',
                ),
            ],
        ),
        Partner(
            name='pickle',
            start_date=None,
            treasury='0x066419EaEf5DE53cc5da0d8702b990c5bc7D1AB3',
            wrappers=[
                Wrapper(
                    name='usdc',
                    vault='0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9',
                    wrapper='0xEecEE2637c7328300846622c802B2a29e65f3919',
                ),
                Wrapper(
                    name='lusd',
                    vault='0x5fA5B62c8AF877CB37031e0a3B2f34A78e3C56A6',
                    wrapper='0x699cF8fE0C1A6948527cD4737454824c6E3828f1',
                ),
            ],
        ),
        Partner(
            name='badger',
            start_date=None,
            treasury='0xD0A7A8B98957b9CD3cFB9c0425AbE44551158e9e',
            wrappers=[
                Wrapper(
                    name='wbtc',
                    vault='0xA696a63cc78DfFa1a63E9E50587C197387FF6C7E',
                    wrapper='0x4b92d19c11435614CD49Af1b589001b7c08cD4D5',
                ),
            ],
        ),
        Partner(
            name='deus',
            start_date=None,
            treasury='0x4e8a7c429192bfda8c9a1ef0f3b749d0f66657aa',
            wrappers=[
                Wrapper(
                    name='aeth',
                    vault='0x132d8D2C76Db3812403431fAcB00F3453Fc42125',
                    wrapper='0x4e8a7c429192bfda8c9a1ef0f3b749d0f66657aa',
                )
            ],
        ),
        Partner(
            name='basketdao',
            start_date=None,
            treasury='0x7301C46be73bB04847576b6Af107172bF5e8388e',
            wrappers=[
                WildcardWrapper(
                    name='bdi',
                    wrapper='0x0309c98B1bffA350bcb3F9fB9780970CA32a5060',
                ),
                WildcardWrapper(
                    name='bmi',
                    wrapper='0x0aC00355F80E289f53BF368C9Bdb70f5c114C44B',
                ),
            ],
        ),
        Partner(
            name='gb',
            start_date=None,
            treasury='0x6965292e29514e527df092659FB4638dc39e7248',
            wrappers=[
                WildcardWrapper(
                    name='gb1',
                    wrapper='0x6965292e29514e527df092659FB4638dc39e7248',
                ),
            ],
        ),
        Partner(
            name='donutapp',
            start_date=None,
            treasury='0x9eaCFF404BAC19195CbD131a4BeA880Abd09B35e',
            wrappers=[
                Wrapper(
                    name='yvDAI',
                    vault='0x19D3364A399d251E894aC732651be8B0E4e85001',
                    wrapper='0x9eaCFF404BAC19195CbD131a4BeA880Abd09B35e',
                ),
            ],
        ),
        Partner(
            name="yieldster",
            start_date=None,
            treasury='0x2955278aBCE187315D6d72B0d626f1217786DF60',
            wrappers=[
                WildcardWrapper(
                    name="liva-one",
                    wrapper="0x2747ce11793F7059567758cc35D34F63ceE8Ac00",
                ),
            ],
        ),
        Partner(
            name="akropolis",
            start_date=None,
            treasury='0xC5aF91F7D10dDe118992ecf536Ed227f276EC60D',
            wrappers=[
                WildcardWrapper(
                    name="vaults-savings-v2",
                    wrapper="0x6511D8686EB43Eac9D4852458435c1beC4D67bc6",
                ),
            ],
        ),
        Partner(
            name="mover",
            start_date=None,
            treasury='0xf6A0307cb6aA05D7C19d080A0DA9B14eAB1050b7',
            wrappers=[
                Wrapper(
                    name="savings_yUSDCv2",
                    vault='0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9',
                    wrapper="0x541d78076352a884C8358a2ac3f36408b99a18dB",
                ),
            ],
        ),
        Partner(
            name='yapeswap',
            start_date=None,
            treasury='0x10DE513EE154BfA97f1c2841Cab91E8C389c7c72',
            wrappers=[
                YApeSwapFactoryWrapper(
                    'yapeswap', '0x46aDc1C052Fafd590F56C42e379d7d16622835a2'
                ),
            ],
        ),
        Partner(
            name='abracadabra',
            start_date=None,
            treasury='0xDF2C270f610Dc35d8fFDA5B453E74db5471E126B',
            retired_treasuries=[
                '0x5A7C5505f3CFB9a0D9A8493EC41bf27EE48c406D',
            ],
            # brownie run abracadabra_wrappers
            wrappers=[
                BentoboxWrapper(
                    name='yvCurve-IronBank',
                    vault='0x27b7b1ad7288079A66d12350c828D3C00A6F07d7',
                    wrapper='0xEBfDe87310dc22404d918058FAa4D56DC4E93f0A',
                ),
                BentoboxWrapper(
                    name='yvCurve-stETH',
                    vault='0xdCD90C7f6324cfa40d7169ef80b12031770B4325',
                    wrapper='0x0BCa8ebcB26502b013493Bf8fE53aA2B1ED401C1',
                ),
                BentoboxWrapper(
                    name='yvUSDC',
                    vault='0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9',
                    wrapper='0x6cbAFEE1FaB76cA5B5e144c43B3B50d42b7C8c8f',
                ),
                BentoboxWrapper(
                    name='yvUSDT',
                    vault='0x7Da96a3891Add058AdA2E826306D812C638D87a7',
                    wrapper='0x551a7CfF4de931F32893c928bBc3D25bF1Fc5147',
                ),
                BentoboxWrapper(
                    name='yvWETH',
                    vault='0xa258C4606Ca8206D8aA700cE2143D7db854D168c',
                    wrapper='0x920D9BD936Da4eAFb5E25c6bDC9f6CB528953F9f',
                ),
                BentoboxWrapper(
                    name='yvYFI',
                    vault='0xE14d13d8B3b85aF791b2AADD661cDBd5E6097Db1',
                    wrapper='0xFFbF4892822e0d552CFF317F65e1eE7b5D3d9aE6',
                ),
                BentoboxWrapper(
                    name='yvWETH',
                    vault='0xa9fE4601811213c340e850ea305481afF02f5b28',
                    wrapper='0x6Ff9061bB8f97d948942cEF376d98b51fA38B91f',
                ),
                DegenboxWrapper(
                    name='yvCurve-CVXETH',
                    vault='0x1635b506a88fBF428465Ad65d00e8d6B6E5846C3',
                    wrapper='0xf179fe36a36B32a4644587B8cdee7A23af98ed37',
                ),
                DegenboxWrapper(
                    name='yvDAI',
                    vault='0xdA816459F1AB5631232FE5e97a05BBBb94970c95',
                    wrapper='0x7Ce7D9ED62B9A6c5aCe1c6Ec9aeb115FA3064757',
                )
            ],
        ),
        Partner(
            name='chfry',
            start_date=None,
            treasury='0x3400985be0b41Ce9778823E9618074115f830799',
            wrappers=[
                Wrapper(
                    name='USDT yVault',
                    vault='0x7Da96a3891Add058AdA2E826306D812C638D87a7',
                    wrapper='0x87e51ebF96eEB023eCc28536Ad0DBca83dEE0203',
                ),
                Wrapper(
                    name='DAI yVault',
                    vault='0xdA816459F1AB5631232FE5e97a05BBBb94970c95',
                    wrapper='0xd5F38f4F1e0c157dd1AE8Fd66EE2761A14eF7324',
                ),
                Wrapper(
                    name='USDC yVault',
                    vault='0x5f18C75AbDAe578b483E5F43f12a39cF75b973a9',
                    wrapper='0x782bc9B1F11cDBa13aCb030cDab04f04FB667846',
                ),
            ],
        ),
        Partner(
            name='ambire',
            start_date=None,
            treasury='0xa07D75aacEFd11b425AF7181958F0F85c312f143',
            wrappers=[
                WildcardWrapper(
                    name="batcher",
                    wrapper="0x460fad03099f67391d84c9cc0ea7aa2457969cea",
                ),
            ],
        ),
        Partner(
            name='shapeshiftdao',
            start_date=None,
            treasury='0x90A48D5CF7343B08dA12E067680B4C6dbfE551Be',
            wrappers=[
                WildcardWrapper(
                    name='ShapeShift DAO Router',
                    wrapper='0x6a1e73f12018D8e5f966ce794aa2921941feB17E',
                ),
            ],
        ),
        Partner(
            name='gearbox',
            start_date=None,
            treasury='0x7b065Fcb0760dF0CEA8CFd144e08554F3CeA73D1',
            wrappers=[            
                GearboxWrapper(
                    name='gearbox usdc v2',
                    vault='0xa354F35829Ae975e850e23e9615b11Da1B3dC4DE',
                    wrapper='0x444CD42BaEdDEB707eeD823f7177b9ABcC779C04',
                ),
                GearboxWrapper(
                    name='gearbox dai v2',
                    vault='0xdA816459F1AB5631232FE5e97a05BBBb94970c95',
                    wrapper='0x444CD42BaEdDEB707eeD823f7177b9ABcC779C04',
                ),
                GearboxWrapper(
                    name='gearbox weth v2',
                    vault='0xa258C4606Ca8206D8aA700cE2143D7db854D168c',
                    wrapper='0x444CD42BaEdDEB707eeD823f7177b9ABcC779C04',
                ),
                GearboxWrapper(
                    name='gearbox wbtc v2',
                    vault='0xA696a63cc78DfFa1a63E9E50587C197387FF6C7E',
                    wrapper='0x444CD42BaEdDEB707eeD823f7177b9ABcC779C04',
                ),
                GearboxWrapper(
                    name='gearbox steth v2',
                    vault='0xdCD90C7f6324cfa40d7169ef80b12031770B4325',
                    wrapper='0x444CD42BaEdDEB707eeD823f7177b9ABcC779C04',
                ),
                GearboxWrapper(
                    name='gearbox frax v2',
                    vault='0xB4AdA607B9d6b2c9Ee07A275e9616B84AC560139',
                    wrapper='0x444CD42BaEdDEB707eeD823f7177b9ABcC779C04',
                ),                        
            ],     
        ),         
        Partner(
            name='wido',
            start_date=None,
            treasury='0x5EF7F250f74d4F11A68054AE4e150705474a6D4a',
            wrappers=[
                WildcardWrapper(
                    name='dt',
                    wrapper='0x7Bbd6348db83C2fb3633Eebb70367E1AEc258764',
                ),
                WildcardWrapper(
                    name='st',
                    wrapper='0x926D47CBf3ED22872F8678d050e70b198bAE1559',
                ),
            ],
        ),
        Partner(
            name='cofi',
            start_date=None,
            treasury='0x982646BA80a706B402Bf6e286A815c06f5b71129',
            wrappers=[
                Wrapper(
                    name='cofi-usdc-v1',
                    vault='0xa354F35829Ae975e850e23e9615b11Da1B3dC4DE',
                    wrapper='0x39936db69a547f617E96C42C241f4C574Fa81eE6',
                 ),
            ],
        ),
        Partner(
            name='rhino.fi',
            start_date=date(2022, 8, 24),
            treasury='0x520Cf70a2D0B3dfB7386A2Bc9F800321F62a5c3a',
            wrappers=[
                WildcardWrapper(
                    name='rhino.fi Layer2 StarkEx Bridge',
                    wrapper='0x5d22045DAcEAB03B158031eCB7D9d06Fad24609b',
                 ),
            ],
        ),
        Partner(
            name='element',
            start_date=None,
            treasury='0x82eF450FB7f06E3294F2f19ed1713b255Af0f541',
            wrappers=[
                ElementWrapper(
                    name='WrapperRegistry',
                    wrapper='0x149f615057F905988fFC97994E29c0Cc7DaB5337',
                ),
            ],
        ),
        Partner(
            name = 'Phuture',
            start_date=date(2022, 10, 22),
            treasury='0x237a4d2166Eb65cB3f9fabBe55ef2eb5ed56bdb9',
            wrappers=[
                Wrapper(
                    name='UNI Vault Controller',
                    vault='0xFBEB78a723b8087fD2ea7Ef1afEc93d35E8Bed42',
                    wrapper='0xA75425382590468346a58F7bE0801713Eb117546'
                ),
                Wrapper(
                    name='AAVE Vault Controller',
                    vault='0xd9788f3931Ede4D5018184E198699dC6d66C1915',
                    wrapper='0xFaC5b964d0A51ECf437f5C8D48EA685188f2e070'
                ),
                Wrapper(
                    name='YFI Vault Controller',
                    vault='0xdb25cA703181E7484a155DD612b06f57E12Be5F0',
                    wrapper='0x673Aa111acd33F6e4A406A3A02A8B94E3dBa00F1'
                ),
                Wrapper(
                    name='SUSHI Vault Controller',
                    vault='0x6d765CbE5bC922694afE112C140b8878b9FB0390',
                    wrapper='0x97c3a96c1BC8f3220A6B77312c8E88c715d3C501'
                ),
                Wrapper(
                    name='SNX Vault Controller',
                    vault='0xF29AE508698bDeF169B89834F76704C3B205aedf',
                    wrapper='0x34B19E5381235D72e92Feb1a0E594d665a0805c3'
                )
            ]
        ),
        Partner(
            name="ledger",
            start_date=date(2022, 11, 24),
            treasury="0x558247e365be655f9144e1a0140d793984372ef3",
            wrappers=[
                DelegatedDepositWildcardWrapper(
                    name="ledger",
                    partnerId="0x558247e365be655f9144e1a0140d793984372ef3",
                )
            ]
        ),
        Partner(
            name='choise',
            start_date=date(2023, 3, 1),
            treasury='0xEf2Cdb67A09F14e466a58A3ffCE579595282c970',
            wrappers=[
                DelegatedDepositWildcardWrapper(
                    name="TB",
                    partnerId="0x35b956B1d22d19Dc85A943039458743D2Fc64FF2",
                )
            ]
        )
    ],
    Network.Fantom: [
        Partner(
            name='abracadabra',
            start_date=None,
            treasury='0xb4ad8B57Bd6963912c80FCbb6Baea99988543c1c',
            wrappers=[
                BentoboxWrapper(
                    name='yvFTM',
                    vault='0x0DEC85e74A92c52b7F708c4B10207D9560CEFaf0',
                    wrapper='0xed745b045f9495B8bfC7b58eeA8E0d0597884e12'
                )
            ]
        ),
        Partner(
            name='qidao',
            start_date=None,
            treasury='0x679016B3F8E98673f85c6F72567f22b58Aa15A54',
            wrappers=[
                Wrapper(
                    name='fantom',
                    vault='0x0dec85e74a92c52b7f708c4b10207d9560cefaf0',
                    wrapper='0x7efb260662a6fa95c1ce1092c53ca23733202798',
                ),
                Wrapper(
                    name='dai',
                    vault='0x637ec617c86d24e421328e6caea1d92114892439',
                    wrapper='0x682e473fca490b0adfa7efe94083c1e63f28f034',
                ),
            ]
        ),
        Partner(
            name='tempus',
            start_date=None,
            treasury='0x51252c520375C6A236Bb56DdF0C407A099B2EC0e',
            wrappers=[
                Wrapper(
                    name='yvUSDC Tempus Pool',
                    vault='0xEF0210eB96c7EB36AF8ed1c20306462764935607',
                    wrapper='0x943B73d3B7373de3e5Dd68f64dbf85E6F4f56c9E',
                ),
                Wrapper(
                    name='yvDAI Tempus Pool',
                    vault='0x637eC617c86D24E421328e6CAEa1d92114892439',
                    wrapper='0x9c0273E4abB665ce156422a75F5a81db3c264A23',
                ),
                Wrapper(
                    name='yvUSDT Tempus Pool',
                    vault='0x148c05caf1Bb09B5670f00D511718f733C54bC4c',
                    wrapper='0xE9b557f9766Fb20651E3685374cd1DF6f977d36B',
                ),
                Wrapper(
                    name='yvWETH Tempus Pool',
                    vault='0xCe2Fc0bDc18BD6a4d9A725791A3DEe33F3a23BB7',
                    wrapper='0xA9C549aeFa21ee6e79bEFCe91fa0E16a9C7d585a',
                ),
                Wrapper(
                    name='yvYFI Tempus Pool',
                    vault='0x2C850cceD00ce2b14AA9D658b7Cad5dF659493Db',
                    wrapper='0xAE7E5242eb52e8a592605eE408268091cC8794b8',
                )
            ]
        ),
        Partner(
            name='Sturdy',
            start_date=None,
            treasury='0xFd1D36995d76c0F75bbe4637C84C06E4A68bBB3a',
            wrappers=[
                Wrapper(
                    name='yvWFTM',
                    vault='0x0DEC85e74A92c52b7F708c4B10207D9560CEFaf0',
                    wrapper='0x7d939674451ab005EC51d523f5D6846B745e2565',
                ),
                Wrapper(
                    name='yvBOO',
                    vault='0x0fBbf9848D969776a5Eb842EdAfAf29ef4467698',
                    wrapper='0x6C5ee1f9B050E0De3489d60f687bEf16ee5c4C3D',
                ),
                Wrapper(
                    name='yvfBEETS',
                    vault='0x1e2fe8074a5ce1Bb7394856B0C618E75D823B93b',
                    wrapper='0x63F925C970ba617662fde778Cf5fB70d798B2bB8',
                ),
                Wrapper(
                    name='yvLINK',
                    vault='0xf2d323621785A066E64282d2B407eAc79cC04966',
                    wrapper='0x197dcF678163C20d0D34dC8065F6eba36D5BAD3E',
                ),
            ],
        ),
        Partner(
            name='wido',
            start_date=None,
            treasury='0x5EF7F250f74d4F11A68054AE4e150705474a6D4a',
            wrappers=[
                WildcardWrapper(
                    name='Router',
                    wrapper='0x7Bbd6348db83C2fb3633Eebb70367E1AEc258764',
                ),
            ],
        ),
        Partner(
            name='beethovenx',
            start_date=None,
            treasury='0xa1E849B1d6c2Fd31c63EEf7822e9E0632411ada7',
            wrappers=[
                WildcardWrapper(
                    name='Vault',
                    wrapper='0x20dd72Ed959b6147912C2e529F0a0C651c33c9ce',
                ),
            ],
        ),
        Partner(
            name='alchemix',
            start_date=None,
            treasury='0x6b291CF19370A14bbb4491B01091e1E29335e605',
            wrappers=[
                Wrapper(
                    name='V2 ydai',
                    vault='0x637eC617c86D24E421328e6CAEa1d92114892439',
                    wrapper='0x76b2E3c5a183970AAAD2A48cF6Ae79E3e16D3A0E',
                ),
                Wrapper(
                    name='V2 yusdc',
                    vault='0xEF0210eB96c7EB36AF8ed1c20306462764935607',
                    wrapper='0x76b2E3c5a183970AAAD2A48cF6Ae79E3e16D3A0E',
                ),
                Wrapper(
                    name='V2 yusdt',
                    vault='0x148c05caf1Bb09B5670f00D511718f733C54bC4c',
                    wrapper='0x76b2E3c5a183970AAAD2A48cF6Ae79E3e16D3A0E',
                ),
            ],
        ),
        Partner(
            name='SpoolFi',
            start_date=date(2022, 10, 2),
            treasury='0xF6Bc2E3b1F939C435D9769D078a6e5048AaBD463',
            wrappers=[
                WildcardWrapper(
                    name='MasterSpool',
                    wrapper='0xe140bB5F424A53e0687bfC10F6845a5672D7e242',
                ),
            ],
        ),
        Partner(
            name='choise',
            start_date=date(2023, 3, 1),
            treasury='0xEf2Cdb67A09F14e466a58A3ffCE579595282c970',
            wrappers=[
                DelegatedDepositWildcardWrapper(
                    name="TB",
                    partnerId="0x9A2E8Bc149cDB13dB60ABC108425bB388eda2F9d",
                ),
            ],
        ),
    ],
}.get(chain.id, [])
