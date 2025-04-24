#!/bin/bash

cd /app

uvicorn main:app "$@"
