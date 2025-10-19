#!/bin/bash
# Database healthcheck script
# Verifies that PostgreSQL is ready AND initialization scripts have completed

set -e

# Check if PostgreSQL is ready to accept connections
pg_isready -U cservice >/dev/null 2>&1 || exit 1

# Check if initialization is complete by verifying the marker table exists
psql -U cservice -tAc "SELECT 1 FROM init_completed LIMIT 1" >/dev/null 2>&1 || exit 1

# All checks passed
exit 0
