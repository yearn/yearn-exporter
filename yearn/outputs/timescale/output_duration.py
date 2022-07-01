from yearn.outputs.timescale.output_helper import _build_item, _post

def export(duration_seconds, pool_size, direction, timestamp_seconds):
    item = _build_item(
      "export_duration",
      [ "pool_size", "direction" ],
      [ pool_size, direction ],
      duration_seconds,
      timestamp_seconds
    )
    _post([item])
