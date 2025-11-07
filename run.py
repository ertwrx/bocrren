# run.py

import webbrowser
from app import create_app
from config import SERVER_URL

app = create_app()

if __name__ == '__main__':
    # Your auto-open feature now lives here
    # We point it to the static index.html file
    webbrowser.open(f"{SERVER_URL}/static/index.html")
    
    print("--- Portable OCR Renamer Server ---")
    print(f"Starting Flask server on {SERVER_URL}")
    app.run(host='0.0.0.0', port=5000, debug=False)
