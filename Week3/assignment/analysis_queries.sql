-- Week 3 Warehouse Assignment — Analytical Queries
-- Run these against your loaded movie_dw. See warehouse_assignment.md for the full scenario text.


-- Q8 — Best-rated movie per genre (Intermediate · Window functions)
-- genre_name, title, imdb_rating — one row per genre, the single highest-rated movie in it

WITH ranked_movies AS (
    SELECT
        g.genre_name,
        m.title,
        f.imdb_rating,
        ROW_NUMBER() OVER (
            PARTITION BY g.genre_key
            ORDER BY f.imdb_rating DESC NULLS LAST
        ) AS rank
    FROM bridge_movie_genre bmg
    JOIN dim_genre g
        ON bmg.genre_key = g.genre_key
    JOIN dim_movie m
        ON bmg.movie_key = m.movie_key
    JOIN fact_movie f
        ON m.movie_key = f.movie_key
)
SELECT
    genre_name,
    title,
    imdb_rating
FROM ranked_movies
WHERE rank = 1
ORDER BY genre_name;

-- Q9 — Average rating by decade (Basic–Intermediate · Aggregation)
-- decade, movie_count, avg_imdb_rating (2 decimals) — one row per decade, sorted chronologically

SELECT
    d.decade, COUNT(f.movie_key) AS movie_count, ROUND(AVG(f.imdb_rating), 2) AS avg_imdb_rating
FROM fact_movie f
JOIN dim_release_date d
    ON f.release_date_key = d.date_key
GROUP BY d.decade
ORDER BY d.decade;

-- Q10 — Directors with the highest average box office (Intermediate · Aggregation + filtering)
-- director_name, movies_loaded, avg_box_office_usd — only directors with 2+ movies loaded,
-- sorted by avg_box_office_usd descending

SELECT
    d.name AS director_name, COUNT(f.movie_key) AS movies_loaded, ROUND(AVG(f.box_office_usd), 2) AS avg_box_office_usd
FROM fact_movie f
JOIN dim_director d
    ON f.director_key = d.director_key
WHERE f.box_office_usd IS NOT NULL
GROUP BY d.director_key, d.name
HAVING COUNT(f.movie_key) >= 2
ORDER BY avg_box_office_usd DESC;