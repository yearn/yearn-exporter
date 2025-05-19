from y import Network
from y.constants import CHAINID

from yearn.treasury.accountant.classes import HashMatcher, IterFilter


is_zapper_swap = HashMatcher(
    {
        Network.Mainnet: (
            ("0x22f62d0922c430232aa402296055d79a6cf5c36a8b6253a7f1f46f1e1f66e277", IterFilter("log_index", (34, 58))),
            ("0xec4fbe1320194b94aecb642a833de444a152d46eee969eb4ec1ca92ce1968706", IterFilter('log_index', (100, 129))),
            "0xe5ac989c66e42b8c0a6ea4a138e31ae29511decb7e3a0bdbc1dba61092951dec",
            ("0xa2d59d54bd3df1bd7779b4fe9ffa3bbfbf26a068ff289b05b7e8c91f2a40e91a", IterFilter('log_index', (32, 50))),
            ("0x5cff668fc50705e2bbb69ebe02e0be120a2d83ad02f1d454f52beb3d5386e55e", IterFilter('log_index', (95, 119))),
            ("0x4de98ec72929eeda2f46ce867698bdc90929b4579d16198d609de7f6601dc90f", IterFilter('log_index', (84, 114))),
            ("0xffc1234adfbc26fceb546bcbc4d04a776e094fd9dd1f31683464f1771aeaac25", IterFilter('log_index', (185, 196))),
            ("0x7d319b0fc7e22cd2ac1ad2287ae58760a9ce5eb6b24f6019d0b14f6d201576ed", IterFilter('log_index', (113, 130))),
            ("0xc1ab4ccb2760747d8e0835f86ec2fa00611fa060b4976e94b4d18e66220b53f4", IterFilter('log_index', (76, 87))),
        )
    }.get(CHAINID, ())
).contains

