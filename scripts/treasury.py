import logging
import os

import pandas as pd
from brownie import Contract, chain, convert, web3
from pandas.core.frame import DataFrame
from requests import get
from ypricemagic import magic
from ypricemagic.utils.utils import Contract_with_erc20_fallback

from eth_abi import encode_single

moralis = 'https://deep-index.moralis.io/api/v2/'
moralis_key = os.environ['MORALIS_KEY']
headers = {"x-api-key": moralis_key}

def walletdataframe(wallet, block):
    # NOTE: Moralis API is returning absurd values for token balances,
    # so we will disreagrd balances returned by the API. We only use 
    # the API to fetch a list of tokens in the wallet. We then use the
    # token list to query correct balances from the blockchain.

    url = f'{moralis}{wallet}/erc20'
    df = pd.DataFrame(get(url, headers=headers).json())

    # NOTE: Remove spam tokens
    df = df[~df.token_address.isin(SPAM_TOKENS)]

    def getcategory(token_address):
        try:
            return CATEGORY_MAPPINGS[token_address]
        except KeyError:
            return

    def getbalance(token_address):
        logging.debug(f'token: {token_address}')
        return Contract_with_erc20_fallback(token_address).balanceOf(wallet, block_identifier=block)

    def getprice(token_address):
        if token_address == '0x27d22a7648e955e510a40bdb058333e9190d12d4': # PPOOL
            return magic.get_price('0x0cec1a9154ff802e7934fc916ed7ca50bde6844e',block)
        return magic.get_price(token_address, block)
    
    # NOTE: Add some details
    df['wallet'] = wallet
    df['wallet_label'] = YEARN_WALLETS[wallet]
    df['category'] = df['token_address'].apply(getcategory)

    # NOTE: Do some maths
    df['balance'] = df['token_address'].apply(getbalance) / 10 ** df['decimals'].apply(int)
    df['price'] = df['token_address'].apply(getprice)
    df['value'] = df['balance'] * df['price']
    
    # NOTE: Get rid of columns we don't need
    df = df.drop(columns=['logo','thumbnail','decimals'])
    
    # NOTE: Get rid of tokens with 0 balance
    df = df[df['balance'] != 0]

    ethbal = web3.eth.get_balance(convert.to_address(wallet), block_identifier = block)/10 ** 18
    if ethbal > 0:
        ethprice = magic.get_price('0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2', block)
        return df.append(pd.DataFrame({
            'token_address': [None],
            'name': ['Ethereum'],
            'symbol': ['ETH'],
            'balance': [ethbal],
            'category': ['ETH'],
            'wallet': [wallet],
            'wallet_label': [YEARN_WALLETS[wallet]],
            'price': [ethprice],
            'value': [ethbal * ethprice],
        }))
    return df

