"""
SimAPI Launch Script
Usage: python launch.py
"""
import os
import subprocess
import sys
import threading
import time
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║  S I M A P I  —  Physics Simulation Validation              ║
║  YC S26 Demo                                                  ║
╠══════════════════════════════════════════════════════════════╣
║  Real physics validation · ML-ready output · <30ms latency  ║
╚══════════════════════════════════════════════════════════════╝
"""

print(BANNER)
print("[1/2] Starting SimAPI server on http://localhost:8000 ...")
print("      API docs: http://localhost:8000/docs")

def open_browser():
    time.sleep(2.5)
    dashboard = os.path.join(ROOT, "dashboard", "index.html")
    webbrowser.open(f"file://{dashboard}")
    print("[2/2] Dashboard opened in browser")
    print()
    print("Try the API directly:")
    print('  curl -X POST http://localhost:8000/v1/demo')
    print('  curl http://localhost:8000/v1/health')
    print()
    print("Press Ctrl+C to stop.")

threading.Thread(target=open_browser, daemon=True).start()

os.chdir(ROOT)
subprocess.run([
    sys.executable, "-m", "uvicorn", "api.server:app",
    "--host", "0.0.0.0", "--port", "8000", "--reload"
])
