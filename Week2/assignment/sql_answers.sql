-- Week 2 SQL Assignment — Answers
-- Fill in each query below. See sql_assignment.md for the full scenario text.
-- Rename this file to sql_answers.sql before committing.


-- Q1 — Standardizing driver names from the raw feed (Basic · String functions)
-- Distinct, cleaned driver_name from rides — one column: clean_driver_name

SELECT DISTINCT INITCAP(LOWER(TRIM(driver_name))) AS clean_driver_name
FROM rides;

-- Q2 — Every payment method actually in use (Basic · String functions)
-- Distinct, lowercased payment_method from rides, sorted alphabetically

SELECT DISTINCT LOWER(COALESCE(NULLIF(TRIM(payment_method), ''), 'unknown')) AS payment_method
FROM rides
ORDER BY payment_method;


-- Q3 — A readable log of every completed trip (Basic · Joins)
-- driver_name, passenger_name, pickup_city, dropoff_city, fare_amount, requested_at
-- Join locations twice (pickup + dropoff) with separate aliases

SELECT d.name AS driver_name,
       p.name AS passenger_name,
       pl.city_name AS pickup_city,
       dl.city_name AS dropoff_city,
       t.fare_amount AS fare_amount,
       t.requested_at AS requested_at
FROM trips t
JOIN drivers d ON t.driver_id = d.driver_id
JOIN passengers p ON t.passenger_id = p.passenger_id
JOIN locations pl ON t.pickup_location_id = pl.location_id
JOIN locations dl ON t.dropoff_location_id = dl.location_id
WHERE LOWER(TRIM(t.status))= LOWER(TRIM('completed'))

-- Q4 — Drivers who have never driven a single trip (Basic–Intermediate · Joins)
-- driver_name — drivers with zero rows in trips at all
-- Comment: why can't INNER JOIN answer this?

SELECT d.name AS driver_name
FROM drivers d
LEFT JOIN trips t ON d.driver_id = t.driver_id
WHERE t.driver_id IS NULL;
-- (In this case, an INNER JOIN cannot answer the question 
--because it only returns rows where there is a match in both tables. 
--Since we are looking for drivers who have never driven a single trip, 
--we need to use a LEFT JOIN to include all drivers
-- and then filter out those who have trips by checking for NULL values in the trips table.)


-- Q5 — Payment methods nobody has ever used (Intermediate · Joins)
-- payment_method_id, name — payment methods with zero trips
-- Comment: which join type / FROM table if written the other way around?

SELECT pm.payment_method_id AS payment_method_id, pm.name AS name
FROM payment_methods pm
LEFT JOIN trips t ON pm.payment_method_id = t.payment_method_id
WHERE t.payment_method_id IS NULL;
-- (If we were to write the query the other way around,we would use a RIGHT JOIN instead of a LEFT JOIN.
-- In that case, we would start with the trips table and join it to the payment_methods table, 
--and then filter for NULL values in the payment_methods table to find payment methods that have never been used.)


-- Q6 — Numbering each driver's trips in order (Basic–Intermediate · Window functions)
-- driver_name, requested_at, fare_amount, trip_number (ROW_NUMBER per driver)

SELECT d.name AS driver_name, t.requested_at AS requested_at, t.fare_amount AS fare_amount,
       ROW_NUMBER() OVER (PARTITION BY d.driver_id ORDER BY t.requested_at) AS trip_number
FROM trips t
JOIN drivers d ON t.driver_id = d.driver_id

-- Q7 — Each driver's running earnings (Intermediate · Window functions)
-- driver_name, requested_at, fare_amount, running_total (cumulative SUM per driver)

SELECT d.name AS driver_name, t.requested_at AS requested_at, t.fare_amount AS fare_amount,
       SUM(t.fare_amount) OVER (PARTITION BY d.driver_id ORDER BY t.requested_at) AS running_total
FROM trips t
JOIN drivers d ON t.driver_id = d.driver_id

-- Q8 — Each driver's single highest-fare trip, without a subquery (Intermediate · Window functions)
-- driver_name, trip_id, fare_amount — one row per driver, via RANK()/ROW_NUMBER() + CTE

SELECT driver_name, trip_id, fare_amount
FROM (
    SELECT d.name AS driver_name, t.trip_id AS trip_id, t.fare_amount AS fare_amount,
           ROW_NUMBER() OVER (PARTITION BY d.driver_id ORDER BY t.fare_amount DESC) AS row_number
    FROM trips t
    JOIN drivers d ON t.driver_id = d.driver_id
) ranked_trips
WHERE row_number = 1;

-- Q9 — Driver performance scorecard (Intermediate · Conditional aggregation)
-- driver_name, total_trips, completed_trips, cancelled_trips, cancellation_rate, avg_rating

