#!/bin/sh
cd "$(dirname "$0")" && PORT=${PORT:-8080} exec python3 server.py
