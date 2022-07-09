from yearn.outputs.timescale.output_helper import mapping, _get_label_values, _build_item, _post

def export(timestamp, data):
    metrics_to_export = []
    for key, value in data['agg_stats'].items():
        if key == 'wallet balances usd':
            for wallet, usd_bal in value.items():
                label_names = ["param","wallet"]
                label_values = ["balance usd",wallet]
                item = _build_item("aggregate", label_names, label_values, usd_bal, timestamp)
                metrics_to_export.append(item)
            continue
        label_names = ['param']
        label_values = [key]
        item = _build_item("aggregate", label_names, label_values, value, timestamp)
        metrics_to_export.append(item)
    for key in data.keys():
        if key == 'agg_stats':
            continue
        product = key
        metric = mapping[product]["metric"]
        for key, value in data[product].items():
            if key in mapping[product]["agg_stats"]:
                label_names = ['param']
                label_values = [key]
                item = _build_item(metric, label_names, label_values, value, timestamp)
                metrics_to_export.append(item)
                continue
            elif key == "wallet balances usd":
                for wallet, usd_bal in value.items():
                    label_names = ["param","wallet"]
                    label_values = ["balance usd",wallet]
                    item = _build_item(metric, label_names, label_values, usd_bal, timestamp)
                    metrics_to_export.append(item)
                continue
            
            vault, params = key, value
            for k, v in params.items():
                if k == 'wallet balances':
                    for wallet, bals in v.items():
                        for denom, bal in bals.items():
                            label_values = [wallet] + _get_label_values(params, [vault, denom], product in ['v2','special'])
                            label_names = ["wallet"] + mapping[product]["labels"]
                            item = _build_item(metric, label_names, label_values, bal, timestamp)
                            metrics_to_export.append(item)
                    continue

                label_values = _get_label_values(params, [vault, k], True)
                label_names = mapping[product]["labels"]

                item = _build_item(metric, label_names, label_values, v, timestamp)
                metrics_to_export.append(item)

    # post all wallet metrics for this timestamp at once
    _post(metrics_to_export)
