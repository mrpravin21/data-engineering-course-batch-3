-- Week 1 SQL Assignment — Answers
-- Fill in each query below. See sql_assignment.md for the full scenario text.
-- Rename this file to sql_answers.sql before committing.


-- Q1 — Kathmandu to Pokhara (Basic · DQL)
-- Completed rides from Kathmandu to Pokhara: ride_id, driver_name, passenger_name, fare_amount

SELECT ride_id, driver_name, passenger_name, fare_amount
FROM rides
WHERE LOWER(pickup_city) = LOWER('kathmandu') 
AND LOWER(dropoff_city) = LOWER('pokhara') 
AND ride_status = 'completed';


-- Q2 — Top 5 highest fares (Basic · DQL)
-- driver_name, passenger_name, fare_amount — 5 highest fares, descending

SELECT driver_name, passenger_name, fare_amount
FROM rides
WHERE ride_status = 'completed'
ORDER BY fare_amount DESC
LIMIT 5;

-- Q3 — The "Shrestha" complaint (Basic · DQL)
-- Every ride where driver_name contains "shrestha", case-insensitive

SELECT *
FROM rides
WHERE LOWER(driver_name) LIKE '%shrestha%';

-- Q4 — How many rides were never rated? (Basic–Intermediate · NULL)
-- One query returning: total_rides, rated_rides, unrated_rides

SELECT
COUNT(*) AS total_rides,
COUNT(rating) AS rated_rides,
COUNT(*) - COUNT(rating) AS unrated_rides
FROM rides;


-- Q5 — Every ride that wasn't paid in cash (Intermediate · NULL)
-- ride_id, driver_name, payment_method — not cash, including unrecorded payment methods

SELECT ride_id, driver_name, payment_method
FROM rides
WHERE LOWER(payment_method) != LOWER('cash') 
OR payment_method IS NULL;

-- Q6 — Revenue by pickup city (Intermediate · Aggregation)
-- pickup_city, total_rides, total_revenue, avg_fare (2 decimals) — sorted by total_revenue desc

SELECT
pickup_city,
count(*) AS total_rides,
SUM(fare_amount) AS total_revenue,
ROUND(AVG(fare_amount), 2) AS avg_fare
FROM rides
GROUP BY pickup_city
ORDER BY total_revenue DESC;


-- Q7 — Drivers who qualify for the loyalty bonus (Intermediate · Aggregation)
-- driver_name, completed_rides — drivers with more than 100 completed rides, sorted desc

SELECT driver_name, COUNT(*) AS completed_rides
FROM rides
WHERE ride_status = 'completed'
GROUP BY driver_name
HAVING COUNT(*) > 100
ORDER BY completed_rides DESC;

-- Q8 — Ride outcomes by status (Intermediate · Aggregation)
-- ride_status, ride_count, avg_distance_km (2 decimals) — sorted by ride_count desc

SELECT
ride_status,
COUNT(*) AS ride_count,
ROUND(AVG(ride_distance_km), 2) AS avg_distance_km
FROM rides
GROUP BY ride_status
ORDER BY ride_count DESC;

-- Q9 — A new driver's first ride (Basic–Intermediate · DML)
-- 9a. INSERT the new ride (ride_id 9001, rating NULL)

INSERT INTO rides (ride_id, driver_name, passenger_name, pickup_city, dropoff_city, fare_amount, ride_distance_km, ride_status, rating, payment_method)
VALUES (9001, 'Sunita Gurung', 'Rajan Thapa', 'Lalitpur', 'Bhaktapur', 350.00, 12.40, 'completed', NULL, 'cash');

-- 9b. UPDATE the rating to 4.8 for ride_id 9001

UPDATE rides
SET rating = 4.8
WHERE ride_id = 9001;

-- Q10 — Locking down payment methods (Intermediate · DDL)
-- 10a. ALTER TABLE to restrict payment_method to a fixed set of values

ALTER TABLE rides
ADD CONSTRAINT payment_method_check 
CHECK (payment_method IN ('cash', 'esewa', 'khalti', 'card', 'wallet'));

-- 10b. INSERT using an invalid payment method — note the error you'd expect in a comment

INSERT INTO rides (ride_id, driver_name, passenger_name, pickup_city, dropoff_city, fare_amount, ride_distance_km, ride_status, rating, payment_method)
VALUES (9002, 'Ramesh Thapa', 'Sita Lama', 'Kathmandu', 'lalitpur', 500.00, 15.00, 'completed', 5.0, 'applepay'); 
-- This will fail as the payment_method_check constraint only allows 'cash', 'esewa', 'khalti', 'card', or 'wallet' as a valid payment method.

-- Q11 — Rides priced above the platform average (Intermediate · Subquery)
-- ride_id, driver_name, fare_amount — fare_amount above the average of ALL rides (via subquery)

SELECT ride_id, driver_name, fare_amount
FROM rides
WHERE fare_amount > (SELECT AVG(fare_amount) FROM rides);

-- Q12 — Each driver's single best ride (Intermediate · Correlated subquery)
-- driver_name, ride_id, fare_amount — one row per driver, their own max fare_amount

SELECT r1.driver_name, r1.ride_id, r1.fare_amount
FROM rides r1
WHERE r1.fare_amount = (
    SELECT MAX(r2.fare_amount)
    FROM rides r2
    WHERE r2.driver_name = r1.driver_name
);