def dataframe(block):
    for wallet in YEARN_WALLETS:
        print(wallet)
        walletdf = walletdataframe(wallet,block)
        try:
            df = df.append(walletdf)
        except UnboundLocalError:
            df = walletdf

    def appendmore(token_address,amount,wallet,category=False,wallet_label=False):
        token = Contract(token_address)
        price = magic.get_price(token_address, block)
        if category and not wallet_label:
            return df.append(pd.DataFrame({
                'token_address': [token.address],
                'name': [token.name()],
                'symbol': [token.symbol()],
                'balance': [amount],
                'category': [category],
                'wallet': [wallet],
                'wallet_label': [YEARN_WALLETS[wallet]],
                'price': [price],
                'value': [amount * price],
            }))
        if wallet_label and not category:
            return df.append(pd.DataFrame({
                'token_address': [token.address],
                'name': [token.name()],
                'symbol': [token.symbol()],
                'balance': [amount],
                'category': [CATEGORY_MAPPINGS[token.address]],
                'wallet': [wallet],
                'wallet_label': [wallet_label],
                'price': [price],
                'value': [amount * price],
            }))
        if wallet_label and category:
            return df.append(pd.DataFrame({
                'token_address': [token.address],
                'name': [token.name()],
                'symbol': [token.symbol()],
                'balance': [amount],
                'category': [category],
                'wallet': [wallet],
                'wallet_label': [wallet_label],
                'price': [price],
                'value': [amount * price],
            }))
        return df.append(pd.DataFrame({
            'token_address': [token.address],
            'name': [token.name()],
            'symbol': [token.symbol()],
            'balance': [amount],
            'category': [CATEGORY_MAPPINGS[token.address]],
            'wallet': [wallet],
            'wallet_label': [YEARN_WALLETS[wallet]],
            'price': [price],
            'value': [amount * price],
        }))

    # NOTE: CDP Collat & Debt
    # NOTE: Maker
    print('fetching MakerDAO data')
    proxy_registry = Contract('0x4678f0a6958e4D2Bc4F1BAF7Bc52E8F3564f3fE4')
    cdp_manager = Contract('0x5ef30b9986345249bc32d8928B7ee64DE9435E39')
    ychad = Contract('0xfeb4acf3df3cdea7399794d0869ef76a6efaff52')
    vat = Contract('0x35D1b3F3D7966A1DFe207aa4514C12a259A0492B')
    proxy = proxy_registry.proxies(ychad)
    cdp = cdp_manager.first(proxy)
    urn = cdp_manager.urns(cdp)
    ilk = encode_single('bytes32', b'YFI-A')
    art = vat.urns(ilk, urn, block_identifier = block).dict()["art"]
    rate = vat.ilks(ilk, block_identifier = block).dict()["rate"]
    debt = art * rate / 1e27
    if debt > 0:
        df = appendmore('0x6b175474e89094c44da98b954eedeac495271d0f', -1 * debt / 10 ** 18,'0xfeb4acf3df3cdea7399794d0869ef76a6efaff52',category='Debt')

    ink = vat.urns(ilk, urn, block_identifier = block).dict()["ink"]
    if ink > 0:
        df = appendmore('0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e', ink / 10 ** 18,urn,wallet_label='Maker')
    
    # NOTE: Unit.xyz
    print('fetching Unit.xyz data')
    unitVault = Contract("0xb1cff81b9305166ff1efc49a129ad2afcd7bcf19")
    debt = unitVault.getTotalDebt('0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e',ychad, block_identifier = block)
    if debt > 0:
        df = appendmore('0x1456688345527bE1f37E9e627DA0837D6f08C925', -1 * debt / 10 ** 18,'0xfeb4acf3df3cdea7399794d0869ef76a6efaff52',category='Debt')

    bal = unitVault.collaterals('0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e',ychad, block_identifier = block)
    if bal > 0:
        df = appendmore('0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e', bal / 10 ** 18,unitVault.address,wallet_label='Unit.xyz')


    # NOTE: This doesn't factor in unspent balance in Blue Citadel, get unspent balance in Blue Citadel
    
    # NOTE: This doesn't factor in bonded KP3R or LP tokens, get bonded KP3R and LP tokens
    print('fetching KP3R escrow data')
    yearnKp3rWallet = "0x5f0845101857d2a91627478e302357860b1598a1"
    escrow = Contract("0xf14cb1feb6c40f26d9ca0ea39a9a613428cdc9ca")
    kp3rLPtoken = Contract("0xaf988aff99d3d0cb870812c325c588d8d8cb7de8")
    bal = escrow.userLiquidityTotalAmount(yearnKp3rWallet,kp3rLPtoken, block_identifier = block)
    if bal > 0:
        df = appendmore(kp3rLPtoken.address, bal / 10 ** 18,escrow.address,wallet_label='KP3R Escrow')

    return df

def main():
    #logging.basicConfig(level=logging.DEBUG)
    block = chain[-1].number
    print(f'querying data at block {block}')
    df = dataframe(block)
    path = './reports/treasury_balances.csv'
    df.to_csv(path, index=False)
    print(f'csv exported to {path}')
    return df

def allocations(df=None):
    if df is None:
        block = chain[-1].number
        print(f'querying data at block {block}')
        df = dataframe(block)
    df = df.groupby(['category'])['value'].sum().reset_index()
    sumassets = df.loc[df['value'] > 0, 'value'].sum()
    df['pct_of_assets'] = df['value'] / sumassets * 100
    df = df.sort_values(['pct_of_assets'],ascending=False)
    path = './reports/treasury_allocation.csv'
    df.to_csv(path, index=False)
    print(f'csv exported to {path}')

def all():
    df = main()
    allocations(df=df)

