#!/usr/bin/env python3
"""
Build / update historical snapshots from the latest scrape.

Reads the current DFW listings and appends a market-level snapshot
+ per-property price/rent tracking to history.json.

Usage:
    python build_history.py                          # uses json/dfw_listings.json
    python build_history.py json/some_other.json     # custom input
"""

import json
import statistics
import sys
import time
from pathlib import Path


def load_history(path: Path) -> dict:
    """Load existing history or create a fresh structure."""
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "snapshots": [],
        "properties": {},  # zpid -> list of {date, price, rent}
    }


def build_snapshot(listings: list[dict], date: str, zipcodes: list[str]) -> dict:
    """Create a market-level summary snapshot."""
    prices = [l["price"] for l in listings if isinstance(l.get("price"), (int, float)) and l["price"] > 0]
    rents = [l["rentZestimate"] for l in listings if isinstance(l.get("rentZestimate"), (int, float)) and l["rentZestimate"] > 0]
    sqft_prices = [
        l["price"] / l["livingArea"]
        for l in listings
        if isinstance(l.get("price"), (int, float)) and l["price"] > 0
        and isinstance(l.get("livingArea"), (int, float)) and l["livingArea"] > 0
    ]

    # Per-zipcode breakdown
    by_zip: dict[str, dict] = {}
    zip_groups: dict[str, list] = {}
    for l in listings:
        zc = str(l.get("zipcode", ""))
        if zc not in zip_groups:
            zip_groups[zc] = []
        zip_groups[zc].append(l)

    for zc, group in sorted(zip_groups.items()):
        zp = [g["price"] for g in group if isinstance(g.get("price"), (int, float)) and g["price"] > 0]
        zr = [g["rentZestimate"] for g in group if isinstance(g.get("rentZestimate"), (int, float)) and g["rentZestimate"] > 0]
        by_zip[zc] = {
            "count": len(group),
            "medianPrice": int(statistics.median(zp)) if zp else 0,
            "medianRent": int(statistics.median(zr)) if zr else 0,
        }

    # Home type breakdown
    by_type: dict[str, int] = {}
    for l in listings:
        ht = l.get("homeType", "Unknown")
        by_type[ht] = by_type.get(ht, 0) + 1

    return {
        "date": date,
        "totalListings": len(listings),
        "medianPrice": int(statistics.median(prices)) if prices else 0,
        "medianRent": int(statistics.median(rents)) if rents else 0,
        "avgPricePerSqFt": round(statistics.mean(sqft_prices), 1) if sqft_prices else 0,
        "minPrice": min(prices) if prices else 0,
        "maxPrice": max(prices) if prices else 0,
        "zipcodes": zipcodes,
        "byZipcode": by_zip,
        "byHomeType": by_type,
    }


def update_property_history(
    history: dict,
    listings: list[dict],
    date: str,
) -> tuple[int, int, int]:
    """Track per-property price & rent changes. Returns (new, updated, price_drops)."""
    props = history.setdefault("properties", {})
    new_count = 0
    updated = 0
    price_drops = 0

    for l in listings:
        zpid = str(l.get("zpid", ""))
        if not zpid:
            continue

        price = l.get("price")
        rent = l.get("rentZestimate")
        if not isinstance(price, (int, float)):
            continue

        entry = {
            "date": date,
            "price": int(price),
            "rent": int(rent) if isinstance(rent, (int, float)) else None,
            "address": l.get("streetAddress", l.get("addressRaw", "")),
            "zipcode": str(l.get("zipcode", "")),
        }

        if zpid not in props:
            props[zpid] = [entry]
            new_count += 1
        else:
            last = props[zpid][-1]
            # Only add if price or rent changed, or it's a new week
            if last["date"] != date:
                props[zpid].append(entry)
                updated += 1
                if entry["price"] < last["price"]:
                    price_drops += 1

    return new_count, updated, price_drops


def main():
    # Input file
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("json/dfw_listings.json")
    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        sys.exit(1)

    data = json.loads(input_path.read_text(encoding="utf-8"))
    listings = data.get("listings", [])
    date = data.get("scraped_at", time.strftime("%Y-%m-%d"))
    zipcodes = data.get("zipcodes", [])

    print(f"Processing {len(listings)} listings from {date}")

    # Load existing history
    history_path = Path("json/history.json")
    history = load_history(history_path)

    # Check if we already have a snapshot for this date
    existing_dates = {s["date"] for s in history["snapshots"]}
    if date in existing_dates:
        print(f"Snapshot for {date} already exists — updating property history only")
    else:
        # Build market snapshot
        snapshot = build_snapshot(listings, date, zipcodes)
        history["snapshots"].append(snapshot)
        history["snapshots"].sort(key=lambda s: s["date"])
        print(f"Added market snapshot for {date}")
        print(f"  Median price: ${snapshot['medianPrice']:,}")
        print(f"  Median rent:  ${snapshot['medianRent']:,}/mo")
        print(f"  Listings:     {snapshot['totalListings']}")

    # Update per-property tracking
    new, updated, drops = update_property_history(history, listings, date)
    print(f"Property tracking: {new} new, {updated} updated, {drops} price drops")

    # Save history
    history_path.write_text(json.dumps(history, indent=2, default=str), encoding="utf-8")
    print(f"Saved → {history_path}")

    # Copy to frontend
    frontend_history = Path("frontend/public/history.json")
    if frontend_history.parent.exists():
        frontend_history.write_text(json.dumps(history, indent=2, default=str), encoding="utf-8")
        print(f"Copied → {frontend_history}")

    # Print price drop alerts
    if drops > 0:
        print(f"\n🔻 {drops} price drops detected:")
        props = history["properties"]
        for zpid, entries in props.items():
            if len(entries) >= 2:
                curr = entries[-1]
                prev = entries[-2]
                if curr["date"] == date and curr["price"] < prev["price"]:
                    drop = prev["price"] - curr["price"]
                    pct = (drop / prev["price"]) * 100
                    addr = curr.get("address", zpid)
                    print(f"  {addr}: ${prev['price']:,} → ${curr['price']:,} (-${drop:,}, -{pct:.1f}%)")


if __name__ == "__main__":
    main()
