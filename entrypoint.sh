#!/bin/bash

python3 /app/prepare_docker_environment.py --config /opt/ptah_config.yaml

cd /app
uvicorn main:app --host :: --reload
