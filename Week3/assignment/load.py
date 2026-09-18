import json
import logging
import os
from datetime import datetime
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s"
)

logger = logging.getLogger(__name__)
load_dotenv()

DEST_DB_CONFIG = dict(
    host=os.getenv("MOVIE_DB_HOST"),
    port=os.getenv("MOVIE_DB_PORT"),
    dbname=os.getenv("MOVIE_DB_NAME"),
    user=os.getenv("MOVIE_DB_USER"),
    password=os.getenv("MOVIE_DB_PASSWORD")
)

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data" / "raw"

# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------

def clean_na(value):
    """
    Convert OMDb's 'N/A' value into Python None.
    """
    if value == "N/A":
        return None
    return value

def parse_runtime(value):
    """
    Convert '148 min' into integer 148.
    """
    value = clean_na(value)
    if value is None:
        return None
    try:
        return int(value.replace(" min", "").strip())
    except ValueError:
        return None

def parse_integer(value):
    """
    Convert a numeric string into an integer.
    """
    value = clean_na(value)
    if value is None:
        return None
    try:
        return int(value.replace(",", "").strip())
    except ValueError:
        return None

def parse_decimal(value):
    """
    Convert a numeric string into a float.
    """
    value = clean_na(value)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None

def parse_box_office(value):
    """
    Convert '$28,341,469' into 28341469.
    """
    value = clean_na(value)
    if value is None:
        return None
    try:
        return float(
            value.replace("$", "")
                 .replace(",", "")
                 .strip()
        )
    except ValueError:
        return None

def parse_percentage(value):
    """
    Convert '87%' into integer 87.
    """
    value = clean_na(value)
    if value is None:
        return None
    try:
        return int(value.replace("%", "").strip())
    except ValueError:
        return None

def first_value(value):
    """
    Return the first value from a comma-separated OMDb field.
    """
    value = clean_na(value)
    if value is None:
        return None
    return value.split(",")[0].strip()

def parse_release_date(value):
    """
    Convert OMDb's release date string into a Python date.
    """
    value = clean_na(value)
    if value is None:
        return None
    try:
        return datetime.strptime(
            value,
            "%d %b %Y"
        ).date()
    except ValueError:
        return None

def extract_rotten_tomatoes(ratings):
    """
    Find the Rotten Tomatoes rating from the Ratings list.
    """
    if not ratings:
        return None
    for rating in ratings:

        if rating.get("Source") == "Rotten Tomatoes":
            return parse_percentage(
                rating.get("Value")
            )
    return None

# ----------------------------------------------------------------------
# EXTRACT
# ----------------------------------------------------------------------

def extract_raw_movies():
    """
    Read every individual movie JSON file from data/raw/.

    Search result files are skipped because they are not
    individual movie records.
    """

    movies = []

    for file_path in RAW_DIR.glob("*.json"):

        if file_path.name.startswith("search_"):
            continue

        if file_path.name == "_manifest.json":
            continue
        try:
            movie = json.loads(
                file_path.read_text()
            )
            movies.append(movie)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(
                f"Failed to read {file_path}: {e}"
            )
    logger.info(
        f"Extracted {len(movies)} movie records from raw JSON"
    )
    return movies
