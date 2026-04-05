.PHONY: install test lint format type-check all deploy-rpi

install:
	uv sync --all-groups

test:
	uv run pytest tests/ -v --cov=ble_scanner --cov-report=term-missing

lint:
	uv run ruff check .

format:
	uv run ruff format .

type-check:
	uv run pyright .

all: lint type-check test

# Raspberry Pi へのデプロイ（SSH 接続が必要）
deploy-rpi:
	ssh pi@raspberrypi.local 'cd ~/smarthome-pi-client && git pull && uv sync && sudo systemctl restart smarthome-ble'
