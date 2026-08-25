-- Week 3 Warehouse Assignment — Answers

-- Q1 — dim_movie
-- One row per movie.
-- imdb_id is the natural key from OMDb and is used for idempotent loading.

CREATE TABLE dim_movie (
    movie_key       SERIAL          PRIMARY KEY,
    imdb_id         VARCHAR(20)     NOT NULL UNIQUE,
    title           VARCHAR(255)    NOT NULL,
    rated           VARCHAR(30),
    plot            TEXT,
    poster_url      TEXT
);

-- Q2 — dim_director
-- Store only the first-listed director from the comma-separated OMDb field.
-- If OMDb contains multiple directors, the loader will keep only the first one.

CREATE TABLE dim_director (
    director_key    SERIAL          PRIMARY KEY,
    name            VARCHAR(255)    NOT NULL UNIQUE

);

-- Store only the first-listed country from the comma-separated OMDb field.
-- If OMDb contains multiple countries, the loader will keep only the first one.

CREATE TABLE dim_country (
    country_key     SERIAL          PRIMARY KEY,
    country_name    VARCHAR(255)    NOT NULL UNIQUE
);

-- Store only the first-listed language from the comma-separated OMDb field.
-- If OMDb contains multiple languages, the loader will keep only the first one.

CREATE TABLE dim_language (
    language_key    SERIAL          PRIMARY KEY,
    language_name   VARCHAR(255)    NOT NULL UNIQUE
);

-- Q3 — dim_genre + bridge_movie_genre
--
-- Genre is modeled as many-to-many because one movie can have multiple
-- genres and one genre can belong to many movies.
--
-- dim_movie cannot simply contain one genre_key because a movie such as
-- "Inception" can belong to multiple genres. A single genre_key would allow
-- only one genre per movie and would cause the other genre relationships
-- to be lost. The bridge table allows one movie to have many genres.

CREATE TABLE dim_genre (
    genre_key       SERIAL          PRIMARY KEY,
    genre_name      VARCHAR(100)    NOT NULL UNIQUE
);

CREATE TABLE bridge_movie_genre (
    movie_key       INTEGER         NOT NULL
                    REFERENCES dim_movie(movie_key),
    genre_key       INTEGER         NOT NULL
                    REFERENCES dim_genre(genre_key),
    PRIMARY KEY (movie_key, genre_key)
);

-- Q4 — dim_certificate
-- Stores the Rated field from OMDb, such as PG-13, R, G, Not Rated, etc.

CREATE TABLE dim_certificate (
    certificate_key SERIAL          PRIMARY KEY,
    code            VARCHAR(30)     NOT NULL UNIQUE
);

-- Q5 — dim_release_date
-- Calendar dimension for movie release dates.
-- date_key uses YYYYMMDD format, for example 19940706.
-- decade stores the first year of the decade, for example 1990 for 1994.

CREATE TABLE dim_release_date (
    date_key        INTEGER         PRIMARY KEY,
    full_date       DATE            NOT NULL UNIQUE,
    year            SMALLINT        NOT NULL,
    decade          SMALLINT        NOT NULL,
    month           SMALLINT        NOT NULL
                    CHECK (month BETWEEN 1 AND 12),
    month_name      VARCHAR(10)     NOT NULL
);

-- Populate dim_release_date
-- Generates one row per calendar day from 1900-01-01 through today.

INSERT INTO dim_release_date (
    date_key,
    full_date,
    year,
    decade,
    month,
    month_name
)

SELECT
    TO_CHAR(d, 'YYYYMMDD')::INTEGER                    AS date_key,
    d::DATE                                            AS full_date,
    EXTRACT(YEAR FROM d)::SMALLINT                    AS year,
    (EXTRACT(YEAR FROM d)::INTEGER / 10 * 10)::SMALLINT     AS decade,
    EXTRACT(MONTH FROM d)::SMALLINT                  AS month,
    TRIM(TO_CHAR(d, 'Month'))                          AS month_name
FROM generate_series(
    '1900-01-01'::DATE,
    CURRENT_DATE,
    '1 day'::INTERVAL
) AS d;

-- Q6 — fact_movie
-- One row per movie.
-- movie_key links the fact to dim_movie.
--
-- Dimension keys are nullable where OMDb can genuinely provide "N/A".
-- movie_key itself is always required because every fact row must correspond
-- to a movie in dim_movie.

CREATE TABLE fact_movie (
    movie_fact_key          SERIAL          PRIMARY KEY,
    movie_key               INTEGER         NOT NULL UNIQUE
                            REFERENCES dim_movie(movie_key),
    director_key            INTEGER
                            REFERENCES dim_director(director_key),
    country_key             INTEGER
                            REFERENCES dim_country(country_key),
    language_key            INTEGER
                            REFERENCES dim_language(language_key),
    certificate_key         INTEGER
                            REFERENCES dim_certificate(certificate_key),
    release_date_key        INTEGER
                            REFERENCES dim_release_date(date_key),
    runtime_minutes         SMALLINT,
    imdb_rating             NUMERIC(3,1),
    imdb_votes              BIGINT,
    metascore               SMALLINT,
    rotten_tomatoes_pct     SMALLINT,
    box_office_usd          NUMERIC(15,2)
);