# ----------------------------------------------------------------------
# TRANSFORM
# ----------------------------------------------------------------------
def transform(raw_movies):
    """
    Transform raw OMDb records into clean warehouse-ready
    Python dictionaries.

    This function does not deal with database surrogate keys.
    """
    transformed_movies = []
    for movie in raw_movies:
        imdb_id = clean_na(
            movie.get("imdbID")
        )
        if imdb_id is None:
            logger.warning(
                "Movie missing imdbID — skipped"
            )
            continue
        # --------------------------------------------------------------
        # Movie dimension
        # --------------------------------------------------------------
        movie_data = {
            "imdb_id": imdb_id,
            "title": clean_na(movie.get("Title")),
            "rated": clean_na(movie.get("Rated")),
            "plot": clean_na(movie.get("Plot")),
            "poster_url": clean_na(movie.get("Poster"))
        }
        # --------------------------------------------------------------
        # Other dimensions
        # --------------------------------------------------------------
        director_name = first_value(movie.get("Director"))
        country_name = first_value(movie.get("Country"))
        language_name = first_value(movie.get("Language"))
        certificate_code = clean_na(movie.get("Rated"))
        # --------------------------------------------------------------
        # Genres
        # --------------------------------------------------------------
        genre_names = []
        genre = clean_na(movie.get("Genre"))
        if genre is not None:
            genre_names = [
                genre_name.strip()
                for genre_name in genre.split(",")
                if genre_name.strip()
            ]
        # --------------------------------------------------------------
        # Release date
        # --------------------------------------------------------------
        release_date = parse_release_date(movie.get("Released"))
        # --------------------------------------------------------------
        # Measures
        # --------------------------------------------------------------
        runtime_minutes = parse_runtime(movie.get("Runtime"))
        imdb_rating = parse_decimal(movie.get("imdbRating"))
        imdb_votes = parse_integer(movie.get("imdbVotes"))
        metascore = parse_integer(movie.get("Metascore"))
        rotten_tomatoes_pct = extract_rotten_tomatoes(movie.get("Ratings"))
        box_office_usd = parse_box_office(movie.get("BoxOffice"))
        # --------------------------------------------------------------
        # Clean transformed structure
        # --------------------------------------------------------------
        transformed_movies.append({
            "movie": movie_data,
            "director_name": director_name,
            "country_name": country_name,
            "language_name": language_name,
            "certificate_code": certificate_code,
            "genre_names": genre_names,
            "release_date": release_date,
            "runtime_minutes": runtime_minutes,
            "imdb_rating": imdb_rating,
            "imdb_votes": imdb_votes,
            "metascore": metascore,
            "rotten_tomatoes_pct": rotten_tomatoes_pct,
            "box_office_usd": box_office_usd
        })

    logger.info(f"Transformed {len(transformed_movies)} movie records")
    return transformed_movies
# ----------------------------------------------------------------------
# LOAD DIMENSIONS
# ----------------------------------------------------------------------
def load_dim_movie(conn, movie):
    """
    Load one movie into dim_movie and return its surrogate key.
    """

    sql = """
        INSERT INTO dim_movie
        (
            imdb_id,
            title,
            rated,
            plot,
            poster_url
        )
        VALUES
        (
            %(imdb_id)s,
            %(title)s,
            %(rated)s,
            %(plot)s,
            %(poster_url)s
        )
        ON CONFLICT (imdb_id)
        DO NOTHING
    """
    with conn.cursor() as curr:
        curr.execute(sql, movie)
        curr.execute(
            """
            SELECT movie_key
            FROM dim_movie
            WHERE imdb_id = %s
            """,
            (movie["imdb_id"],)
        )
        return curr.fetchone()[0]


def load_dim_director(conn, name):
    """
    Load director into dim_director.
    """
    if name is None:
        return None
    sql = """
        INSERT INTO dim_director
        (
            name
        )
        VALUES
        (
            %s
        )
        ON CONFLICT (name)
        DO NOTHING
    """
    with conn.cursor() as curr:
        curr.execute(sql, (name,))

def load_dim_country(conn, name):
    """
    Load country into dim_country.
    """
    if name is None:
        return None
    sql = """
        INSERT INTO dim_country
        (
            country_name
        )
        VALUES
        (
            %s
        )
        ON CONFLICT (country_name)
        DO NOTHING
    """
    with conn.cursor() as curr:
        curr.execute(sql, (name,))


