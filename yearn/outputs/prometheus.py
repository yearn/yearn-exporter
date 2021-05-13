from prometheus_client import Gauge, start_http_server

earn_gauge = Gauge("iearn", "", ["vault", "param"])
ironbank_gauge = Gauge("ironbank", "", ["vault", "param"])
v1_gauge = Gauge("yearn", "", ["vault", "param"])
v2_gauge = Gauge("yearn_vault", "", ["vault", "param", "experimental"])
v2_strategy_gauge = Gauge("yearn_strategy", "", ["vault", "strategy", "param", "experimental"])
simple_gauges = {"v1": v1_gauge, "earn": earn_gauge, "ib": ironbank_gauge, "special": v2_gauge}


def start(port):
    start_http_server(port)


def export(data):
    for product, gauge in simple_gauges.items():
        for vault, params in data[product].items():
            for key, value in params.items():
                if value is None:
                    continue
                label_values = [vault, key]
                if product == "special":
                    experimental = _get_bool_label(params, "experimental")
                    label_values.append(experimental)
                gauge.labels(*label_values).set(value)

    for vault, params in data["v2"].items():
        for key, value in params.items():
            if key == "strategies" or value is None:
                continue
            experimental = _get_bool_label(params, "experimental")
            label_values = [vault, key, experimental]
            v2_gauge.labels(*label_values).set(value)

        # strategies can have nested structs
        for strategy, strategy_params in data["v2"][vault]["strategies"].items():
            flat = flatten_dict(strategy_params)
            for key, value in flat.items():
                if value is None:
                    continue
                experimental = _get_bool_label(params, "experimental")
                label_values = [vault, strategy, key, experimental]
                v2_strategy_gauge.labels(*label_values).set(value or 0)


def flatten_dict(d):
    def items():
        for key, value in d.items():
            if isinstance(value, dict):
                for subkey, subvalue in flatten_dict(value).items():
                    yield key + "." + subkey, subvalue
            else:
                yield key, value

    return dict(items())

def _get_bool_label(a_dict, key):
    return "true" if key in a_dict and a_dict[key] == True else "false"
