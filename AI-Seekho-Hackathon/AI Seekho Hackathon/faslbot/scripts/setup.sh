#!/bin/bash
# FaslBot One-Command Setup Script

echo "=== FaslBot Environment Setup ==="

# 1. Create Python virtual environment
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Copy env template
cp .env.example .env
echo ">>> IMPORTANT: Fill in your API keys in backend/.env before running"

# 4. Flutter setup
cd ../mobile
flutter pub get
echo ">>> Flutter dependencies installed"

# 5. Firebase login
firebase login
echo ">>> Run: firebase init firestore  (select your project)"

echo "=== Setup Complete ==="