def load_dim_language(conn, name):
    """
    Load language into dim_language.
    """
    if name is None:
        return None
    sql = """
        INSERT INTO dim_language
        (
            language_name
        )
        VALUES
        (
            %s
        )
        ON CONFLICT (language_name)
        DO NOTHING
    """
    with conn.cursor() as curr:
        curr.execute(sql, (name,))

def load_dim_genre(conn, genre_names):
    """
    Load all genres into dim_genre.
    """
    sql = """
        INSERT INTO dim_genre
        (
            genre_name
        )
        VALUES
        (
            %s
        )
        ON CONFLICT (genre_name)
        DO NOTHING
    """
    with conn.cursor() as curr:
        for genre_name in genre_names:
            curr.execute(sql,(genre_name,))

def load_dim_certificate(conn, code):
    """
    Load certificate into dim_certificate.
    """
    if code is None:
        return None
    sql = """
        INSERT INTO dim_certificate
        (
            code
        )
        VALUES
        (
            %s
        )
        ON CONFLICT (code)
        DO NOTHING
    """
    with conn.cursor() as curr:
        curr.execute(sql, (code,))

# ----------------------------------------------------------------------
# LOOKUP TABLE
# ----------------------------------------------------------------------

def load_lookup_dim(conn):
    """
    Load all dimension surrogate keys into memory.
    """
    logger.info(
        "Loading dimension lookups into memory"
    )
    lookup = {}

    with conn.cursor() as curr:
        # Movie
        curr.execute(
            """
            SELECT imdb_id, movie_key
            FROM dim_movie
            """
        )
        lookup["movie"] = {
            row[0]: row[1]
            for row in curr.fetchall()
        }
        # Director
        curr.execute(
            """
            SELECT name, director_key
            FROM dim_director
            """
        )
        lookup["director"] = {
            row[0]: row[1]
            for row in curr.fetchall()
        }
        # Country
        curr.execute(
            """
            SELECT country_name, country_key
            FROM dim_country
            """
        )
        lookup["country"] = {
            row[0]: row[1]
            for row in curr.fetchall()
        }
        # Language
        curr.execute(
            """
            SELECT language_name, language_key
            FROM dim_language
            """
        )
        lookup["language"] = {
            row[0]: row[1]
            for row in curr.fetchall()
        }
        # Genre
        curr.execute(
            """
            SELECT genre_name, genre_key
            FROM dim_genre
            """
        )
        lookup["genre"] = {
            row[0]: row[1]
            for row in curr.fetchall()
        }
        # Certificate
        curr.execute(
            """
            SELECT code, certificate_key
            FROM dim_certificate
            """
        )
        lookup["certificate"] = {
            row[0]: row[1]
            for row in curr.fetchall()
        }
        # Release date
        curr.execute(
            """
            SELECT full_date, date_key
            FROM dim_release_date
            """
        )
        lookup["date"] = {
            row[0]: row[1]
            for row in curr.fetchall()
        }
    return lookup
# ----------------------------------------------------------------------
# TRANSFORM WITH SURROGATE KEYS
# ----------------------------------------------------------------------
def transform_movie(movie, lookups):
    """
    Resolve natural dimension values into warehouse surrogate keys.
    """
    movie_key = lookups["movie"].get(
        movie["movie"]["imdb_id"]
    )
    director_key = lookups["director"].get(
        movie["director_name"]
    )
    country_key = lookups["country"].get(
        movie["country_name"]
    )
    language_key = lookups["language"].get(
        movie["language_name"]
    )
    certificate_key = lookups["certificate"].get(
        movie["certificate_code"]
    )
    release_date_key = lookups["date"].get(
        movie["release_date"]
    )
    genre_keys = []
    for genre_name in movie["genre_names"]:
        genre_key = lookups["genre"].get(genre_name)
        if genre_key is not None:
            genre_keys.append(genre_key)
    return {
        "movie_key": movie_key,
        "director_key": director_key,
        "country_key": country_key,
        "language_key": language_key,
        "certificate_key": certificate_key,
        "release_date_key": release_date_key,
        "genre_keys": genre_keys,
        "runtime_minutes": movie["runtime_minutes"],
        "imdb_rating": movie["imdb_rating"],
        "imdb_votes": movie["imdb_votes"],
        "metascore": movie["metascore"],
        "rotten_tomatoes_pct": movie["rotten_tomatoes_pct"],
        "box_office_usd": movie["box_office_usd"]
    }
