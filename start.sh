#!/bin/sh
set -e

echo "Running database seed..."
python seed_demo_data.py

echo "Starting gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 app:app
