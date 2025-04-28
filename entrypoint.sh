#!/bin/bash

cd /app || exit

uvicorn main:app "$@"
