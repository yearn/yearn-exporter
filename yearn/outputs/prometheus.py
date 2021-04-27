from prometheus_client import Gauge, start_http_server

earn_gauge = Gauge("iearn", "", ["vault", "param"])
ironbank_gauge = Gauge("ironbank", "", ["vault", "param"])
v1_gauge = Gauge("yearn", "", ["vault", "param"])
v2_gauge = Gauge("yearn_vault", "", ["vault", "param"])
v2_strategy_gauge = Gauge("yearn_strategy", "", ["vault", "strategy", "param"])
simple_gauges = {"v1": v1_gauge, "earn": earn_gauge, "ib": ironbank_gauge}


def start(port):
    start_http_server(port)


def export(data):
    for product, gauge in simple_gauges.items():
        for vault, params in data[product].items():
            for key, value in params.items():
                if value is None:
                    continue
                gauge.labels(vault, key).set(value)

    for vault, params in data["v2"].items():
        for key, value in params.items():
            if key == "strategies" or value is None:
                continue
            v2_gauge.labels(vault, key).set(value)

        # strategies can have nested structs
        for strategy, strategy_params in data["v2"][vault]["strategies"].items():
            flat = flatten_dict(strategy_params)
            for key, value in flat.items():
                if value is None:
                    continue
                v2_strategy_gauge.labels(vault, strategy, key).set(value or 0)


def flatten_dict(d):
    def items():
        for key, value in d.items():
            if isinstance(value, dict):
                for subkey, subvalue in flatten_dict(value).items():
                    yield key + "." + subkey, subvalue
            else:
                yield key, value

    return dict(items())
