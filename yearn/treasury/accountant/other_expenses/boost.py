from yearn.entities import TreasuryTx


def is_buying_crv_for_boost(tx: TreasuryTx) -> bool:
    return (
        (tx._symbol == "DAI" and tx._to_nickname == "CRV Buyer Contract (DAI)")
        or (tx._symbol == "CRV" and tx._from_nickname == "CRV Buyer Contract (DAI)")
    ) or (
        (tx._symbol == "USDT" and tx._to_nickname == "CRV Buyer Contract (USDT)")
        or (tx._symbol == "CRV" and tx._from_nickname == "CRV Buyer Contract (USDT)")
    ) or "0x3D71d79C224998E608d03C5Ec9B405E7a38505F0" in (tx.to_address.address, tx.from_address.address) or tx.hash in {
        # bought via some multi-token buyer contract that probably doesnt need hueristics
        "0x2391a566b567528ad838169804c77b67ee9724acd174ae6d8a5ebbb715870c35",
        "0xd04e5b2b19b2e88d72426d08cb04a54b64d788309787caacfcdb0a4bd440503f",
        "0x000f6a0140da4a5c70e671523c8b8406ee8353c973b700dcc575ca1f347628af",
        "0x8d7e61b2c6b4e3554258c0f383baee9afc26f60a01d5cdc4a178840f9b506cce",
        "0x2ebb191b54e7b2d9916d36462a211e416781a873bac630c32c5e771192410e14",
        "0x4a8a8ddbca5b4debdc298c3ed39149f8933b79b937aa71b9e8d969c5fd691865",
        # and these from some different one
        "0xb87eb568fb662b28b61bfb4fa477d6db59e8c5c0eb8107cb5f7aa6ad0be4292c",
        "0xe2d6420b3eae91634e6b06f4c1d2d7e25e5277f7f945c98731daccb005513f11",
        "0xd5b506d20d35daf583350d5f7cfbf8f827cbe78326d36dbf02bbbbede7bbb0b2",
        "0x54e88407a9a7161bc259b1d9193a0cec8152c976cf985ccdd9ab1c23e80ce112",
        "0x6fd9d2da32a1b5b4b9e61a1659900ebb54c45b2a6254d79d84cb8cd9fe06c474",
        # and another
        "0x3fa631fe04338ffd71d07c05d5a6d93c4f8c6bbe435a0af17bf819e43d31f8b3",
        "0xf5aa2466338bb9d134c7a7dfe9a42aefa4348684ce2fab3ce655acf5925da8fe",
        "0xc945264eef9e494251bdc3c23147fa7fde7c4115f94c8feae9826bc06dd0338c",
        "0x7c365f0afa683727163ee627e5cdab607be70e1c6beee3e3d0c2e35b0e366bde",
        "0xf0a946524c4b244b626bdddb9ef07051a3252dfa18caac7a8e66ec365655a15f",
        "0xc8ac7d1ec0631723846e170fb22aab5881c15ccf4fdae15dbe283cd38d782ea7",
        # bought via 0x protocol
        "0x2367da0c38d9c5b7fb0e422ce364ae9c8fbb74567a96f94078c58d9f9e0809ac",
        "0x2f5c5e6ba0633d097c99d0bf64e4a96f5f440c6eab2197565e83435f96473ed1",
        "0xcf2f0cfe8c5a1b848b57d5cebd5375335ae889f2075373e23f50a3c65a03b2b2",
    }
