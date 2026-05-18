#!/bin/bash

# Script to create the directory structure and empty files for auth/infrastructure/persistence

set -e  # Exit on error

BASE_DIR="auth/infrastructure/persistence"
REPO_DIR="$BASE_DIR/repositories"

echo "Creating directory structure under $BASE_DIR..."

# Create directories
mkdir -p "$REPO_DIR"

# Create files in the base persistence directory
touch "$BASE_DIR/orm_models.py"
touch "$BASE_DIR/encryption.py"
touch "$BASE_DIR/mappers.py"
touch "$BASE_DIR/unit_of_work.py"
touch "$BASE_DIR/fake_unit_of_work.py"

# Create files in the repositories subdirectory
touch "$REPO_DIR/user_repository.py"
touch "$REPO_DIR/github_profile_repository.py"

echo "Done. Directory tree created with empty files."

# Optional: Show the tree if tree command is available
if command -v tree &> /dev/null; then
    tree "$BASE_DIR"
else
    echo "Use 'ls -R $BASE_DIR' to view the structure."
fi
