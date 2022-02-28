from yearn.outputs.victoria.output_helper import _build_item, _post
from yearn.treasury.buckets import get_token_bucket
from yearn.utils import contract

def export(timestamp, data, label):
    metrics_to_export = []
    for section, section_data in data.items():
        for wallet, wallet_data in section_data.items():
            for token, bals in wallet_data.items():
                symbol = _get_symbol(token)
                bucket = get_token_bucket(token)
                for key, value in bals.items():
                    label_names = ['param','wallet','token_address','token','bucket']
                    label_values = [key,wallet,token,symbol,bucket]
                    item = _build_item(f"{label}_{section}",label_names,label_values,value,timestamp)
                    metrics_to_export.append(item)
    
    # post all metrics for this timestamp at once
    _post(metrics_to_export)

def _get_symbol(token):
    if token == 'ETH':
        return 'ETH'
    try:
        return contract(token).symbol()
    except AttributeError:
        return None