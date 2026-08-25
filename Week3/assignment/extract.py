import json
import logging
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s"
)

logger = logging.getLogger(__name__)

load_dotenv()

API_KEY = os.getenv("OMDB_API_KEY")
BASE_URL = "http://www.omdbapi.com/"
RAW_DIR = Path(__file__).parent / "data" / "raw"
MANIFEST_PATH = RAW_DIR / "_manifest.json"
REQUEST_DELAY_SECONDS = 0.5


MOVIES = [
    ("Inception", 2010), ("The Dark Knight", 2008), ("Parasite", 2019), ("Spirited Away", 2001),
    ("The Godfather", 1972), ("Pulp Fiction", 1994), ("Interstellar", 2014), ("The Matrix", 1999),
    ("Titanic", 1997), ("Avengers: Endgame", 2019), ("Whiplash", 2014), ("Coco", 2017), ("Get Out", 2017),
    ("Joker", 2019), ("La La Land", 2016), ("The Shawshank Redemption", 1994), ("Fight Club", 1999),
    ("Gladiator", 2000), ("The Lion King", 1994), ("Toy Story", 1995), ("Forrest Gump", 1994),
    ("The Social Network", 2010), ("Mad Max: Fury Road", 2015), ("Django Unchained", 2012),
    ("Everything Everywhere All at Once", 2022),
]

SEARCH_KEYWORD = "batman"


def load_manifest():
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text())
    return {}

def save_manifest(manifest):
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2)
    )

def fetch_movie(title, year):
    try:
        response = requests.get(
            BASE_URL,
            params={
                "t": title,
                "y": year,
                "apikey": API_KEY
            },
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.error(
            f"Failed to fetch '{title}' ({year}): {exc}"
        )
        return None
    if data.get("Response") != "True":
        logger.error(
            f"OMDb error for '{title}' ({year}): "
            f"{data.get('Error')}"
        )
        return None
    return data

def fetch_search_page(keyword, page):
    try:
        response = requests.get(
            BASE_URL,
            params={
                "s": keyword,
                "page": page,
                "apikey": API_KEY
            },
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.error(
            f"Failed to fetch search page {page} "
            f"for '{keyword}': {exc}"
        )
        return None
    if data.get("Response") != "True":
        logger.error(
            f"OMDb search error for '{keyword}': "
            f"{data.get('Error')}"
        )
        return None
    return data

def extract_movies():
    
    RAW_DIR.mkdir(
        parents=True,
        exist_ok=True
    )
    manifest = load_manifest()
    for title, year in MOVIES:
        manifest_key = f"{title}|{year}"
        if manifest_key in manifest:
            logger.info(f"Skipping already extracted movie: "f"{manifest_key}")
            continue
        movie = fetch_movie(title, year)
        if movie is None:
            time.sleep(REQUEST_DELAY_SECONDS)
            continue
        imdb_id = movie.get("imdbID")
        if not imdb_id:
            logger.error(f"Movie response missing imdbID: "f"{manifest_key}")
            time.sleep(REQUEST_DELAY_SECONDS)
            continue
        output_path = RAW_DIR / f"{imdb_id}.json"
        output_path.write_text(
            json.dumps(movie, indent=2)
        )
        manifest[manifest_key] = imdb_id
        save_manifest(manifest)
        logger.info(
            f"Saved {manifest_key} to {output_path}"
        )
        time.sleep(REQUEST_DELAY_SECONDS)

def extract_search(keyword):
    all_results = []
    page = 1
    total_results = None

    while (total_results is None or len(all_results) < total_results):
        response = fetch_search_page(keyword, page)
        if response is None:
            break
        results = response.get("Search", [])
        if not results:
            break
        all_results.extend(results)
        total_results = int(response.get("totalResults", len(all_results)))
        logger.info(
            f"Fetched search page {page} for "
            f"'{keyword}' "
            f"({len(all_results)}/{total_results} results)"
        )
        page += 1
        if len(all_results) < total_results:
            time.sleep(REQUEST_DELAY_SECONDS)
    output_path = (RAW_DIR / f"search_{keyword}.json")
    output_path.write_text(json.dumps(all_results, indent=2))
    logger.info(
        f"Saved {len(all_results)} search results "
        f"for '{keyword}' to {output_path}"
    )

def main():
    if not API_KEY:
        logger.critical(
            "OMDB_API_KEY not set — "
            "add it to Week3/.env"
        )
        raise SystemExit(1)
    extract_movies()
    extract_search(SEARCH_KEYWORD)
    logger.info("Extraction complete.")

if __name__ == "__main__":
    main()