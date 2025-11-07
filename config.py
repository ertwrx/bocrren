# config.py

import os

# Path to the Tesseract executable
# On Windows, it might be: r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# On Linux/macOS, it's often just 'tesseract' if it's in the system's PATH
TESSERACT_CMD = 'tesseract' 

# Language for Tesseract to use
TESSERACT_LANG = 'eng'

# Server URL for auto-opening in the browser
SERVER_URL = "http://127.0.0.1:5000"
