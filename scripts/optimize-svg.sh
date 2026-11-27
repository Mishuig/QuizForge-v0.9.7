#!/bin/bash
# Оптимізація SVG файлів з SVGO
# Використання: ./scripts/optimize-svg.sh

set -e

if ! command -v svgo &> /dev/null; then
    echo "SVGO не встановлено. Встановіть: npm install -g svgo"
    exit 1
fi

echo "Оптимізація SVG файлів..."
svgo -f assets --multipass

echo "Готово!"
