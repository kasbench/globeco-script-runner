FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Install dependencies with uv
RUN uv pip install --system

# Copy application code
COPY runner.py initialize.py ./
COPY files ./files

CMD ["python", "runner.py", "initialize"] 