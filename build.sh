#!/usr/bin/env bash
# exit on error
set -o errexit

echo "--- Starting build process: Compiling Stockfish from source ---"

echo "--- 1. Installing build tools (git, g++, make) ---"
apt-get update -y
apt-get install -y git build-essential

echo "--- 2. Cloning Stockfish source code ---"
git clone https://github.com/official-stockfish/Stockfish.git

echo "--- 3. Compiling Stockfish ---"
# Navigate into the source code directory
cd Stockfish/src
# Compile the code. This creates an executable named 'stockfish'
make -j build ARCH=x86-64

echo "--- 4. Copying compiled executable to root directory ---"
# Copy the new program back to our main project folder
cp stockfish ../../stockfish-linux

echo "--- Build process finished successfully ---"