YEARN_WALLETS = {
    '0xb99a40fce04cb740eb79fc04976ca15af69aaaae': 'Treasury V1'
    ,'0x93a62da5a14c80f265dabc077fcee437b1a0efde': 'Treasury V2'
    ,'0xfeb4acf3df3cdea7399794d0869ef76a6efaff52': 'Multisig'
    ,'0x5f0845101857d2a91627478e302357860b1598a1': 'EOA for Kp3r jobs'
}

SPAM_TOKENS = [
    '0xa9517b2e61a57350d6555665292dbc632c76adfe'
    ,'0xb07de4b2989e180f8907b8c7e617637c26ce2776'
    ,'0xcdbb37f84bf94492b44e26d1f990285401e5423e'
    ,'0x11068577ae36897ffab0024f010247b9129459e6'
    ,'0x528ff33bf5bf96b5392c10bc4748d9e9fb5386b2'
    ,'0xe256cf1c7caeff4383dabafee6dd53910f97213d'
    ,'0x53d345839e7df5a6c8cf590c5c703ae255e44816'
    ,'0x830cbe766ee470b67f77ea62a56246863f75f376'
    ,'0x8f49cb69ee13974d6396fc26b0c0d78044fcb3a7'
    ,'0x9694eed198c1b7ab81addaf36255ea58acf13fab'
    ,'0x1368452bfb5cd127971c8de22c58fbe89d35a6bf'
    # Not spam, still disregard for accounting
    # ape tax tokens 
    ,'0xf11b141be4d1985e41c3aea99417e27603f67c4c'
    ,'0x2832817633520bf0da1b57e2fb7bb2fba95014f9'
]

