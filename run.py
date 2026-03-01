import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    cert = "media-pc.tail9914ae.ts.net.crt"
    key  = "media-pc.tail9914ae.ts.net.key"

    if os.path.exists(cert) and os.path.exists(key):
        print("Starting Cost of Living Tracker (HTTPS)...")
        print("Open https://media-pc.tail9914ae.ts.net:5000 in your browser")
        app.run(debug=True, host="0.0.0.0", port=5000, ssl_context=(cert, key))
    else:
        print("Starting Cost of Living Tracker (HTTP)...")
        print("Open http://127.0.0.1:5000 in your browser")
        app.run(debug=True, host="0.0.0.0", port=5000)
