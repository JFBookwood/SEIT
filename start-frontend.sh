#!/bin/bash
echo "🚀 Starting SEIT Frontend..."
echo "📦 Checking dependencies..."

if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    pnpm install
fi

echo "🌐 Starting development server..."
pnpm dev
