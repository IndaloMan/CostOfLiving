from app import create_app

app = create_app()

if __name__ == "__main__":
    print("Starting Cost of Living Tracker...")
    print("Open http://127.0.0.1:5000 in your browser")
    app.run(debug=True)
