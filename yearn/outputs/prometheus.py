from yearn import single_sided_curve
from prometheus_client import Gauge, start_http_server

earn_gauge = Gauge("iearn", "", ["vault", "param", "address", "version"])
ironbank_gauge = Gauge("ironbank", "", ["vault", "param", "address", "version"])
v1_gauge = Gauge("yearn", "", ["vault", "param", "address", "version"])
v2_gauge = Gauge("yearn_vault", "", ["vault", "param", "address", "version", "experimental"])
v2_strategy_gauge = Gauge("yearn_strategy", "", ["vault", "strategy", "param", "address", "version", "experimental"])
simple_gauges = {"v1": v1_gauge, "earn": earn_gauge, "ib": ironbank_gauge, "special": v2_gauge}
single_sided_curve_gauge = Gauge("single_sided_curve", "", ["pool_name", "address", "decimals", "token", "param"])


def start(port):
    start_http_server(port)


def export(data):
    for product, gauge in simple_gauges.items():
        for vault, params in data[product].items():
            for key, value in params.items():
                if key in ["address", "version", "experimental"] or value is None:
                    continue

                has_experiments = product == "special"
                label_values = _get_label_values(params, [vault, key], has_experiments)
                gauge.labels(*label_values).set(value)

    for vault, params in data["v2"].items():
        for key, value in params.items():
            if key in ["address", "version", "experimental", "strategies"] or value is None:
                continue

            label_values = _get_label_values(params, [vault, key], True)
            v2_gauge.labels(*label_values).set(value)

        # strategies can have nested structs
        for strategy, strategy_params in data["v2"][vault]["strategies"].items():
            flat = flatten_dict(strategy_params)
            for key, value in flat.items():
                if key in ["address", "version", "experimental"] or value is None:
                    continue

                label_values = _get_label_values(params, [vault, strategy, key], True)
                v2_strategy_gauge.labels(*label_values).set(value or 0)
    for coin in data["single_sided_curve"]:
        label_values = [coin['pool_name'], coin['address'], coin['decimals'], coin['token'], "ratio"]
        single_sided_curve_gauge.labels(*label_values).set(coin['ratio'] or 0)
        label_values[4] = 'balance'
        single_sided_curve_gauge.labels(*label_values).set(coin['balance'] or 0)
        label_values[4] = 'get_virtual_price'
        single_sided_curve_gauge.labels(*label_values).set(coin['get_virtual_price'] or 0)
        label_values[4] = 'calc_token_amount_deposit'
        single_sided_curve_gauge.labels(*label_values).set(coin['calc_token_amount_deposit'] or 0)
        label_values[4] = 'calc_withdraw_one_coin'
        single_sided_curve_gauge.labels(*label_values).set(coin['calc_withdraw_one_coin'] or 0)


def flatten_dict(d):
    def items():
        for key, value in d.items():
            if isinstance(value, dict):
                for subkey, subvalue in flatten_dict(value).items():
                    yield key + "." + subkey, subvalue
            else:
                yield key, value

    return dict(items())


def _get_label_values(params, inital_labels, experimental=False):
    address = _get_string_label(params, "address")
    version = _get_string_label(params, "version")
    label_values = inital_labels + [address, version]
    if experimental:
        experimental_label = _get_bool_label(params, "experimental")
        label_values.append(experimental_label)

    return label_values


def _get_bool_label(a_dict, key):
    return "true" if key in a_dict and a_dict[key] == True else "false"


def _get_string_label(a_dict, key):
    return a_dict[key] if key in a_dict else "n/a"
