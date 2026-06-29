#!/bin/bash
set -e

echo "Building lbf engine for Vega Nesting..."

# Install Rust if not present
if ! command -v cargo &> /dev/null; then
    echo "Rust not found. Installing Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
fi

# Clone jagua-rs fork
REPO_DIR="jagua-rs"
if [ -d "$REPO_DIR" ]; then
    echo "Directory $REPO_DIR exists, updating..."
    cd "$REPO_DIR"
    git pull
else
    echo "Cloning jagua-rs..."
    git clone https://github.com/VovaStelmashchuk/jagua-rs.git "$REPO_DIR"
    cd "$REPO_DIR"
fi

echo "Building lbf in release mode..."
cargo build --release

echo "Copying lbf binary to app directory..."
cp target/release/lbf ../lbf
echo "LBF binary is ready at app/lbf"
echo "Make sure it is executable: chmod +x app/lbf"
