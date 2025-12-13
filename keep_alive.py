from flask import Flask
from threading import Thread
import os
import time
import requests

app = Flask('')

@app.route('/')
def home():
    return "I am alive!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def ping_self():
    """
    Periodically pings the web server to keep it awake.
    Render sleeps after 15 minutes of inactivity.
    """
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url:
        print("No RENDER_EXTERNAL_URL found. Self-ping disabled (running locally?).")
        return
    
    while True:
        time.sleep(840) # 14 minutes
        try:
            response = requests.get(url)
            print(f"Pinged self: {response.status_code}")
        except Exception as e:
            print(f"Ping failed: {e}")

def keep_alive():
    t = Thread(target=run)
    t.start()
    
    # Start self-pinging in a separate thread
    t2 = Thread(target=ping_self)
    t2.start()
