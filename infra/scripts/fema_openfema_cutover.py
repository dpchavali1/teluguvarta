"""One-off: move the FEMA source from its RSS feed to the OpenFEMA API.

The RSS feed sent bare disaster numbers as titles ("1", "100") with 2004 dates,
which filled the review queue. This deletes the unpublished stories built only
from those RSS items, deletes the RSS items nothing references any more, and
points the source at the API (`app.adapters.openfema.retire_legacy_feed_items`).
Published or mixed stories are kept and counted.

Dry run by default: prints what it would do and rolls back. `--apply` commits
and writes an audit event. Safe to rerun. It does not reactivate the source;
do that in admin afterwards.

    DATABASE_URL=... python infra/scripts/fema_openfema_cutover.py [--apply]
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not set.", file=sys.stderr)
        return 1
    apply = "--apply" in sys.argv[1:]

    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.adapters.openfema import retire_legacy_feed_items
    from app.models import AuditEvent, Source

    with Session(create_engine(database_url)) as db:
        sources = db.scalars(select(Source).where(Source.base_url == "https://www.fema.gov")).all()
        if len(sources) != 1:
            print(f"Expected exactly one FEMA source, found {len(sources)}.", file=sys.stderr)
            return 1
        source = sources[0]
        old_feed_url = source.feed_url
        summary = retire_legacy_feed_items(db, source)
        print(f"{source.name} ({source.id}): feed_url {old_feed_url} -> {source.feed_url}")
        for key, value in summary.items():
            print(f"  {key}: {value}")
        if not apply:
            db.rollback()
            print("Dry run: rolled back. Rerun with --apply to commit.")
            return 0
        db.add(
            AuditEvent(
                actor="script:fema_openfema_cutover",
                action="SOURCE_UPDATED",
                entity_type="source",
                entity_id=source.id,
                metadata_={"feed_url": source.feed_url, "old_feed_url": old_feed_url, **summary},
            )
        )
        db.commit()
        print("Committed. Set the source active in admin to start fetching.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
