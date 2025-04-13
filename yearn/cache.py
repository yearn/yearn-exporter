from joblib import Memory
from y.constants import CHAINID

memory = Memory(f'cache/{CHAINID}', verbose=0)