# ----------------------------------------------------------------------
# LOAD BRIDGE
# ----------------------------------------------------------------------

def load_bridge_movie_genre(conn, movie_key, genre_keys):
    """
    Load movie-to-genre relationships.
    """
    sql = """
        INSERT INTO bridge_movie_genre
        (
            movie_key,
            genre_key
        )
        VALUES
        (
            %s,
            %s
        )
        ON CONFLICT DO NOTHING
    """
    with conn.cursor() as curr:
        for genre_key in genre_keys:
            curr.execute(sql, (movie_key, genre_key))

# ----------------------------------------------------------------------
# LOAD FACT
# ----------------------------------------------------------------------
def load_fact_movie(conn, movie):
    """
    Load one movie into fact_movie.
    """
    sql = """
        INSERT INTO fact_movie
        (
            movie_key,
            director_key,
            country_key,
            language_key,
            certificate_key,
            release_date_key,
            runtime_minutes,
            imdb_rating,
            imdb_votes,
            metascore,
            rotten_tomatoes_pct,
            box_office_usd
        )
        VALUES
        (
            %(movie_key)s,
            %(director_key)s,
            %(country_key)s,
            %(language_key)s,
            %(certificate_key)s,
            %(release_date_key)s,
            %(runtime_minutes)s,
            %(imdb_rating)s,
            %(imdb_votes)s,
            %(metascore)s,
            %(rotten_tomatoes_pct)s,
            %(box_office_usd)s
        )
        ON CONFLICT (movie_key)
        DO UPDATE SET
            director_key = EXCLUDED.director_key,
            country_key = EXCLUDED.country_key,
            language_key = EXCLUDED.language_key,
            certificate_key = EXCLUDED.certificate_key,
            release_date_key = EXCLUDED.release_date_key,
            runtime_minutes = EXCLUDED.runtime_minutes,
            imdb_rating = EXCLUDED.imdb_rating,
            imdb_votes = EXCLUDED.imdb_votes,
            metascore = EXCLUDED.metascore,
            rotten_tomatoes_pct = EXCLUDED.rotten_tomatoes_pct,
            box_office_usd = EXCLUDED.box_office_usd
    """
    with conn.cursor() as curr:
        curr.execute(sql, movie)
# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------
def main():
    conn = psycopg2.connect(
        **DEST_DB_CONFIG
    )
    try:
        raw_movies = extract_raw_movies()
        movies = transform(raw_movies)
        loaded = 0
        for movie in movies:
            try:
                movie_key = load_dim_movie(conn, movie["movie"])
                load_dim_director(conn, movie["director_name"])
                load_dim_country(conn, movie["country_name"])
                load_dim_language(conn, movie["language_name"])
                load_dim_genre(conn, movie["genre_names"])
                load_dim_certificate(conn, movie["certificate_code"])
                
                lookups = load_lookup_dim(conn)
                
                transformed_movie = transform_movie(movie, lookups)
                
                load_bridge_movie_genre(conn, transformed_movie["movie_key"], transformed_movie["genre_keys"])
                load_fact_movie(conn, transformed_movie)
                conn.commit()
                loaded += 1
                logger.info(f"Loaded movie: "f"{movie['movie']['title']}")
            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to load "f"{movie['movie'].get('title')}: {e}")
        logger.info(f"Movie warehouse load complete: "f"{loaded} movies loaded")
    finally:
        conn.close()

if __name__ == "__main__":
    main()