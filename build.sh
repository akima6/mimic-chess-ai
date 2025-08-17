#!/usr/bin/env bash
# exit on error
set -o errexit

echo "--- Starting build process ---"

echo "--- Updating package lists ---"
apt-get update -y

echo "--- Installing Stockfish ---"
apt-get install -y stockfish

echo "--- Installation complete. Verifying installation... ---"

# This is the most important command. It asks the system "Where did you put the stockfish program?"
# It will print the full path, e.g., /usr/bin/stockfish or /some/other/path/stockfish
echo "--- Finding Stockfish executable path ---"
which stockfish

echo "--- Listing contents of /usr/games to check ---"
ls -la /usr/games || echo "/usr/games does not exist or is empty"

echo "--- Listing contents of /usr/bin to check ---"
ls -la /usr/bin | grep stockfish || echo "Stockfish not found in /usr/bin"

echo "--- Build process finished ---"