# DataSync Pro — Setup Guide

A full-stack data synchronization tool: Python backend (FastAPI + ML pipeline),
Node.js frontend build tools, and a Rust CLI helper.

## Prerequisites

Make sure you have Python 3.11+, Node.js 18+, and Rust installed.

## Backend Setup (Python)

This project uses a mix of core dependencies and ML libraries. Install them
in order:

```
pip install fastapi==0.110.0
pip install "uvicorn[standard]>=0.29.0"
pip install numpy==1.26.4
pip install pandas>=2.1.0
pip install scikit-learn~=1.4.0
pip install python-dotenv
pip install sqlalchemy==2.0.29
pip install alembic
```

For local development you'll also want the dev/test tools:

```
pip install pytest==8.1.1
pip install black
pip install mypy
```

## Frontend Build Tools (Node.js)

We use Vite for bundling and a couple of CLI utilities:

```
npm install vite@5.2.0
npm install --save-dev eslint
npm install --save-dev prettier
npm install axios
```

## Rust CLI Helper

There's a small Rust binary used for fast file-diffing during sync:

```
cargo build --release
```

## Database

We use PostgreSQL locally. If you don't have it, install it via your package
manager:

```
sudo apt-get install postgresql
```

(macOS users: `brew install postgresql`)

## Environment Variables

Copy the example env file and fill in your own values:

```
export DATABASE_URL=postgresql://localhost:5432/datasync
export SECRET_KEY=changeme
```

## Optional: Docker

If you'd rather skip local installs entirely, just run:

```
docker-compose up --build
```

## Notes

- Don't forget to run migrations after installing dependencies (not covered here).
- The `frontend/` folder setup is legacy and no longer used — ignore any old
  instructions mentioning it.
- If something breaks, check that your Python and Node versions match the
  prerequisites above before opening an issue.
