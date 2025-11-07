# app/services.py

import re
import datetime
import os
from PIL import Image
import pytesseract
import numpy as np
import cv2

# Conditional import for pdf2image
try:
    from pdf2image import convert_from_bytes
except ImportError:
    convert_from_bytes = None

def preprocess_image(image_stream, crop_top_percent=50):
    """
    Converts an image stream to a preprocessed image for better OCR.
    
    Args:
        image_stream: The file stream of the image
        crop_top_percent: Percentage of image height to keep from top (default 50%)
                         Set to 100 to process entire image
    """
    # Read the image stream into a format OpenCV can use
    image_np = np.frombuffer(image_stream.read(), np.uint8)
    img = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
    
    # OPTIMIZATION: Crop to top portion only (most docs have key info at top)
    if crop_top_percent < 100:
        height = img.shape[0]
        crop_height = int(height * crop_top_percent / 100)
        img = img[0:crop_height, :]  # Keep only top X%
        print(f"[OCR OPTIMIZATION] Scanning only top {crop_top_percent}% of image")

    # 1. Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2. Apply a binary threshold to get a pure black and white image
    _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    # Convert the processed image back to a PIL-compatible format
    return Image.fromarray(thresh)


def process_file_stream(file_stream, file_extension, crop_top_percent=50):
    """
    Processes a file stream (image or PDF) and returns extracted text.
    
    Args:
        file_stream: The file stream to process
        file_extension: The file extension (.jpg, .pdf, etc)
        crop_top_percent: Percentage of image to scan from top (default 50%)
    """
    try:
        if file_extension in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']:
            # Apply preprocessing with optional cropping
            processed_pil_image = preprocess_image(file_stream, crop_top_percent)
            return pytesseract.image_to_string(processed_pil_image, lang='eng')
        
        elif file_extension == '.pdf':
            if not convert_from_bytes:
                raise ImportError("PDF processing requires 'pdf2image' and 'poppler-utils'.")
            
            pdf_bytes = file_stream.read()
            images = convert_from_bytes(pdf_bytes, first_page=1, last_page=1)
            if images:
                # Convert PIL image to bytes for preprocessing
                import io
                img_byte_arr = io.BytesIO()
                images[0].save(img_byte_arr, format='PNG')
                img_byte_arr = io.BytesIO(img_byte_arr.getvalue())

                processed_pdf_image = preprocess_image(img_byte_arr, crop_top_percent)
                return pytesseract.image_to_string(processed_pdf_image, lang='eng')
            else:
                raise Exception("Could not convert PDF to image.")
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")
    
    except pytesseract.TesseractNotFoundError:
        raise Exception("Tesseract is not installed or not in your system's PATH.")
    except Exception as e:
        raise e


