#!/bin/bash

# RanomEngine Activation Script
# Run: source activate.sh

echo "🚀 Activating RanomEngine virtual environment..."

# Activate virtual environment
source venv/bin/activate

echo "✅ Virtual environment activated!"
echo ""
echo "📋 Available commands:"
echo "  python cli.py --help                     # Show all available commands"
echo "  python cli.py config-info                # Show configuration"
echo "  python cli.py validate-vin <VIN>         # Validate VIN format"
echo "  python cli.py search-vin <VIN>           # Search for VIN listings"
echo "  python cli.py process <VIN_OR_URL>       # Full pipeline processing"
echo "  python cli.py fetch-page <URL>           # Fetch webpage content"
echo "  python cli.py parse-page <URL>           # Parse vehicle listing"
echo ""
echo "📖 Documentation: See README.md for detailed setup and usage"
echo "🔧 Configuration: Copy env.example to .env to customize settings"
echo ""
echo "Ready to use RanomEngine! 🎯" 