CATEGORY_MAPPINGS = {
    '0xfc1e690f61efd961294b3e1ce3313fbd8aa4f85d': 'Cash & cash equivalents'
    ,'0x6ee0f7bb50a54ab5253da0667b0dc2ee526c30a8': 'Cash & cash equivalents'
    ,'0x625ae63000f46200499120b906716420bd059240': 'Cash & cash equivalents'
    ,'0x6b175474e89094c44da98b954eedeac495271d0f': 'Cash & cash equivalents'
    ,'0xdac17f958d2ee523a2206206994597c13d831ec7': 'Cash & cash equivalents'
    ,'0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48': 'Cash & cash equivalents'
    ,'0x9ca85572e6a3ebf24dedd195623f188735a5179f': 'Cash & cash equivalents'
    ,'0x25212df29073fffa7a67399acefc2dd75a831a1a': 'Cash & cash equivalents'
    ,'0xf8768814b88281de4f532a3beefa5b85b69b9324': 'Cash & cash equivalents'
    ,'0x1aef73d49dedc4b1778d0706583995958dc862e6': 'Cash & cash equivalents'
    ,'0xfd2a8fa60abd58efe3eee34dd494cd491dc14900': 'Cash & cash equivalents'
    ,'0x3a664ab939fd8482048609f652f9a0b0677337b9': 'Cash & cash equivalents'
    ,'0xc25a3a3b969415c80451098fa907ec722572917f': 'Cash & cash equivalents'
    ,'0x845838df265dcd2c412a1dc9e959c7d08537f8a2': 'Cash & cash equivalents'
    ,'0x39caf13a104ff567f71fd2a4c68c026fdb6e740b': 'Cash & cash equivalents'
    ,'0x2994529c0652d127b7842094103715ec5299bbed': 'Cash & cash equivalents'
    ,'0xe2f2a5c287993345a840db3b0845fbc70f5935a5': 'Cash & cash equivalents'
    ,'0x7da96a3891add058ada2e826306d812c638d87a7': 'Cash & cash equivalents'
    ,'0x63739d137eefab1001245a8bd1f3895ef3e186e7': 'Cash & cash equivalents'
    ,'0x5a770dbd3ee6baf2802d29a901ef11501c44797a': 'Cash & cash equivalents'
    ,'0xa74d4b67b3368e83797a35382afb776baae4f5c8': 'Cash & cash equivalents'
    ,'0x30fcf7c6cdfc46ec237783d94fc78553e79d4e9c': 'Cash & cash equivalents'
    ,'0xb4d1be44bff40ad6e506edf43156577a3f8672ec': 'Cash & cash equivalents'
    ,'0x4962b6c40b5e9433e029c5c423f6b1ce7ff28b0f': 'Cash & cash equivalents'
    ,'0x84e13785b5a27879921d6f685f041421c7f482da': 'Cash & cash equivalents'
    ,'0x02d341ccb60faaf662bc0554d13778015d1b285c': 'Cash & cash equivalents'
    ,'0xd6ea40597be05c201845c0bfd2e96a60bacde267': 'Cash & cash equivalents'
    ,'0xc116df49c02c5fd147de25baa105322ebf26bd97': 'Cash & cash equivalents'
    ,'0xa5ca62d95d24a4a350983d5b8ac4eb8638887396': 'Cash & cash equivalents'
    ,'0x194ebd173f6cdace046c53eacce9b953f28411d1': 'Cash & cash equivalents'
    ,'0x5f18c75abdae578b483e5f43f12a39cf75b973a9': 'Cash & cash equivalents'
    ,'0x8cc94ccd0f3841a468184aca3cc478d2148e1757': 'Cash & cash equivalents'
    ,'0xda816459f1ab5631232fe5e97a05bbbb94970c95': 'Cash & cash equivalents'
    ,'0x0000000000085d4780b73119b644ae5ecd22b376': 'Cash & cash equivalents'
    ,'0x94e131324b6054c0d789b190b2dac504e4361b53': 'Cash & cash equivalents'
    ,'0xb4ada607b9d6b2c9ee07a275e9616b84ac560139': 'Cash & cash equivalents'
    ,'0x0fcdaedfb8a7dfda2e9838564c5a1665d856afdf': 'Cash & cash equivalents'
    ,'0x19d3364a399d251e894ac732651be8b0e4e85001': 'Cash & cash equivalents'
    ,'0x7eb40e450b9655f4b3cc4259bcc731c63ff55ae6': 'Cash & cash equivalents'
    ,'0xdf5e0e81dff6faf3a7e52ba697820c5e32d806a8': 'Cash & cash equivalents'
    ,'0x2a38b9b0201ca39b17b460ed2f11e4929559071e': 'Cash & cash equivalents'
    ,'0x054af22e1519b020516d72d749221c24756385c9': 'Cash & cash equivalents'
    ,'0x5dbcf33d8c2e976c6b560249878e6f1491bca25c': 'Cash & cash equivalents'
    ,'0x5fa5b62c8af877cb37031e0a3b2f34a78e3c56a6': 'Cash & cash equivalents'
    ,'0x8ee57c05741aa9db947a744e713c15d4d19d8822': 'Cash & cash equivalents'
    ,'0xaf322a2edf31490250fdeb0d712621484b09abb6': 'Cash & cash equivalents'
    ,'0x6ede7f19df5df6ef23bd5b9cedb651580bdf56ca': 'Cash & cash equivalents'
    ,'0x6c3f90f043a72fa612cbac8115ee7e52bde6e490': 'Cash & cash equivalents'
    ,'0x1c6a9783f812b3af3abbf7de64c3cd7cc7d1af44': 'Cash & cash equivalents'
    ,'0x3b3ac5386837dc563660fb6a0937dfaa5924333b': 'Cash & cash equivalents'
    ,'0xd2967f45c4f384deea880f807be904762a3dea07': 'Cash & cash equivalents'
    ,'0xc4daf3b5e2a9e93861c3fbdd25f1e943b8d87417': 'Cash & cash equivalents'
    ,'0x5b5cfe992adac0c9d48e05854b2d91c73a003858': 'Cash & cash equivalents'
    ,'0x27b7b1ad7288079a66d12350c828d3c00a6f07d7': 'Cash & cash equivalents'
    ,'0xdb25f211ab05b1c97d595516f45794528a807ad8': 'Cash & cash equivalents'
    ,'0x9ba60ba98413a60db4c651d4afe5c937bbd8044b': 'Cash & cash equivalents'
    ,'0xacd43e627e64355f1861cec6d3a6688b31a6f952': 'Cash & cash equivalents'
    ,'0x056fd409e1d7a124bd7017459dfea2f387b6d5cd': 'Cash & cash equivalents'
    ,'0x4f3e8f405cf5afc05d68142f3783bdfe13811522': 'Cash & cash equivalents'
    ,'0xed279fdd11ca84beef15af5d39bb4d4bee23f0ca': 'Cash & cash equivalents'
    ,'0x4b5bfd52124784745c1071dcb244c6688d2533d3': 'Cash & cash equivalents'
    ,'0x873fb544277fd7b977b196a826459a69e27ea4ea': 'Cash & cash equivalents'
    ,'0xfd0877d9095789caf24c98f7cce092fa8e120775': 'Cash & cash equivalents'
    ,'0x7158c1bee7a0fa5bd6affc77b2309991d7adcdd4': 'Cash & cash equivalents'
    ,'0x3b96d491f067912d18563d56858ba7d6ec67a6fa': 'Cash & cash equivalents'
    ,'0x2dfb14e32e2f8156ec15a2c21c3a6c053af52be8': 'Cash & cash equivalents'

    ,'0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e': 'YFI'
    ,'0x0bc529c00c6401aef6d220be8c6ea1667f6ad93e': 'YFI'
    ,'0xe14d13d8b3b85af791b2aadd661cdbd5e6097db1': 'YFI'
    
    ,'0xaa17a236f2badc98ddc0cf999abb47d47fc0a6cf': 'ETH'
    ,'0xbfedbcbe27171c418cdabc2477042554b1904857': 'ETH'
    ,'0xac333895ce1a73875cf7b4ecdc5a743c12f3d82b': 'ETH'
    ,'0xdcd90c7f6324cfa40d7169ef80b12031770b4325': 'ETH'
    ,'0xa9fe4601811213c340e850ea305481aff02f5b28': 'ETH'
    ,'0x132d8d2c76db3812403431facb00f3453fc42125': 'ETH'
    ,'0xa258c4606ca8206d8aa700ce2143d7db854d168c': 'ETH'
    ,'0x53a901d48795c58f485cbb38df08fa96a24669d5': 'ETH'
    ,'0x986b4aff588a109c09b50a03f42e4110e29d353f': 'ETH'
    ,'0xa3d87fffce63b53e0d54faa1cc983b7eb0b74a9c': 'ETH'
    ,'0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2': 'ETH'
    
    ,'0x410e3e86ef427e30b9235497143881f717d93c2a': 'BTC'
    ,'0x075b1bb99792c9e1041ba13afef80c91a1e70fb3': 'BTC'
    ,'0xb19059ebb43466c323583928285a49f558e572fd': 'BTC'
    ,'0x8fa3a9ecd9efb07a8ce90a6eb014cf3c0e3b32ef': 'BTC'
    ,'0x0e8a7717a4fd7694682e7005957dd5d7598bf14a': 'BTC'
    ,'0xbf7aa989192b020a8d3e1c65a558e123834325ca': 'BTC'
    ,'0x8414db07a7f743debafb402070ab01a4e0d2e45e': 'BTC'
    ,'0x49849c98ae39fff122806c06791fa73784fb3675': 'BTC'
    ,'0x2fe94ea3d5d4a175184081439753de15aef9d614': 'BTC'
    ,'0x625b7df2fa8abe21b0a976736cda4775523aed1e': 'BTC'
    ,'0xde5331ac4b3630f94853ff322b66407e0d6331e8': 'BTC'
    ,'0xe9dc63083c464d6edccff23444ff3cfc6886f6fb': 'BTC'
    ,'0x23d3d0f1c697247d5e0a9efb37d8b0ed0c464f7f': 'BTC'
    ,'0xa696a63cc78dffa1a63e9e50587c197387ff6c7e': 'BTC'
    ,'0x7047f90229a057c13bf847c0744d646cfb6c9e1a': 'BTC'
    ,'0x3c5df3077bcf800640b5dae8c91106575a4826e6': 'BTC'
    ,'0x410e3e86ef427e30b9235497143881f717d93c2a': 'BTC'
    ,'0x2260fac5e5542a773aa44fbcfedf7c193bc2c599': 'BTC'
    ,'0xa696a63cc78dffa1a63e9e50587c197387ff6c7e': 'BTC'
    
    ,'0xa64bd6c70cb9051f6a9ba1f163fdc07e0dfb5f84': 'Other short term assets'
    ,'0x0cec1a9154ff802e7934fc916ed7ca50bde6844e': 'Other short term assets'
    ,'0xf2db9a7c0acd427a680d640f02d90f6186e71725': 'Other short term assets'
    ,'0x7356f09c294cb9c6428ac7327b24b0f29419c181': 'Other short term assets'
    ,'0x3d980e50508cfd41a13837a60149927a11c03731': 'Other short term assets'
    ,'0x671a912c10bba0cfa74cfc2d6fba9ba1ed9530b2': 'Other short term assets'
    ,'0xac1c90b9c76d56ba2e24f3995f7671c745f8f308': 'Other short term assets'
    ,'0x497590d2d57f05cf8b42a36062fa53ebae283498': 'Other short term assets'
    ,'0xfbeb78a723b8087fd2ea7ef1afec93d35e8bed42': 'Other short term assets'
    ,'0x6d765cbe5bc922694afe112c140b8878b9fb0390': 'Other short term assets'
    ,'0xcee60cfa923170e4f8204ae08b4fa6a3f5656f3a': 'Other short term assets'
    ,'0xe537b5cc158eb71037d4125bdd7538421981e6aa': 'Other short term assets'
    ,'0xf29ae508698bdef169b89834f76704c3b205aedf': 'Other short term assets'
    ,'0x56a5fd5104a4956898753dfb060ff32882ae0eb4': 'Other short term assets'
    ,'0xb8c3b7a2a618c552c23b1e4701109a9e756bab67': 'Other short term assets'
    ,'0x27eb83254d900ab4f9b15d5652d913963fec35e3': 'Other short term assets'
    ,'0x27d22a7648e955e510a40bdb058333e9190d12d4': 'Other short term assets'
    ,'0xca3d75ac011bf5ad07a98d02f18225f9bd9a6bdf': 'Other short term assets'
    ,'0x4da27a545c0c5b758a6ba100e3a049001de870f5': 'Other short term assets'
    ,'0x7095472d01a964e50349aa12ce4d5263af77e0d7': 'Other short term assets'
    ,'0x3a68bc59c500de3d5239b5e7f5bdaa1a3bcabba3': 'Other short term assets'
    ,'0xc011a73ee8576fb46f5e1c5751ca3b9fe0af2a6f': 'Other short term assets'
    ,'0x111111111117dc0aa78b770fa6a738034120c302': 'Other short term assets'
    ,'0x514910771af9ca656af840dff83e8264ecf986ca': 'Other short term assets'
    ,'0x0d4ea8536f9a13e4fba16042a46c30f092b06aa5': 'Other short term assets'
    ,'0xd9788f3931ede4d5018184e198699dc6d66c1915': 'Other short term assets'
    ,'0x4a3fe75762017db0ed73a71c9a06db7768db5e66': 'Other short term assets'
    ,'0x92e187a03b6cd19cb6af293ba17f2745fd2357d5': 'Other short term assets'
    ,'0x2ba592f78db6436527729929aaf6c908497cb200': 'Other short term assets'
    ,'0x090185f2135308bad17527004364ebcc2d37e5f6': 'Other short term assets'
    ,'0x5a98fcbea516cf06857215779fd812ca3bef1b32': 'Other short term assets'
    ,'0x63125c0d5cd9071de9a1ac84c400982f41c697ae': 'Other short term assets'
    
    ,'0x1ceb5cb57c4d4e2b2433641b95dd330a33185a44': 'Other long term assets'
    ,'0xaf988afF99d3d0cb870812C325C588D8D8CB7De8': 'Other long term assets'

    ,'0x1abbac88b8f47d46a3d822efa75f64a15c25966f': 'Junk that somehow has value'
    ,'0x55a290f08bb4cae8dcf1ea5635a3fcfd4da60456': 'Junk that somehow has value'
    ,'0xa00c7a61bcbb3f0abcafacd149a3008a153b2dab': 'Junk that somehow has value'
    ,'0x0a24bb4842c301276c65086b5d78d5c872993c72': 'Junk that somehow has value'
    ,'0xe5868468cb6dd5d6d7056bd93f084816c6ef075f': 'Junk that somehow has value'
    ,'0x26004d228fc8a32c5bd1a106108c8647a455b04a': 'Junk that somehow has value'
}