#!/bin/bash

echo "🔧 Creating virtual environment..."
python3 -m venv venv

echo "📦 Activating virtual environment..."
source venv/bin/activate

echo "📜 Installing Python dependencies..."
pip install -r requirements.txt

echo "📂 Creating instance directory (for SQLite DB)..."
mkdir -p instance

echo "🗄️ Initializing the SQLite database..."
python init_db.py

echo "🚀 Launching Flask app..."
export FLASK_APP=run.py
export FLASK_ENV=development
flask run