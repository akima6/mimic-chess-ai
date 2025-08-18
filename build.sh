#!/usr/bin/env bash
# exit on error
set -o errexit

echo "--- Starting build process: Compiling Stockfish from source ---"

# 1. Install necessary tools to build software
apt-get update -y && apt-get install -y git build-essential

# 2. Clone the official Stockfish source code
git clone --depth 1 https://github.com/official-stockfish/Stockfish.git

# 3. Compile the code
cd Stockfish/src
# The 'ARCH=general-64' flag creates a highly compatible version
make -j build ARCH=general-64

# 4. Copy the finished program to our main directory so app.py can find it
cp stockfish ../../pystockfish-engine

echo "--- Build process finished. 'pystockfish-engine' created. ---"