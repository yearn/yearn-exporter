import requests
import os
import math

mapping = {
    "earn": {
        "metric": "iearn",
        "labels": ["vault", "param", "address", "version"]
    },
    "ib": {
        "metric": "ironbank",
        "labels": ["vault", "param", "address", "version"]
    },
    "v1": {
        "metric": "yearn",
        "labels": ["vault", "param", "address", "version"]
    },
    "v2": {
        "metric": "yearn_vault",
        "labels": ["vault", "param", "address", "version", "experimental"]
    },
    "v2_strategy": {
        "metric": "yearn_strategy",
        "labels": ["vault", "strategy", "param", "address", "version", "experimental"]
    },
    "special": {
        "metric": "yearn_vault",
        "labels": ["vault", "param", "address", "version", "experimental"]
    }
}

simple_products = ["v1", "earn", "ib", "special"]

def export(timestamp, data):

    for product in simple_products:
        metric = mapping[product]["metric"]
        for vault, params in data[product].items():

            for key, value in params.items():
                if key in ["address", "version", "experimental"] or value is None:
                    continue

                has_experiments = product == "special"

                label_values = _get_label_values(params, [vault, key], has_experiments)
                label_names = mapping[product]["labels"]
                csv_format = _get_csv_format(label_names, metric)
                csv_payload = _get_csv_payload(label_values, value, timestamp)

                _post(csv_format, csv_payload)

    for vault, params in data["v2"].items():
        metric = mapping["v2"]["metric"]
        for key, value in params.items():
            if key in ["address", "version", "experimental", "strategies"] or value is None:
                continue

            label_values = _get_label_values(params, [vault, key], True)
            label_names = mapping["v2"]["labels"]
            csv_format = _get_csv_format(label_names, metric)
            csv_payload = _get_csv_payload(label_values, value, timestamp)

            _post(csv_format, csv_payload)

        # strategies can have nested structs
        metric = mapping["v2_strategy"]["metric"]
        for strategy, strategy_params in data["v2"][vault]["strategies"].items():
            flat = flatten_dict(strategy_params)
            for key, value in flat.items():
                if key in ["address", "version", "experimental"] or value is None:
                    continue

                label_values = _get_label_values(params, [vault, strategy, key], True)
                label_names = mapping["v2_strategy"]["labels"]
                csv_format = _get_csv_format(label_names, metric)
                csv_payload = _get_csv_payload(label_values, value or 0, timestamp)

                _post(csv_format, csv_payload)


def _post(csv_format, csv_payload):
    base_url = os.environ.get('VM_URL', 'http://victoria-metrics:8428')
    url = f'{base_url}/api/v1/import/csv?format={csv_format}'
    requests.post(
        url = url,
        data = csv_payload
    )


def _get_csv_format(label_names, metric):
    csv_format = []
    i = 0
    for name in label_names:
        i += 1
        csv_format.append(f'{i}:label:{name}')

    i += 1
    csv_format.append(f'{i}:metric:{metric}')
    i += 1
    csv_format.append(f'{i}:time:unix_s')

    return ",".join(map(str, csv_format))


def _get_csv_payload(label_values, value, timestamp):
    csv_payload = []
    for label in label_values:
        csv_payload.append(_sanitize_value(label))

    csv_payload.append(_sanitize_value(value))
    csv_payload.append(math.floor(timestamp))

    return ",".join(map(str, csv_payload))


def _sanitize_value(value):
    v = value
    if type(value) == bool:
        v = 1 if value == True else 0
    elif type(value) == str:
        v = v.replace('"', '') # e.g. '"yvrenBTC" 0.3.5 0x340832'

    return v


def flatten_dict(d):
    def items():
        for key, value in d.items():
            if isinstance(value, dict):
                for subkey, subvalue in flatten_dict(value).items():
                    yield key + "." + subkey, subvalue
            else:
                yield key, value

    return dict(items())


def _get_label_values(params, inital_labels, experimental = False):
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
