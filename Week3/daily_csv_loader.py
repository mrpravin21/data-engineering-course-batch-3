import os
import csv
from dotenv import load_dotenv
import logging
import re
from pathlib import Path
import psycopg2
from psycopg2.extras import execute_values

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

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

FILENAME_PATTERN = re.compile(
    r"^rides_(\d{8})\.csv$"
)


# ── SQL ────────────────────────────────────────────────────────────────────

CREATE_TRACKING_TABLE_QUERY = """
    CREATE TABLE IF NOT EXISTS processed_files (
        filename TEXT PRIMARY KEY,
        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        row_count INTEGER
    );
"""


CHECK_PROCESSED_QUERY = """
    SELECT 1
    FROM processed_files
    WHERE filename = %s;
"""


INSERT_RIDES_QUERY = """
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
    VALUES %s
    ON CONFLICT (ride_id) DO NOTHING;
"""


MARK_PROCESSED_QUERY = """
    INSERT INTO processed_files (
        filename,
        row_count
    )
    VALUES (%s, %s);
"""


# ── CSV handling ───────────────────────────────────────────────────────────

def read_csv(filename):
    """Read a rides CSV file and return rows for insertion."""

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
        logger.error(f"Failed to read {filename}: {e}")
        raise

    logger.info(
        f"Read {len(rows):,} rows from {filename}"
    )

    return rows


# ── File discovery ─────────────────────────────────────────────────────────

def find_csv_files():
    """Find valid daily rides CSV files and sort them by date."""

    logger.info(f"Scanning data directory: {DATA_DIR}")

    try:
        files = []

        for path in DATA_DIR.glob("rides_*.csv"):
            match = FILENAME_PATTERN.match(path.name)

            if match:
                file_date = match.group(1)
                files.append((file_date, path))

    except Exception as e:
        logger.error(f"Failed to scan data directory: {e}")
        raise

    files.sort(key=lambda item: item[0])

    logger.info(f"Found {len(files)} valid CSV file(s).")

    return [path for _, path in files]


# ── Database setup ─────────────────────────────────────────────────────────

def create_tracking_table(conn):
    """Create processed_files if it does not already exist."""

    logger.info("Checking processed_files table...")

    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TRACKING_TABLE_QUERY)

    except Exception as e:
        logger.error(
            f"Failed to create/check processed_files table: {e}"
        )
        raise

    conn.commit()

    logger.info("processed_files table is ready.")


# ── Processed-file checking ────────────────────────────────────────────────

def is_file_processed(conn, filename):
    """Return True if the filename already exists in processed_files."""

    logger.info(f"Checking whether {filename} was already processed...")

    try:
        with conn.cursor() as cur:
            cur.execute(
                CHECK_PROCESSED_QUERY,
                (filename,)
            )

            result = cur.fetchone()

    except Exception as e:
        logger.error(
            f"Failed to check processed status for {filename}: {e}"
        )
        raise

    return result is not None


# ── Database insertion ─────────────────────────────────────────────────────

def insert_rows(conn, rows):
    """
    Insert rides using ride_id as an additional duplicate safeguard.

    Returns the number of rows actually inserted.
    """

    logger.info(f"Inserting up to {len(rows):,} ride rows...")

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM rides"
            )

            before_count = cur.fetchone()[0]

            execute_values(
                cur,
                INSERT_RIDES_QUERY,
                rows,
                page_size=1000
            )

            cur.execute(
                "SELECT COUNT(*) FROM rides"
            )

            after_count = cur.fetchone()[0]

    except Exception as e:
        logger.error(f"Failed to insert ride rows: {e}")
        raise

    inserted_count = after_count - before_count

    logger.info(
        f"Inserted {inserted_count:,} new ride rows."
    )

    return inserted_count


def mark_file_processed(conn, filename, row_count):
    """Record a successfully processed file."""

    logger.info(f"Recording processed file: {filename}")

    try:
        with conn.cursor() as cur:
            cur.execute(
                MARK_PROCESSED_QUERY,
                (filename, row_count)
            )

    except Exception as e:
        logger.error(
            f"Failed to record processed file {filename}: {e}"
        )
        raise


# ── Process one file ───────────────────────────────────────────────────────

def process_file(conn, path):
    """
    Load one CSV file and record it as processed.

    The ride insertion and processed_files insertion happen
    inside the same transaction.
    """

    filename = path.name

    logger.info(f"Starting file: {filename}")

    if is_file_processed(conn, filename):
        logger.info(
            f"Skipping {filename}: already processed."
        )
        return

    rows = read_csv(path)

    try:
        inserted_count = insert_rows(conn, rows)

        mark_file_processed(
            conn,
            filename,
            inserted_count
        )

        try:
            conn.commit()

        except Exception as e:
            logger.error(
                f"Failed to commit {filename}: {e}"
            )
            raise

    except Exception as e:
        try:
            conn.rollback()
        except Exception as rollback_error:
            logger.error(
                f"Rollback failed for {filename}: "
                f"{rollback_error}"
            )

        logger.error(
            f"File failed and transaction was rolled back: "
            f"{filename}"
        )
        raise

    logger.info(
        f"Successfully processed {filename}: "
        f"{inserted_count:,} new rows."
    )


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    logger.info("Starting daily incremental CSV loader...")
    logger.info("Connecting to database...")

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False

    except Exception as e:
        logger.critical(
            f"Cannot connect to database: {e}"
        )
        raise

    try:
        create_tracking_table(conn)
        
        # No filename is supplied manually.
        # The loader discovers all daily files automatically,
        # allowing this script to be triggered by cron/scheduler.
        
        files = find_csv_files()

        if not files:
            logger.info("No CSV files found. Nothing to load.")
            return

        for path in files:
            process_file(conn, path)

        logger.info(
            "Daily incremental load completed successfully."
        )

    except Exception as e:
        logger.error(
            f"Daily incremental load failed: {e}"
        )
        raise

    finally:
        conn.close()
        logger.info("Connection closed. Done.")


if __name__ == "__main__":
    main()