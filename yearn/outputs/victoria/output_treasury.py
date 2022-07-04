from yearn.outputs.victoria.output_helper import _build_item, _post
from yearn.treasury.buckets import get_token_bucket
from yearn.utils import contract

def export(timestamp, data, label):
    metrics_to_export = []

    for section, section_data in data.items():
        # handle partners data
        if section == 'partners':
            export_partners(timestamp, section_data, label)
            continue

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


def export_partners(timestamp, data, label):
    metrics_to_export = []
    label_names = ['partner', 'param', 'token_address', 'token', 'bucket']
    for partner, partner_data in data.items():
        for wrapper, wrapper_data in partner_data.items():
            # get vault token
            token = wrapper_data.get('vault')
            if token is None:
                continue
            symbol = _get_symbol(token)
            bucket = get_token_bucket(token)

            # wrapper balance
            for key in ['balance', 'balance_usd']:
                item = _build_item(
                    f"{label}_partners",
                    label_names,
                    [partner, key, token, symbol, bucket],
                    wrapper_data.get(key, 0.0),
                    timestamp
                )
                metrics_to_export.append(item)

            # payouts
            payout = wrapper_data.get('payout', {})
            for interval, value in payout.items():
                key = f"payout_{interval}"
                item = _build_item(
                    f"{label}_partners",
                    label_names,
                    [partner, key, token, symbol, bucket],
                    value,
                    timestamp
                )
                metrics_to_export.append(item)
            payout_usd = wrapper_data.get('payout_usd', {})
            for interval, value in payout_usd.items():
                key = f"payout_usd_{interval}"
                item = _build_item(
                    f"{label}_partners",
                    label_names,
                    [partner, key, token, symbol, bucket],
                    value,
                    timestamp
                )
                metrics_to_export.append(item)

    # post all metrics for this timestamp at once
    _post(metrics_to_export)
