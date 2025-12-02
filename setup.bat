@echo off
REM Setup script voor Platform Analytics (Windows)

echo ================================
echo Platform Analytics Setup
echo ================================
echo.

echo [1/5] Stopping existing containers...
docker compose down
echo.

echo [2/5] Starting setup service...
docker compose up setup -d
timeout /t 30 /nobreak
echo.

echo [3/5] Starting all services...
docker compose up -d
echo.

echo [4/5] Waiting for services to be ready...
timeout /t 30 /nobreak
echo.

echo [5/5] Setting up Elasticsearch index template...
python setup_elasticsearch.py
echo.

echo ================================
echo Setup Complete!
echo ================================
echo.
echo Services running at:
echo - Kibana:          http://localhost:5601
echo - Elasticsearch:   http://localhost:9200
echo - RabbitMQ UI:     http://localhost:15672
echo.
echo Default credentials:
echo - Elastic/Kibana:  elastic / changeme
echo - RabbitMQ:        admin / admin
echo.
echo Next: Run "python generate_test_events.py" to create test data
echo.

pause
