#!/usr/bin/env python3
"""AutoResolve Chaos Engineering Script"""
import argparse
import requests
import time
import subprocess

DEMO_APP = "http://localhost:5000"
PROMETHEUS = "http://localhost:9090"

def print_header(text):
    print(f"\n{'='*60}")
    print(f"{text.center(60)}")
    print(f"{'='*60}\n")

def kubectl(cmd):
    result = subprocess.run(f"kubectl {cmd}".split(), capture_output=True, text=True)
    return result.stdout + result.stderr

def check_alert(name):
    try:
        r = requests.get(f"{PROMETHEUS}/api/v1/alerts")
        for alert in r.json().get("data", {}).get("alerts", []):
            if alert.get("labels", {}).get("alertname") == name:
                if alert.get("state") == "firing":
                    return True
    except:
        pass
    return False

def wait_for_alert(name, timeout=120):
    print(f"⏳ Waiting for alert '{name}' to fire...")
    start = time.time()
    while time.time() - start < timeout:
        if check_alert(name):
            print(f"🚨 Alert '{name}' is FIRING!")
            return True
        time.sleep(5)
        print(".", end="", flush=True)
    print(f"\n❌ Alert did not fire within {timeout}s")
    return False

def chaos_cpu():
    print_header("CHAOS: High CPU Usage")
    print("Starting CPU stress...")
    requests.get(f"{DEMO_APP}/chaos/cpu/start")
    print("✅ CPU stress started")
    wait_for_alert("HighCPUUsage")
    print("\n💡 Watch your FastAPI terminal for agent activity!")

def chaos_reset():
    print_header("RESET: Restoring Healthy State")
    requests.get(f"{DEMO_APP}/chaos/cpu/stop")
    requests.get(f"{DEMO_APP}/chaos/errors/stop")
    requests.get(f"{DEMO_APP}/chaos/latency/stop")
    requests.get(f"{DEMO_APP}/chaos/memory/clear")
    print("✅ Chaos stopped")
    kubectl("rollout restart deployment/demo-app")
    print("✅ Deployment restarted")

def status():
    print_header("SYSTEM STATUS")
    print("Pods:")
    print(kubectl("get pods -l app=demo-app"))
    print("\nFiring Alerts:")
    try:
        r = requests.get(f"{PROMETHEUS}/api/v1/alerts")
        alerts = [a for a in r.json().get("data", {}).get("alerts", []) if a.get("state") == "firing"]
        if alerts:
            for a in alerts:
                print(f"  🚨 {a['labels'].get('alertname')} ({a['labels'].get('severity')})")
        else:
            print("  ✅ No alerts firing")
    except Exception as e:
        print(f"  ❌ Could not fetch alerts: {e}")

def demo():
    print_header("AUTORESOLVE FULL DEMO")
    print("This demo will:")
    print("1. Show healthy state")
    print("2. Inject CPU chaos")
    print("3. Wait for alert to fire")
    print("4. Watch agents fix the issue")
    input("\nPress Enter to start...")
    
    status()
    time.sleep(2)
    
    chaos_cpu()
    
    print("\n⏳ Waiting for agents to fix the issue...")
    print("Watch your FastAPI terminal!")
    
    for i in range(24):
        time.sleep(5)
        if not check_alert("HighCPUUsage"):
            print("\n✅ Alert resolved! Issue fixed!")
            break
        print(".", end="", flush=True)
    
    time.sleep(5)
    status()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["cpu", "reset", "status", "demo"])
    args = parser.parse_args()
    
    {"cpu": chaos_cpu, "reset": chaos_reset, "status": status, "demo": demo}[args.action]()
