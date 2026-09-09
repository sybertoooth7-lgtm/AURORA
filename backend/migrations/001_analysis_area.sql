-- Apply after the initial schema when upgrading an existing AURORA database.
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION;
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS radius_km DOUBLE PRECISION;

UPDATE analyses
SET latitude = ST_Y(ST_Centroid(geometry)),
    longitude = ST_X(ST_Centroid(geometry)),
    radius_km = COALESCE(radius_km, 1)
WHERE latitude IS NULL OR longitude IS NULL OR radius_km IS NULL;

ALTER TABLE analyses ALTER COLUMN latitude SET NOT NULL;
ALTER TABLE analyses ALTER COLUMN longitude SET NOT NULL;
ALTER TABLE analyses ALTER COLUMN radius_km SET NOT NULL;