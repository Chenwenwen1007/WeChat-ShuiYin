#!/usr/bin/env bash

set -e

mkdir -p logs
source /opt/qushuiyin/venv/bin/activate
cd /opt/qushuiyin
nohup python -m server.main > logs/server.out 2>&1 &
