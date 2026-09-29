#!/bin/sh
# Runs once, on first container init. Creates the database pytest uses so the
# test suite never touches development data.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
	CREATE DATABASE outreach_test OWNER $POSTGRES_USER;
EOSQL
