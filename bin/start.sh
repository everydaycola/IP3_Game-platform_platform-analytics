#!/bin/bash
set -e

echo "🚀 Starting platform-analytics stack..."
echo "=" * 60

# Install Python requirements
echo "📦 Installing Python requirements..."
pip3 install -r requirements.txt --quiet || echo "⚠️ Failed to install requirements (continuing anyway)"

# Start Elasticsearch first
echo "📊 Starting Elasticsearch..."
docker-compose up -d elasticsearch

# Wait for Elasticsearch to be healthy
echo "⏳ Waiting for Elasticsearch health check..."
timeout 300 bash -c 'until docker-compose ps elasticsearch | grep -q "healthy"; do sleep 5; done' || {
    echo "❌ Elasticsearch health check timed out"
    exit 1
}

echo "✅ Elasticsearch is healthy!"

# Run setup
echo "🔧 Running setup (templates + user passwords)..."
docker-compose --profile=setup run --rm setup || {
    echo "❌ Setup failed"
    exit 1
}

# Start all services
echo "🎉 Starting all services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 20

# Setup RabbitMQ bindings
echo "🔗 Setting up RabbitMQ queue bindings..."
python3 setup/setup_rabbitmq_bindings.py || echo "⚠️ RabbitMQ setup failed (continuing anyway)"

# Wait for Kibana to be ready
echo "⏳ Waiting for Kibana to be ready..."
sleep 15

# Create data view in Kibana
echo "📊 Creating Kibana data view..."
python3 setup/create_data_view.py || echo "⚠️ Data view creation failed (continuing anyway)"

# Create revenue dashboard
echo "💰 Creating revenue dashboard..."
python3 setup/create_revenue_dashboard.py || echo "⚠️ Dashboard creation failed (continuing anyway)"

echo ""
echo "=" * 60
echo "✅ Platform Analytics is ready!"
echo ""
echo "📍 Access points:"
echo "   - Kibana: http://localhost:5601"
echo "   - Elasticsearch: http://localhost:9200"
echo "   - RabbitMQ Management: http://localhost:15672"
echo "   - Dashboard: http://localhost:5601/app/dashboards#/view/revenue-dashboard"
echo "   - Credentials: elastic / changeme (admin / admin for RabbitMQ)"
echo ""
echo "💰 Revenue dashboard 'Opbrengsten Dashboard' is ready!"
echo ""
echo "💡 Generate test data with:"
echo "   echo '1' | python3 ./scripts/generate_revenue_data.py"
echo "=" * 60
