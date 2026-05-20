-- infra/postgres/init.sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Restricted roles for the application and audit log
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user LOGIN PASSWORD 'sutram_app';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'audit_owner') THEN
        CREATE ROLE audit_owner LOGIN PASSWORD 'sutram_audit';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE sutram TO app_user;
GRANT CONNECT ON DATABASE sutram TO audit_owner;
