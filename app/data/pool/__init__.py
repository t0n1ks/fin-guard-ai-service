"""The companion content pool: data files, one append-only list per bucket.

See model.py for the item model and app/services/pool_picker.py for how
items are chosen without repeats.
"""
from app.data.pool.encouragements import ENCOURAGEMENTS
from app.data.pool.exits import EXITS
from app.data.pool.facts import FACTS
from app.data.pool.jokes import JOKES
from app.data.pool.messages import MESSAGES
from app.data.pool.quota import QUOTA
from app.data.pool.tips import TIPS

# Bucket name (seen_store.BUCKETS) → its items.
BUCKET_ITEMS = {
    "jokes": JOKES,
    "facts": FACTS,
    "tips": TIPS,
    "exits": EXITS,
    "quota": QUOTA,
    "encouragements": ENCOURAGEMENTS,
}

__all__ = ["BUCKET_ITEMS", "ENCOURAGEMENTS", "EXITS", "FACTS", "JOKES", "MESSAGES", "QUOTA", "TIPS"]
