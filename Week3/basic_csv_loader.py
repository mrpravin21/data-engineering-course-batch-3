import csv
import logging
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
import os

load_dotenv()

# ── Logging setup ──────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("pipeline.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


# ── Database config ────────────────────────────────────────────────────────

DB_CONFIG = {
    "host":    os.getenv("DB_HOST", "localhost"),
    "port":     os.getenv("DB_PORT", 5432),
    "dbname":   os.getenv("DB_NAME", "ride_share"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}

# ── Configuration ──────────────────────────────────────────────────────────

CSV_FILE = "Week1/rides.csv"


# ── SQL ────────────────────────────────────────────────────────────────────

TRUNCATE_QUERY = """
    TRUNCATE TABLE rides;
"""

INSERT_QUERY = """
    INSERT INTO rides (
        ride_id,
        driver_name,
        passenger_name,
        pickup_city,
        dropoff_city,
        fare_amount,
        ride_distance_km,
        ride_status,
        requested_at,
        completed_at,
        rating,
        payment_method
    )
    VALUES %s;
"""


def load_csv(filename):
    """Read the CSV file and return rows suitable for database insertion."""

    logger.info(f"Reading CSV file: {filename}")

    try:
        rows = []

        with open(filename, "r", newline="", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)

            for row in reader:
                rows.append((
                    int(row["ride_id"]),
                    row["driver_name"],
                    row["passenger_name"],
                    row["pickup_city"],
                    row["dropoff_city"],
                    row["fare_amount"],
                    row["ride_distance_km"],
                    row["ride_status"],
                    row["requested_at"],
                    row["completed_at"] or None,
                    row["rating"] or None,
                    row["payment_method"] or None,
                ))

    except Exception as e:
        logger.error(f"Failed to read CSV file: {e}")
        raise

    logger.info(f"CSV file read successfully: {len(rows):,} rows")

    return rows


def truncate_rides(conn):
    """Truncate the original rides table."""

    logger.info("Truncating original rides table...")

    try:
        with conn.cursor() as cur:
            cur.execute(TRUNCATE_QUERY)

    except Exception as e:
        logger.error(f"Failed to truncate rides table: {e}")
        raise

    logger.info("rides table truncated successfully.")


def insert_rows(conn, rows):
    """Insert CSV rows into the rides table."""

    logger.info(f"Inserting {len(rows):,} rows into rides...")

    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                INSERT_QUERY,
                rows,
                page_size=1000
            )

    except Exception as e:
        logger.error(f"Failed to insert rows: {e}")
        raise

    logger.info(f"Successfully inserted {len(rows):,} rows.")


def main():
    logger.info("Starting basic CSV load...")
    logger.info("Connecting to database...")

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False

    except Exception as e:
        logger.critical(f"Cannot connect to database: {e}")
        raise

    try:

        rows = load_csv(CSV_FILE)

        truncate_rides(conn)
        insert_rows(conn, rows)

        try:
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to commit transaction: {e}")
            raise

        logger.info("Transaction committed successfully.")
        logger.info("Basic CSV load completed successfully.")

    except Exception as e:
        try:
            conn.rollback()
        except Exception as rollback_error:
            logger.error(f"Rollback failed: {rollback_error}")

        logger.error(f"Basic CSV load failed: {e}")
        raise

    finally:
        conn.close()
        logger.info("Connection closed. Done.")


if __name__ == "__main__":
    main()
    
    
