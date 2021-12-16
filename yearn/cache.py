from brownie import chain
from joblib import Memory

memory = Memory(f'cache/{chain.id}', verbose=0)
