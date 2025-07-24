#!/bin/bash

# RanomEngine Activation Script
# Run: source activate.sh

echo "🚀 Activating RanomEngine virtual environment..."

# Activate virtual environment
source venv/bin/activate

echo "✅ Virtual environment activated!"
echo ""
echo "🖥️  CLI Commands:"
echo "  python cli.py --help                     # Show all available commands"
echo "  python cli.py config-info                # Show configuration"
echo "  python cli.py validate-vin <VIN>         # Validate VIN format"
echo "  python cli.py search-vin <VIN>           # Search for VIN listings"
echo "  python cli.py process <VIN_OR_URL>       # Full pipeline processing"
echo ""
echo "🚀 REST API Server:"
echo "  python api.py                            # Start REST API server"
echo "  # Server: http://localhost:8000"
echo "  # Docs:   http://localhost:8000/docs"
echo ""
echo "🐍 API Client Example:"
echo "  python examples/api_client.py            # Interactive API demo"
echo ""
echo "📖 Documentation: See README.md and docs/API.md"
echo "🔧 Configuration: Copy env.example to .env to customize settings"
echo ""
echo "Ready to use RanomEngine! 🎯" 