SELECT d.name AS driver_name,
       COUNT(t.trip_id) AS total_trips,
       COUNT(CASE WHEN LOWER(TRIM(t.status)) = 'completed' THEN 1 END) AS completed_trips,
       COUNT(CASE WHEN LOWER(TRIM(t.status)) = 'cancelled' THEN 1 END) AS cancelled_trips,
       ROUND(
           CASE 
               WHEN COUNT(t.trip_id) = 0 THEN 0
               ELSE (COUNT(CASE WHEN LOWER(TRIM(t.status)) = 'cancelled' THEN 1 END)::NUMERIC / COUNT(t.trip_id)) * 100
           END, 2) AS cancellation_rate,
       ROUND(AVG(CASE WHEN LOWER(TRIM(t.status)) = 'completed' THEN t.rating END), 2) AS avg_rating
FROM drivers d
LEFT JOIN trips t ON d.driver_id = t.driver_id
GROUP BY d.name

-- Q10 — Onboarding a new driver atomically (Intermediate · Transactions)
-- BEGIN; INSERT driver; 3x INSERT trip; COMMIT;
-- Comment: what would trigger a rollback, and what happens to the driver row then?

BEGIN;

-- Register the new driver
INSERT INTO drivers (name)
VALUES ('Sunita Gurung');

-- Sunita's first trip
INSERT INTO trips (
    driver_id,
    passenger_id,
    pickup_location_id,
    dropoff_location_id,
    fare_amount,
    distance_km,
    status,
    requested_at,
    completed_at,
    rating,
    payment_method_id
)
VALUES (
    currval('drivers_driver_id_seq'),
    1,
    1,
    2,
    15.00,
    10.50,
    'completed',
    '2026-08-10 10:00:00',
    '2026-08-10 10:30:00',
    4.5,
    1
);

-- Sunita's second trip
INSERT INTO trips (
    driver_id,
    passenger_id,
    pickup_location_id,
    dropoff_location_id,
    fare_amount,
    distance_km,
    status,
    requested_at,
    completed_at,
    rating,
    payment_method_id
)
VALUES (
    currval('drivers_driver_id_seq'),
    2,
    2,
    3,
    20.00,
    15.00,
    'completed',
    '2026-08-10 11:00:00',
    '2026-08-10 11:45:00',
    5.0,
    2
);

-- Sunita's third trip
INSERT INTO trips (
    driver_id,
    passenger_id,
    pickup_location_id,
    dropoff_location_id,
    fare_amount,
    distance_km,
    status,
    requested_at,
    completed_at,
    rating,
    payment_method_id
)
VALUES (
    currval('drivers_driver_id_seq'),
    3,
    3,
    4,
    25.00,
    20.00,
    'completed',
    '2026-08-10 12:00:00',
    '2026-08-10 12:30:00',
    4.0,
    3
);

COMMIT;
-- (To deliberately trigger a rollback, we change the third trip's status from 'completed' to 'invalid_status'.
-- This violates the status CHECK constraint. The third INSERT would fail before COMMIT, so the transaction
--would be aborted. After ROLLBACK, the driver row and thefirst two trips would also be removed.)

-- Q11 — A saved view for the ops dashboard (Intermediate · Views)
-- 11a. CREATE VIEW driver_cancellation_summary AS ...

CREATE VIEW driver_cancellation_summary AS
SELECT d.name AS driver_name,
       COUNT(t.trip_id) AS total_trips,
       COUNT(CASE WHEN LOWER(TRIM(t.status)) = 'cancelled' THEN 1 END) AS cancelled_trips,
       ROUND(
           CASE 
               WHEN COUNT(t.trip_id) = 0 THEN 0
               ELSE (COUNT(CASE WHEN LOWER(TRIM(t.status)) = 'cancelled' THEN 1 END)::NUMERIC / COUNT(t.trip_id)) * 100
           END, 2) AS cancellation_rate
FROM drivers d
LEFT JOIN trips t ON d.driver_id = t.driver_id
GROUP BY d.name;

-- 11b. SELECT from the view: drivers with cancellation_rate above 20%

SELECT *
FROM driver_cancellation_summary
WHERE cancellation_rate > 20;

-- Q12 — Speeding up a slow driver lookup (Intermediate · Indexing — beyond the pre-reads)
-- 12a. EXPLAIN ANALYZE before the index — note scan type + execution time in a comment

EXPLAIN ANALYZE
SELECT *
FROM trips
WHERE driver_id = 1;
-- (The scan type is a sequential scan, 
-- which means that the database is scanning through all the rows in the trips table to find the matching driver_id. 
-- The execution time is 0.630 ms.)

-- 12b. CREATE INDEX

CREATE INDEX idx_trips_driver_id ON trips(driver_id);

-- 12c. EXPLAIN ANALYZE after the index — note what changed in a comment

EXPLAIN ANALYZE
SELECT *
FROM trips
WHERE driver_id = 1;
-- (The plan changed from a Sequential Scan to a Bitmap Heap Scan, with a Bitmap Index Scan using idx_trips_driver_id.
-- Execution time: 0.742 ms, slightly slower than the original 0.630 ms, because the test table is relatively small.
-- On a table with millions of rows, this index should make driver-specific lookups substantially more efficient.)