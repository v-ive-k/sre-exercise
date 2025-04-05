# I initially missed the reference code provided, so I approached the assessment from my prespective. 
# I built a version that supports concurrent checks using threading, includes timeout handling, and tracks availability with both response codes and latency. 
# Looking back, I see how the reference was intended as a simpler baseline, 
# but I tried to make my solution,
# production-oriented,
# more detailed logging,
# performance considerations.

import sys
import yaml
from urllib.parse import urlparse
import requests
import time
import logging
from threading import Thread
from concurrent.futures import ThreadPoolExecutor

# Availability tracking class
class AvailabilityTracker:
    def __init__(self):
        self.stats = {}  # domain -> {success: int, total: int}

    def update(self, domain, is_available):
        if domain not in self.stats:
            self.stats[domain] = {'success': 0, 'total': 0}
        self.stats[domain]['total'] += 1
        if is_available:
            self.stats[domain]['success'] += 1

    def get_availability(self, domain):
        stats = self.stats.get(domain, {'success': 0, 'total': 0})
        return (stats['success'] / stats['total'] * 100) if stats['total'] > 0 else 0

# Check an endpoint with 500ms timeout
def check_endpoint(endpoint):
    url = endpoint['url']
    method = endpoint.get('method', 'GET')
    headers = endpoint.get('headers', {})
    body = endpoint.get('body')
    
    try:
        start = time.time()
        resp = requests.request(method, url, headers=headers, data=body, timeout=0.5)
        elapsed = (time.time() - start) * 1000  # Convert to ms
        is_available = 200 <= resp.status_code <= 299 and elapsed <= 500
        domain = urlparse(url).hostname  # Ignore port
        return domain, is_available, elapsed
    except requests.RequestException as e:
        domain = urlparse(url).hostname
        return domain, False, 0

# Log availability every 15 seconds
def log_availability(tracker):
    while True:
        for domain in tracker.stats:
            availability = tracker.get_availability(domain)
            logging.info(f"{domain}: {availability:.1f}% availability")
        time.sleep(15)

# Main monitoring loop
def monitor_endpoints(endpoints):
    tracker = AvailabilityTracker()
    
    # Start logging thread
    Thread(target=log_availability, args=(tracker,), daemon=True).start()
    
    # Check endpoints concurrently
    with ThreadPoolExecutor(max_workers=4) as executor:
        while True:
            results = executor.map(check_endpoint, endpoints)
            for domain, is_available, elapsed in results:
                tracker.update(domain, is_available)
            time.sleep(1)  # Avoid overwhelming the server

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    
    if len(sys.argv) != 2:
        print("Usage: python main.py <config.yaml>")
        sys.exit(1)
    
    try:
        with open(sys.argv[1], 'r') as f:
            config = yaml.safe_load(f)
        if not config or not isinstance(config, list):
            raise ValueError("YAML must contain a list of endpoints")
    except Exception as e:
        print(f"Error loading YAML: {e}")
        sys.exit(1)
    
    monitor_endpoints(config)
