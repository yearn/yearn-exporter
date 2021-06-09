from typing import Union

from semantic_version import Version

from yearn.v1.vaults import VaultV1
from yearn.v2.vaults import Vault
from yearn.prices.curve import is_curve_lp_token

from yearn.apy import v1
from yearn.apy import v2

from yearn.apy.curve import simple as curve

from yearn.apy.common import ApySamples, get_samples, Apy, ApyError

def calculate_apy(vault: Union[Vault, VaultV1], samples: ApySamples) -> Apy:
    if isinstance(vault, Vault):
        if is_curve_lp_token(vault.token.address):
            return curve.simple(vault, samples)
        elif Version(vault.api_version) >= Version("0.3.2"):
            return v2.average(vault, samples)
        else:
            return v2.simple(vault, samples)
    else:
        if is_curve_lp_token(vault.token.address):
            return curve.simple(vault, samples)
        else:
            return v1.simple(vault, samples)