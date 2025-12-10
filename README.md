# bocrren

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Tesseract](https://img.shields.io/badge/Tesseract-5F499F?style=flat&logo=tesseract&logoColor=white)

`bocrren` is a Batch OCR Renaming tool. It is designed to help users rename batches of files according to the text content within them, which is extracted using OCR (Optical Character Recognition).

The main goal of this project is to make it executable locally, so you don't have to expose your files online.

## Project Note

This project started from my own idea and has gone through many rounds of testing and refinement to make it practical.

AI tools supported parts of the development, but the concept and direction were guided by my work and decisions.

## Project Status

This is currently a work-in-progress (WIP) and a personal project for learning purposes.

## Getting Started


## Prerequisites

### System Dependencies
* Python 3.11+ or 3.12
* Tesseract OCR (must be installed on your system)
  * **Ubuntu/Debian**: `sudo apt-get install tesseract-ocr`
  * **macOS**: `brew install tesseract`
  * **Windows**: Download from [Tesseract GitHub](https://github.com/UB-Mannheim/tesseract/wiki)
* Poppler (for PDF support)
  * **Ubuntu/Debian**: `sudo apt-get install poppler-utils`
  * **macOS**: `brew install poppler`
  * **Windows**: Download from [poppler releases](http://blog.alivate.com.au/poppler-windows/)

### Python Dependencies
```bash
pip install -r requirements.txt
```

### Installation

1.  Clone the repository:
    ```sh
    git clone [https://github.com/ertwrx/bocrren.git](https://github.com/ertwrx/bocrren.git)
    cd bocrren
    ```

2.  Install the required Python packages:
    ```sh
    pip install -r requirements.txt
    ```

### Usage

Run the application using:
```sh
python run.py
