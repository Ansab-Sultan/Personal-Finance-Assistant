#!/bin/bash
set -e

# Install uv if not already installed
if ! command -v uv &> /dev/null; then
    echo "Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Ensure uv is accessible in the current script execution path
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "uv is already installed."
fi

# Run uv sync for the backend
echo "Setting up backend dependencies..."
cd backend
uv sync
cd ..

# Run npm install for the frontend
echo "Setting up frontend dependencies..."
cd frontend
npm install
cd ..

echo "Setup completed successfully!"
