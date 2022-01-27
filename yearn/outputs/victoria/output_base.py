from yearn.outputs.victoria.output_helper import mapping, _get_label_values, _build_item, _post, _flatten_dict
from brownie import chain
from yearn.prices import constants
from yearn.networks import Network

def export(block, timestamp, data):
    metrics_to_export = []

    if Network(chain.id) == Network.Fantom:
        simple_products = ["ib"]
    else:
        simple_products = ["v1", "earn", "ib", "special"]

    for product in simple_products:
        metric = mapping[product]["metric"]
        for vault, params in data[product].items():

            for key, value in params.items():
                if key in ["address", "version", "experimental"] or value is None:
                    continue

                has_experiments = product == "special"

                label_values = _get_label_values(params, [vault, key], has_experiments)
                label_names = mapping[product]["labels"]

                if product == "ib" and key == 'tvl' and block >= constants.ib_snapshot_block:
                    # create one item with tvl=0 that will be used in existing dashboards
                    item_legacy = _build_item(metric, label_names, label_values, 0, timestamp)
                    metrics_to_export.append(item_legacy)
                    # create a second item to track ib tvl separately
                    item_own = _build_item(f'{metric}_own', label_names, label_values, value, timestamp)
                    metrics_to_export.append(item_own)
                else:
                    item = _build_item(metric, label_names, label_values, value, timestamp)
                    metrics_to_export.append(item)

    for vault, params in data["v2"].items():
        metric = mapping["v2"]["metric"]
        for key, value in params.items():
            if key in ["address", "version", "experimental", "strategies"] or value is None:
                continue

            label_values = _get_label_values(params, [vault, key], True)
            label_names = mapping["v2"]["labels"]

            item = _build_item(metric, label_names, label_values, value, timestamp)
            metrics_to_export.append(item)

        # strategies can have nested structs
        metric = mapping["v2_strategy"]["metric"]
        for strategy, strategy_params in data["v2"][vault]["strategies"].items():
            flat = _flatten_dict(strategy_params)
            for key, value in flat.items():
                if key in ["address", "version", "experimental"] or value is None:
                    continue

                label_values = _get_label_values(params, [vault, strategy, key], True)
                label_names = mapping["v2_strategy"]["labels"]

                item = _build_item(metric, label_names, label_values, value or 0, timestamp)
                metrics_to_export.append(item)

    # post all metrics for this timestamp at once
    _post(metrics_to_export)
