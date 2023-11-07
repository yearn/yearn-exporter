
from yearn.entities import TreasuryTx

def is_dinobots_rev(tx: TreasuryTx) -> bool:
    return tx.hash in ["0xf1ce47dc8a44fc37ffc580960f22bbe23896cf31bb0484f0cd5d23fc53c4d5fe", "0xa09e8ed14967023a672d332eb620204b20d63c574bc1b7575fc710cdfb794271"]
