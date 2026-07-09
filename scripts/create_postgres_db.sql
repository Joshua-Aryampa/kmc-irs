-- Run once as the PostgreSQL superuser (postgres), e.g.:
-- psql -U postgres -f scripts/create_postgres_db.sql

CREATE USER irs_user WITH PASSWORD 'irs_dev_password';
CREATE DATABASE irs OWNER irs_user;
GRANT ALL PRIVILEGES ON DATABASE irs TO irs_user;
