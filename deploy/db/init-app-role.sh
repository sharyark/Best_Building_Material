#!/bin/sh
# Runs once, when the Postgres data directory is first created.
# The superuser (POSTGRES_USER) is for admin work only. The application connects as a restricted role:
# it owns its own database (so migrations can create tables) but is NOT a superuser and cannot create
# databases or roles, and nobody else can connect to that database.
set -eu
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres \
     -v app_user="$APP_DB_USER" -v app_password="$APP_DB_PASSWORD" -v app_db="$APP_DB_NAME" <<'SQL'
CREATE ROLE :"app_user" LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE DATABASE :"app_db" OWNER :"app_user";
REVOKE ALL ON DATABASE :"app_db" FROM PUBLIC;
SQL
