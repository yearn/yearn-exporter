
mapping = {
    "earn": {
        "metric": "iearn",
        "labels": ["vault", "param", "address", "version"],
        "agg_stats": ["total wallets","active wallets","wallets > $5k","wallets > $50k"]
    },
    "ib": {
        "metric": "ironbank",
        "labels": ["vault", "param", "address", "version"],
        "agg_stats": ["total wallets","active wallets","wallets > $5k","wallets > $50k"]
    },
    "v1": {
        "metric": "yearn",
        "labels": ["vault", "param", "address", "version"],
        "agg_stats": ["total wallets","active wallets","wallets > $5k","wallets > $50k"]
    },
    "v2": {
        "metric": "yearn_vault",
        "labels": ["vault", "param", "address", "version", "experimental"],
        "agg_stats": ["total wallets","active wallets","wallets > $5k","wallets > $50k"]
    },
    "v2_strategy": {
        "metric": "yearn_strategy",
        "labels": ["vault", "strategy", "param", "address", "version", "experimental"],
    },
    "special": {
        "metric": "yearn_vault",
        "labels": ["vault", "param", "address", "version", "experimental"],
        "agg_stats": ["total wallets","active wallets","wallets > $5k","wallets > $50k"]
    },
    "yeth": {
        "metric": "yearn_vault",
        "labels": ["vault", "param", "address", "version", "yeth"],
        "agg_stats": ["total wallets","active wallets","wallets > $5k","wallets > $50k"]
    }
}


def _flatten_dict(d):
    def items():
        for key, value in d.items():
            if isinstance(value, dict):
                for subkey, subvalue in _flatten_dict(value).items():
                    yield key + "." + subkey, subvalue
            else:
                yield key, value

    return dict(items())


def _get_label_values(params, inital_labels, experimental = False, yeth = False):
    address = _get_string_label(params, "address")
    version = _get_string_label(params, "version")
    label_values = inital_labels + [address, version]
    if experimental:
        experimental_label = _get_bool_label(params, "experimental")
        label_values.append(experimental_label)
    if yeth:
        yeth_label = _get_bool_label(params, "yeth")
        label_values.append(yeth_label)

    return label_values


def _get_bool_label(a_dict, key):
    return "true" if key in a_dict and a_dict[key] == True else "false"


def _get_string_label(a_dict, key):
    return str(a_dict[key]) if key in a_dict else "n/a"
