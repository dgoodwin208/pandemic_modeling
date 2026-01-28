#!/bin/bash

# AI-Augmented Pandemic Response Model - Start Script
# This script starts both the backend and frontend servers

set -e

echo "🦠 AI-Augmented Pandemic Response Model"
echo "========================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    echo "Please install Python 3.9+ from https://www.python.org/downloads/"
    exit 1
fi

# Check for Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}Error: Node.js is not installed${NC}"
    echo "Please install Node.js 18+ from https://nodejs.org/"
    exit 1
fi

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Setup Backend
echo -e "${BLUE}Setting up backend...${NC}"
cd "$SCRIPT_DIR/backend"

if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing Python dependencies..."
pip install -r requirements.txt --quiet

# Setup Frontend
echo -e "${BLUE}Setting up frontend...${NC}"
cd "$SCRIPT_DIR/frontend"

if [ ! -d "node_modules" ]; then
    echo "Installing Node.js dependencies..."
    npm install
fi

# Start servers
echo ""
echo -e "${GREEN}Starting servers...${NC}"
echo ""

# Start backend in background
cd "$SCRIPT_DIR/backend"
source venv/bin/activate
echo -e "${BLUE}Starting backend on http://localhost:8000${NC}"
uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

# Give backend time to start
sleep 2

# Start frontend
cd "$SCRIPT_DIR/frontend"
echo -e "${BLUE}Starting frontend on http://localhost:3000${NC}"
npm run dev &
FRONTEND_PID=$!

# Wait a moment then open browser
sleep 3
echo ""
echo -e "${GREEN}========================================"
echo "🚀 Application is running!"
echo ""
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all servers"
echo -e "========================================${NC}"

# Open browser (works on Mac and most Linux)
if command -v open &> /dev/null; then
    open http://localhost:3000
elif command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:3000
fi

# Trap Ctrl+C to kill both processes
trap "echo ''; echo 'Shutting down...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT

# Wait for processes
wait
