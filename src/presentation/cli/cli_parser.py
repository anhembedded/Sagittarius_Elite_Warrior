import argparse


def build_parser() -> argparse.ArgumentParser:
    # Use exit_on_error=False (Python 3.9+) so it raises ArgumentError instead of exiting on bad args in the REPL
    parser = argparse.ArgumentParser(description="Binance Trading Bot CLI", exit_on_error=False)
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # sync command
    sync_parser = subparsers.add_parser(
        "sync", help="Synchronize market data from Binance"
    )
    sync_parser.add_argument(
        "--symbols",
        type=str,
        required=True,
        help="Comma separated list of symbols (e.g. BTCUSDT,ETHUSDT)",
    )
    sync_parser.add_argument(
        "--interval",
        type=str,
        default="1m",
        help="Timeframe interval (e.g. 1m, 1h, 1d)",
    )
    sync_parser.add_argument(
        "--days", type=int, default=30, help="Days back to sync if DB is empty"
    )

    # stream command
    stream_parser = subparsers.add_parser(
        "stream", help="Start live websocket market stream"
    )
    stream_parser.add_argument(
        "--symbols",
        type=str,
        required=True,
        help="Comma-separated list of symbols (e.g. BTCUSDT)",
    )
    stream_parser.add_argument(
        "--interval", type=str, required=True, help="Timeframe (e.g. 1m)"
    )
    
    # stop-stream command
    stop_stream_parser = subparsers.add_parser(
        "stop-stream", help="Stop live websocket market stream"
    )

    return parser
