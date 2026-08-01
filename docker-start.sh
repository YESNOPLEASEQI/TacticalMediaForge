#!/bin/bash
# MilitaryVideoGen Docker Quick Start Script

set -e

echo "MilitaryVideoGen API Docker Deployment"
echo "==================================="
echo ""

if [ -d config.yaml ]; then
    echo "config.yaml is a directory, removing it..."
    rm -rf config.yaml
fi

if [ ! -f config.yaml ]; then
    echo "config.yaml not found, creating from config.example.yaml..."
    if [ -f config.example.yaml ]; then
        cp config.example.yaml config.yaml
        echo "config.yaml created successfully."
        echo ""
        echo "Please edit config.yaml and fill in:"
        echo "   - LLM API key and settings"
        echo "   - ComfyUI URL"
        echo "   - RunningHub API key if needed"
        echo ""
    else
        echo "Error: config.example.yaml not found."
        exit 1
    fi
fi

if ! command -v docker-compose >/dev/null 2>&1 && ! docker compose version >/dev/null 2>&1; then
    echo "Error: docker-compose not found."
    echo "Install Docker Compose first: https://docs.docker.com/compose/install/"
    exit 1
fi

if command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
else
    DOCKER_COMPOSE="docker compose"
fi

echo "Building Docker images..."
$DOCKER_COMPOSE build

echo ""
echo "Starting API service..."
$DOCKER_COMPOSE up -d

echo ""
echo "Waiting for API to be ready..."
sleep 5

echo ""
echo "MilitaryVideoGen API is running."
echo "API:      http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Start the React frontend separately:"
echo "  cd frontend && npm run dev -- --host 127.0.0.1 --port 5173"
echo ""
echo "Useful commands:"
echo "  View logs: $DOCKER_COMPOSE logs -f"
echo "  Stop:      $DOCKER_COMPOSE down"
echo "  Restart:   $DOCKER_COMPOSE restart"
echo "  Rebuild:   $DOCKER_COMPOSE up -d --build"
