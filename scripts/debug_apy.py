import os
from yearn.v2.vaults import Vault
from yearn.apy.common import get_samples

def main():
  address = os.getenv("DEBUG_ADDRESS", None)
  if address:
    vault = Vault.from_address(address)
    vault.apy(get_samples())
  else:
    print("no address specified via $DEBUG_ADDRESS")
