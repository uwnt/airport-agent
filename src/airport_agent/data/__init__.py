"""Data layer: fetch public sources, publish small dated snapshots, read them back.

Build a snapshot with `airport-agent refresh [--as-of YYYY-MM]`; read it with
`metrics.airport_metrics`. Snapshots live in the store DATA_STORE names (store.py).
"""
