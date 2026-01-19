"""
Demo Application with Prometheus Metrics
Designed to be "breakable" for chaos engineering
"""
from flask import Flask, jsonify, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import time
import os
import threading

app = Flask(__name__)

# Prometheus Metrics
REQUEST_COUNT = Counter('demo_app_requests_total', 'Total requests', ['endpoint', 'status'])
REQUEST_LATENCY = Histogram('demo_app_request_latency_seconds', 'Request latency', ['endpoint'])
CPU_USAGE = Gauge('demo_app_cpu_usage_percent', 'CPU usage percentage')
MEMORY_USAGE = Gauge('demo_app_memory_bytes', 'Memory usage in bytes')

# Chaos State
class ChaosState:
    def __init__(self):
        self.cpu_stress = False
        self.memory_hog = []
        self.error_rate = 0.0
        self.latency_ms = 0

chaos = ChaosState()

# Background thread to update CPU metric
def update_metrics():
    import random
    while True:
        if chaos.cpu_stress:
            CPU_USAGE.set(random.uniform(85, 98))
        else:
            CPU_USAGE.set(random.uniform(5, 15))
        
        import psutil
        process = psutil.Process()
        MEMORY_USAGE.set(process.memory_info().rss)
        time.sleep(5)

metrics_thread = threading.Thread(target=update_metrics, daemon=True)
metrics_thread.start()

# Health Endpoints
@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/ready')
def ready():
    if chaos.error_rate > 0.5:
        return jsonify({"status": "not ready"}), 503
    return jsonify({"status": "ready"})

@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

# API Endpoint
@app.route('/api/data')
def get_data():
    import random
    start = time.time()
    
    # Inject latency
    if chaos.latency_ms > 0:
        time.sleep(chaos.latency_ms / 1000)
    
    # Inject errors
    if random.random() < chaos.error_rate:
        REQUEST_COUNT.labels(endpoint='/api/data', status='500').inc()
        return jsonify({"error": "Simulated failure"}), 500
    
    REQUEST_COUNT.labels(endpoint='/api/data', status='200').inc()
    REQUEST_LATENCY.labels(endpoint='/api/data').observe(time.time() - start)
    return jsonify({"data": "success", "timestamp": time.time()})

# Chaos Endpoints
@app.route('/chaos/cpu/start')
def start_cpu():
    chaos.cpu_stress = True
    def burn_cpu():
        while chaos.cpu_stress:
            _ = [x**2 for x in range(10000)]
    for _ in range(2):
        threading.Thread(target=burn_cpu, daemon=True).start()
    return jsonify({"status": "CPU stress started"})

@app.route('/chaos/cpu/stop')
def stop_cpu():
    chaos.cpu_stress = False
    return jsonify({"status": "CPU stress stopped"})

@app.route('/chaos/memory/leak')
def leak_memory():
    chaos.memory_hog.append("X" * (50 * 1024 * 1024))  # 50MB
    return jsonify({"status": f"Leaked {len(chaos.memory_hog) * 50}MB"})

@app.route('/chaos/memory/clear')
def clear_memory():
    chaos.memory_hog.clear()
    return jsonify({"status": "Memory cleared"})

@app.route('/chaos/errors/start/<int:rate>')
def start_errors(rate):
    chaos.error_rate = rate / 100.0
    return jsonify({"status": f"Error rate set to {rate}%"})

@app.route('/chaos/errors/stop')
def stop_errors():
    chaos.error_rate = 0.0
    return jsonify({"status": "Errors stopped"})

@app.route('/chaos/latency/start/<int:ms>')
def start_latency(ms):
    chaos.latency_ms = ms
    return jsonify({"status": f"Latency set to {ms}ms"})

@app.route('/chaos/latency/stop')
def stop_latency():
    chaos.latency_ms = 0
    return jsonify({"status": "Latency removed"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
