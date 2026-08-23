"""Create consistent, retention-managed backups of the live SQLite database."""

import argparse
import datetime
import os
import sqlite3
from pathlib import Path


def backup_database(
    source_path: str | Path,
    backup_dir: str | Path,
    keep: int = 14,
    now: datetime.datetime | None = None,
) -> Path:
    source = Path(source_path).resolve()
    destination_dir = Path(backup_dir).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"SQLite database does not exist: {source}")
    if keep < 1:
        raise ValueError("keep must be at least 1")

    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = (now or datetime.datetime.now(datetime.UTC)).astimezone(datetime.UTC)
    stamp = timestamp.strftime("%Y%m%dT%H%M%S%fZ")
    destination = destination_dir / f"{source.stem}-{stamp}.db"
    partial = destination_dir / f".{destination.name}.partial"
    if destination == source or partial == source:
        raise ValueError("Backup destination must differ from the source database")

    source_conn = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    target_conn = sqlite3.connect(partial)
    try:
        source_conn.backup(target_conn)
        result = target_conn.execute("PRAGMA integrity_check").fetchone()
        if result is None or result[0] != "ok":
            raise RuntimeError(f"Backup integrity check failed: {result}")
    finally:
        target_conn.close()
        source_conn.close()

    partial.replace(destination)

    backups = sorted(
        destination_dir.glob(f"{source.stem}-*.db"),
        key=lambda path: path.name,
        reverse=True,
    )
    for expired in backups[keep:]:
        expired.unlink()
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up the Trade Bot Sim SQLite database")
    parser.add_argument("--source", default=os.getenv("DB_PATH", "trade_bot_sim.db"))
    parser.add_argument("--destination", default=os.getenv("BACKUP_DIR", "backups"))
    parser.add_argument("--keep", type=int, default=int(os.getenv("BACKUP_KEEP", "14")))
    args = parser.parse_args()

    destination = backup_database(args.source, args.destination, args.keep)
    print(destination)


if __name__ == "__main__":
    main()
