# Dockerfile for testing ab-cli installation and commands
FROM python:3.12-slim

# Install git and other dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    bash \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/local/bin/python3 /usr/bin/python3

# Configure git
RUN git config --global user.email "test@example.com" && \
    git config --global user.name "Test User" && \
    git config --global init.defaultBranch master

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install the package in editable mode
RUN pip install --no-cache-dir -e ".[dev]"

# Add bin directory to PATH and make scripts executable
ENV PATH="/app/bin:${PATH}"
RUN chmod +x /app/bin/*

# Create a test git repository for testing git commands
RUN mkdir -p /test-repo && \
    cd /test-repo && \
    git init && \
    echo "test content" > test.txt && \
    git add . && \
    git commit -m "Initial commit"

# Set working directory to test repo
WORKDIR /test-repo

# Default command - show help
CMD ["ab", "help"]