def extract_metadata(text, custom_search_term=None, targeted_label_term=None):
    """
    Analyzes the extracted text to find key metadata for filename generation.
    Uses early return optimization - stops searching once all required fields are found.
    """
    # Initialize all variables at the start
    date_str = None
    amount_str = None
    invoice_str = None
    reference_str = None
    custom_match_str = None
    targeted_label_str = None
    vendor_str = None

    # Split text into lines for line-by-line processing (optimization)
    lines = text.split('\n')
    
    # 1. Find Vendor Name (usually first line)
    if lines:
        first_line = lines[0].strip()
        vendor_str = re.sub(r'[^a-zA-Z0-9\s-]', '', first_line).strip()[:20].replace(' ', '_')
    if not vendor_str:
        vendor_str = "OCR_Scan"

    # 2. Search through lines for patterns (stop early if all found)
    for line in lines:
        # Find Date (if not found yet)
        if not date_str:
            date_match = re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', line)
            if date_match:
                date_str = date_match.group(0).replace('/', '-')
        
        # Find Amount (if not found yet)
        if not amount_str:
            amount_match = re.search(r'([Ss]?\s*|Total|TOTAL|Amount)\s*[\$€£]?\s*(\d{1,3}(?:[,\.\s]?\d{3})*(?:[\.,]\d{2}))', line, re.IGNORECASE)
            if amount_match:
                amount = amount_match.group(2).replace(',', '')
                amount_str = f"USD-{amount}"
        
        # Find Invoice/Reference Numbers (if not found yet)
        if not invoice_str:
            invoice_match = re.search(r'(invoice|inv|bill|statement)\s*[:#\s]*([a-zA-Z0-9-]{3,20})', line, re.IGNORECASE)
            if invoice_match:
                invoice_str = invoice_match.group(2).strip().upper().replace(' ', '_')
        
        if not reference_str and not invoice_str:
            reference_match = re.search(r'(ref|reference|po)\s*[:#\s]*([a-zA-Z0-9-]{3,20})', line, re.IGNORECASE)
            if reference_match:
                reference_str = reference_match.group(2).strip().upper().replace(' ', '_')
        
        # Find Custom Search Term (if not found yet and if provided)
        if custom_search_term and not custom_match_str:
            try:
                if custom_search_term.isdigit():
                    pattern = f'{custom_search_term}[\\d-]+'
                    match = re.search(pattern, line)
                    if match:
                        custom_match_str = match.group(0)
                else:
                    pattern = r'[a-zA-Z0-9-]*' + re.escape(custom_search_term) + r'[a-zA-Z0-9-]*'
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        custom_match_str = match.group(0).strip()
                
                if custom_match_str:
                    custom_match_str = re.sub(r'[^a-zA-Z0-9-]', '', custom_match_str).strip('_')
            except Exception as e:
                print(f"Error during custom regex search: {e}")
        
        # Find Targeted Label (if not found yet and if provided)
        if targeted_label_term and not targeted_label_str:
            try:
                escaped_term = re.escape(targeted_label_term)
                pattern = f'{escaped_term}\\s*([^\\n]+)'
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    targeted_label_str = match.group(1).strip()
                    targeted_label_str = re.sub(r'[^a-zA-Z0-9]', '', targeted_label_str)
                    if not targeted_label_str:
                        targeted_label_str = None
                    else:
                        print(f"Found targeted label match: {targeted_label_str}")
            except Exception as e:
                print(f"Error during targeted label search: {e}")
        
        # EARLY EXIT: If we found everything we're looking for, stop processing
        # (Only check the fields that were actually requested)
        all_found = True
        if not date_str or not vendor_str:
            all_found = False
        if custom_search_term and not custom_match_str:
            all_found = False
        if targeted_label_term and not targeted_label_str:
            all_found = False
        
        if all_found:
            print("[OPTIMIZATION] All required fields found, stopping early")
            break

    # Return all metadata
    return {
        'date': date_str,
        'vendor': vendor_str,
        'amount': amount_str,
        'invoice_number': invoice_str,
        'reference_number': reference_str,
        'custom_match': custom_match_str,
        'targeted_label': targeted_label_str
    }


def create_suggested_name(metadata, original_extension, custom_prefix='', separator='_', component_list=None):
    if component_list is None:
        component_list = ['custom_match']
        
    name_parts = []
    if custom_prefix:
        name_parts.append(re.sub(r'[^a-zA-Z0-9_.-]', '', custom_prefix).strip())
    
    component_map = {
        'date': metadata['date'] or datetime.date.today().strftime('%Y%m%d'),
        'vendor': metadata.get('vendor', "GENERIC"),
        'amount': metadata.get('amount'),
        'invoice_number': metadata.get('invoice_number'),
        'reference_number': metadata.get('reference_number'),
        'custom_match': metadata.get('custom_match'),
        'targeted_label': metadata.get('targeted_label'),
        'timestamp': datetime.datetime.now().strftime('%H%M%S')
    }
    
    for key in component_list:
        if value := component_map.get(key):
            name_parts.append(str(value))
            
    if not name_parts:
        name_parts.extend([datetime.date.today().strftime('%Y%m%d'), "EMPTY_OCR"])
            
    core_name = separator.join(name_parts)
    safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '', core_name).replace(' ', '_')
    
    return f"{safe_name}{original_extension}"
