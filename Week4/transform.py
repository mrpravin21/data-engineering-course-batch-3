import logging
logger = logging.getLogger(__name__)


def transform(oltp_row, lookups):
    fact_rows = []
    skipped = 0
    for row in oltp_row:
        trip_id = row["trip_id"]
        if row["requested_at"] is None:
            logger.warning(f"trip {trip_id}: requested_at is NULL — skipped")
            skipped += 1
            continue

        # ── Date Key ──────────────────────────────────────────────────────────
        date_key = int(row["requested_at"].strftime("%Y%m%d"))
        if date_key not in lookups["date"]:
            logger.warning(f"trip {trip_id}: date_key {date_key} outside of dim_date range — skipped")
            skipped += 1
            continue

        # ── Time Key ──────────────────────────────────────────────
        req_time = row["requested_at"]
        # Round down minutes to the nearest 15-minute bucket (0, 15, 30, 45)
        minute_bucket = (req_time.minute // 15) * 15
        time_key = (req_time.hour * 100) + minute_bucket

        if time_key not in lookups["time"]:
            logger.warning(f"trip {trip_id}: time_key {time_key} not found in dim_time — skipped")
            skipped += 1
            continue

        # ── Dimension Lookups ─────────────────────────────────────────────────
        driver_key = lookups["driver"].get(row["driver_id"])
        if driver_key is None:
            logger.warning(f"trip {trip_id}: driver_id {row['driver_id']} not in dim_driver — skipped")
            skipped += 1
            continue

        passenger_key = lookups["passenger"].get(row["passenger_id"])
        if passenger_key is None:
            logger.warning(f"trip {trip_id}: passenger_id {row['passenger_id']} not in dim_passenger — skipped")
            skipped += 1
            continue

        pickup_location_key = lookups["location"].get(row["pickup_location_id"])
        if pickup_location_key is None:
            logger.warning(f"trip {trip_id}: pickup_location_id {row['pickup_location_id']} not in dim_location — skipped")
            skipped += 1
            continue

        dropoff_location_key = lookups["location"].get(row["dropoff_location_id"])
        if dropoff_location_key is None:
            logger.warning(f"trip {trip_id}: dropoff_location_id {row['dropoff_location_id']} not in dim_location — skipped")
            skipped += 1
            continue

        payment_method_key = None
        if row["payment_method_id"] is not None:
            payment_method_key = lookups["payment_method"].get(row["payment_method_id"])
            if payment_method_key is None:
                logger.warning(f"trip {trip_id}: payment_method_id {row['payment_method_id']} not in dim_payment_method — skipped")
                skipped += 1
                continue

        promo_code_key = None
        if row["promo_code_id"] is not None:
            promo_code_key = lookups["promo_code"].get(row["promo_code_id"])
            if promo_code_key is None:
                logger.warning(f"trip {trip_id}: promo_code_id {row['promo_code_id']} not in dim_promo_code — skipped")
                skipped += 1
                continue

        # ── Measures ──────────────────────────────────────────────────────────
        base_fare = row['base_fare'] or 0
        tip_amount = row["tip_amount"] or 0
        surge_multiplier = row["surge_multiplier"] or 0
        discount_amount = row["discount_amount"] or 0
        fare_amount  = round(base_fare * surge_multiplier + tip_amount - discount_amount, 2)

        duration_minutes = None
        if row["status"] == "completed" and row["completed_at"]:
            delta = row["completed_at"] - row["requested_at"]
            duration_minutes = round(delta.total_seconds() / 60, 1)

        # ── Output Map ────────────────────────────────────────────────────────
        fact_rows.append({
            "source_trip_id":       trip_id,
            "date_key":             date_key,
            "time_key":             time_key,
            "driver_key":           driver_key,
            "passenger_key":        passenger_key,
            "pickup_location_key":  pickup_location_key,
            "dropoff_location_key": dropoff_location_key,
            "payment_method_key":   payment_method_key,
            "promo_code_key":       promo_code_key,
            "base_fare":            base_fare,
            "tip_amount":           tip_amount,
            "discount_amount":      discount_amount,
            "fare_amount":          fare_amount,
            "distance_km":          row["distance_km"],
            "duration_minutes":     duration_minutes,
            "driver_rating":        row["driver_rating"],
            "passenger_rating":     row["passenger_rating"],
            "surge_multiplier":     surge_multiplier,
            "requested_at":         row["requested_at"],
        })

    logger.info(f"Transformed {len(fact_rows)} rows, skipped {skipped}")
    return fact_rows
