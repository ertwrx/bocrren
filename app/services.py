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

def preprocess_image(image_stream):
    """Converts an image stream to a preprocessed image for better OCR."""
    # Read the image stream into a format OpenCV can use
    image_np = np.frombuffer(image_stream.read(), np.uint8)
    img = cv2.imdecode(image_np, cv2.IMREAD_COLOR)

    # 1. Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2. Apply a binary threshold to get a pure black and white image
    # You might need to experiment with the threshold value (127)
    _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    # 3. (Optional) Apply some blurring to remove noise
    # thresh = cv2.medianBlur(thresh, 3)
    
    # Convert the processed image back to a PIL-compatible format
    return Image.fromarray(thresh)


def process_file_stream(file_stream, file_extension):
    """
    Processes a file stream (image or PDF) and returns extracted text.
    """
    try:
        if file_extension in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']:
            # --- APPLY PREPROCESSING ---
            processed_pil_image = preprocess_image(file_stream)
            return pytesseract.image_to_string(processed_pil_image, lang='eng')
        
        elif file_extension == '.pdf':
            # (PDF processing remains the same)
            if not convert_from_bytes:
                raise ImportError("PDF processing requires 'pdf2image' and 'poppler-utils'.")
            
            pdf_bytes = file_stream.read()
            images = convert_from_bytes(pdf_bytes, first_page=1, last_page=1)
            if images:
                # Preprocess the image from the PDF
                # To do this, we need to convert the PIL image to bytes
                import io
                img_byte_arr = io.BytesIO()
                images[0].save(img_byte_arr, format='PNG')
                img_byte_arr = io.BytesIO(img_byte_arr.getvalue()) # seek back to the beginning

                processed_pdf_image = preprocess_image(img_byte_arr)
                return pytesseract.image_to_string(processed_pdf_image, lang='eng')
            else:
                raise Exception("Could not convert PDF to image.")
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")
    
    except pytesseract.TesseractNotFoundError:
        raise Exception("Tesseract is not installed or not in your system's PATH.")
    except Exception as e:
        raise e

# --- THE REST OF THE FILE REMAINS THE SAME ---

# In app/services.py

def extract_metadata(text, custom_search_term=None):
    """
    Analyzes the extracted text to find key metadata for filename generation.
    """
    # 1. Find Date
    date_match = re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', text)
    date_str = date_match.group(0).replace('/', '-') if date_match else None
    
    # 2. Find Amount
    amount_match = re.search(r'([Ss]?\s*|Total|TOTAL|Amount)\s*[\$€£]?\s*(\d{1,3}(?:[,\.\s]?\d{3})*(?:[\.,]\d{2}))', text, re.IGNORECASE)
    amount_str = None
    if amount_match:
        amount = amount_match.group(2).replace(',', '') 
        amount_str = f"USD-{amount}"

    # 3. Find Reference/Invoice Numbers
    invoice_match = re.search(r'(invoice|inv|bill|statement)\s*[:#\s]*([a-zA-Z0-9-]{3,20})', text, re.IGNORECASE)
    reference_match = re.search(r'(ref|reference|po)\s*[:#\s]*([a-zA-Z0-9-]{3,20})', text, re.IGNORECASE)
    invoice_str = invoice_match.group(2).strip().upper().replace(' ', '_') if invoice_match else None
    reference_str = reference_match.group(2).strip().upper().replace(' ', '_') if reference_match and not invoice_match else None

    # --- START OF CORRECTED SECTION 4 ---
    # 4. Find Custom Search Term Match (New, more robust logic)
    custom_match_str = None
    if custom_search_term:
        try:
            # Check if the search term contains only numbers
            if custom_search_term.isdigit():
                # For numeric IDs, look for the number followed by digits and hyphens
                pattern = f'{custom_search_term}[\\d-]+'
                matches = re.finditer(pattern, text)
                longest_match = None
                max_length = 0
                
                # Find the longest matching sequence
                for match in matches:
                    match_text = match.group(0)
                    if len(match_text) > max_length:
                        max_length = len(match_text)
                        longest_match = match_text
                
                if longest_match:
                    custom_match_str = longest_match
            else:
                # For non-numeric patterns, use the original approach
                pattern = r'[a-zA-Z0-9-]*' + re.escape(custom_search_term) + r'[a-zA-Z0-9-]*'
                custom_match = re.search(pattern, text, re.IGNORECASE)
                if custom_match:
                    custom_match_str = custom_match.group(0).strip()
            
            # Only clean the match if we found one
            if custom_match_str:
                # Sanitize for filename but preserve hyphens for IDs
                custom_match_str = re.sub(r'[^a-zA-Z0-9-]', '', custom_match_str).strip('_')
        except Exception as e:
            print(f"Error during custom regex search: {e}")
            custom_match_str = None

    # --- END OF CORRECTED SECTION ---

    # 5. Find a key entity (vendor name)
    first_line = text.split('\n', 1)[0].strip()
    vendor_str = re.sub(r'[^a-zA-Z0-9\s-]', '', first_line).strip()[:20].replace(' ', '_')
    if not vendor_str:
        vendor_str = "OCR_Scan"
            
    return {
        'date': date_str, 'vendor': vendor_str, 'amount': amount_str,
        'invoice_number': invoice_str, 'reference_number': reference_str,
        'custom_match': custom_match_str
    }

def create_suggested_name(metadata, original_extension, custom_prefix='', separator='_', component_list=None):
    if component_list is None:
        component_list = ['custom_match']  # Default to custom_match if no components specified    
    if custom_prefix: name_parts.append(re.sub(r'[^a-zA-Z0-9_.-]', '', custom_prefix).strip())

    component_map = {
        'date': metadata['date'] or datetime.date.today().strftime('%Y%m%d'),
        'vendor': metadata.get('vendor', "GENERIC"), 'amount': metadata.get('amount'),
        'invoice_number': metadata.get('invoice_number'), 'reference_number': metadata.get('reference_number'),
        'custom_match': metadata.get('custom_match'), 'timestamp': datetime.datetime.now().strftime('%H%M%S') 
    }
    
    for key in component_list:
        if value := component_map.get(key): name_parts.append(str(value)) # Ensure value is a string
            
    if not name_parts: name_parts.extend([datetime.date.today().strftime('%Y%m%d'), "EMPTY_OCR"])
            
    core_name = separator.join(name_parts)
    safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '', core_name).replace(' ', '_')
    
    return f"{safe_name}{original_extension}"
