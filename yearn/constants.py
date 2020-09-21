from brownie import interface

CONTROLLER_INTERFACES = {
    '0x2be5D998C95DE70D9A38b3d78e49751F10F9E88b': interface.ControllerV1,
    '0x9E65Ad11b299CA0Abefc2799dDB6314Ef2d91080': interface.ControllerV2,
}

VAULT_INTERFACES = {
    '0x29E240CFD7946BA20895a7a02eDb25C210f9f324': interface.yDelegatedVault,
    '0x881b06da56BB5675c54E4Ed311c21E54C5025298': interface.yWrappedVault,
}

STRATEGY_INTERFACES = {
    '0x25fAcA21dd2Ad7eDB3a027d543e617496820d8d6': interface.StrategyVaultUSDC,
    '0xA30d1D98C502378ad61Fe71BcDc3a808CF60b897': interface.StrategyDForceUSDC,
    '0xc999fb87AcA383A63D804A575396F65A55aa5aC8': interface.StrategyCurveYCRVVoter,
    '0x1d91E3F77271ed069618b4BA06d19821BC2ed8b0': interface.StrategyTUSDCurve,
    '0xAa880345A3147a1fC6889080401C791813ed08Dc': interface.StrategyDAICurve,
    '0x787C771035bDE631391ced5C083db424A4A64bD8': interface.StrategyDForceUSDT,
    '0x40BD98e3ccE4F34c087a73DD3d05558733549afB': interface.StrategyCreamYFI,
    '0x2EE856843bB65c244F527ad302d6d2853921727e': interface.StrategyCurveYBUSDVoterProxy,
    '0x4FEeaecED575239b46d70b50E13532ECB62e4ea8': interface.StrategyCurveSBTC,
    '0x932fc4fd0eEe66F22f1E23fBA74D7058391c0b15': interface.StrategyMKRVaultDAIDelegate,
    '0xF147b8125d2ef93FB6965Db97D6746952a133934': interface.CurveYCRVVoter,
    '0x134c08fAeE4F902999a616e31e0B7e42114aE320': interface.StrategyCurveBTCVoterProxy,
}
