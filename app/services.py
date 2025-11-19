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

def preprocess_image(image_stream, crop_top_percent=50, max_width=1920):
    """
    Converts an image stream to a preprocessed image for better OCR.
    
    Args:
        image_stream: The file stream of the image
        crop_top_percent: Percentage of image height to keep from top (default 50%)
        max_width: Maximum width to resize image (default 1920px, reduces OCR time)
    """
    # Read the image stream into a format OpenCV can use
    image_np = np.frombuffer(image_stream.read(), np.uint8)
    img = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
    
    # OPTIMIZATION 1: Downscale large images (speeds up OCR significantly)
    height, width = img.shape[:2]
    if width > max_width:
        scale_factor = max_width / width
        new_width = max_width
        new_height = int(height * scale_factor)
        img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
        print(f"[OCR OPTIMIZATION] Resized image from {width}x{height} to {new_width}x{new_height}")
    
    # OPTIMIZATION 2: Crop to top portion only (most docs have key info at top)
    if crop_top_percent < 100:
        height = img.shape[0]
        crop_height = int(height * crop_top_percent / 100)
        img = img[0:crop_height, :]
        print(f"[OCR OPTIMIZATION] Scanning only top {crop_top_percent}% of image")

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Apply binary threshold with OTSU
    _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    return Image.fromarray(thresh)


def process_file_stream(file_stream, file_extension, crop_top_percent=50, max_width=1920, component_list=None):
    """
    Processes a file stream (image or PDF) and returns extracted text.
    
    Args:
        file_stream: The file stream to process
        file_extension: The file extension (.jpg, .pdf, etc)
        crop_top_percent: Percentage of image to scan from top (default 50%)
        max_width: Maximum width for image processing (default 1920px)
        component_list: List of components user wants to extract (for adaptive cropping)
    """
    # ADAPTIVE CROPPING: Only adjust if NOT explicitly set to 100
    if crop_top_percent != 100:
        adaptive_crop = calculate_adaptive_crop(component_list)
        if adaptive_crop != crop_top_percent:
            print(f"[ADAPTIVE CROPPING] Adjusted crop from {crop_top_percent}% to {adaptive_crop}% based on components: {component_list}")
            crop_top_percent = adaptive_crop
    else:
        print(f"[FORCED SCAN] Scanning full document (100%) - adaptive cropping disabled")
    
    try:
        if file_extension in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']:
            processed_pil_image = preprocess_image(file_stream, crop_top_percent, max_width)
            # Use PSM 4 for single column with mixed text/tables
            return pytesseract.image_to_string(processed_pil_image, lang='eng', config='--psm 4')
        
        elif file_extension == '.pdf':
            if not convert_from_bytes:
                raise ImportError("PDF processing requires 'pdf2image' and 'poppler-utils'.")
            
            pdf_bytes = file_stream.read()
            # OPTIMIZATION: Lower DPI for faster PDF conversion (200 instead of default 300)
            images = convert_from_bytes(pdf_bytes, first_page=1, last_page=1, dpi=200)
            
            if images:
                # Convert PIL image directly to numpy array (avoid extra I/O)
                img_array = np.array(images[0])
                
                # Process directly without saving to BytesIO
                height, width = img_array.shape[:2]
                
                # Downscale if needed
                if width > max_width:
                    scale_factor = max_width / width
                    new_width = max_width
                    new_height = int(height * scale_factor)
                    img_array = cv2.resize(img_array, (new_width, new_height), interpolation=cv2.INTER_AREA)
                    print(f"[OCR OPTIMIZATION] Resized PDF image from {width}x{height} to {new_width}x{new_height}")
                
                # Crop if needed
                if crop_top_percent < 100:
                    height = img_array.shape[0]
                    crop_height = int(height * crop_top_percent / 100)
                    img_array = img_array[0:crop_height, :]
                    print(f"[OCR OPTIMIZATION] Scanning only top {crop_top_percent}% of PDF")
                
                # Convert to grayscale and threshold
                gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
                _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
                
                processed_image = Image.fromarray(thresh)
                return pytesseract.image_to_string(processed_image, lang='eng', config='--psm 4')
            else:
                raise Exception("Could not convert PDF to image.")
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")
    
    except pytesseract.TesseractNotFoundError:
        raise Exception("Tesseract is not installed or not in your system's PATH.")
    except Exception as e:
        raise e


def calculate_adaptive_crop(component_list):
    """
    Calculates optimal crop percentage based on components user wants to extract.
    
    Different document elements appear at different locations:
    - Header info (vendor, date, invoice#): Top 30-40%
    - Line items, descriptions: Middle 40-70%
    - Totals, amounts, signatures: Bottom 70-100%
    
    Args:
        component_list: List of component types user selected
        
    Returns:
        int: Recommended crop percentage (30-100)
    """
    if not component_list:
        return 50  # Default
    
    # Define where each component typically appears on documents
    component_locations = {
        # Top section (0-40%)
        'vendor': 30,
        'date': 35,
        'invoice_number': 40,
        'reference_number': 40,
        'custom_match': 40,  # Usually near header
        'targeted_label': 50,  # Usually in header/top section
        
        # Bottom section (60-100%)
        'amount': 80,  # Totals usually at bottom
        'timestamp': 100,  # Not from document, but include for completeness
    }
    
    # Find the deepest component the user needs
    max_location = 50  # Default minimum
    
    for component in component_list:
        if component in component_locations:
            component_depth = component_locations[component]
            if component_depth > max_location:
                max_location = component_depth
    
    # Add 20% buffer to ensure we capture the full field
    adaptive_crop = min(max_location + 10, 100)
    
    return adaptive_crop


def extract_metadata(text, custom_search_term=None, targeted_label_term=None):
    """
    Analyzes the extracted text to find key metadata for filename generation.
    Uses early return optimization - stops searching once all required fields are found.
    """
    date_str = None
    amount_str = None
    invoice_str = None
    reference_str = None
    custom_match_str = None
    targeted_label_str = None
    vendor_str = None

    lines = text.split('\n')
    
    # Find Vendor Name (first line)
    if lines:
        first_line = lines[0].strip()
        vendor_str = re.sub(r'[^a-zA-Z0-9\s-]', '', first_line).strip()[:20].replace(' ', '_')
    if not vendor_str:
        vendor_str = "OCR_Scan"

    # Precompile regex patterns for better performance
    date_pattern = re.compile(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}')
    amount_pattern = re.compile(r'([Ss]?\s*|Total|TOTAL|Amount)\s*[\$€£]?\s*(\d{1,3}(?:[,\.\s]?\d{3})*(?:[\.,]\d{2}))', re.IGNORECASE)
    invoice_pattern = re.compile(r'(invoice|inv|bill|statement)\s*[:#\s]*([a-zA-Z0-9-]{3,20})', re.IGNORECASE)
    reference_pattern = re.compile(r'(ref|reference|po)\s*[:#\s]*([a-zA-Z0-9-]{3,20})', re.IGNORECASE)

    # Track what we're looking for
    fields_needed = {
        'date': True,
        'amount': False,  # Optional
        'invoice': False,  # Optional
        'custom': bool(custom_search_term),
        'targeted': bool(targeted_label_term)
    }

    for line in lines:
        # Find Date
        if not date_str and fields_needed['date']:
            date_match = date_pattern.search(line)
            if date_match:
                date_str = date_match.group(0).replace('/', '-')
        
        # Find Amount
        if not amount_str:
            amount_match = amount_pattern.search(line)
            if amount_match:
                amount = amount_match.group(2).replace(',', '')
                amount_str = f"USD-{amount}"
        
        # Find Invoice Number
        if not invoice_str:
            invoice_match = invoice_pattern.search(line)
            if invoice_match:
                invoice_str = invoice_match.group(2).strip().upper().replace(' ', '_')
        
        # Find Reference Number
        if not reference_str and not invoice_str:
            reference_match = reference_pattern.search(line)
            if reference_match:
                reference_str = reference_match.group(2).strip().upper().replace(' ', '_')
        
        # Find Custom Search Term
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
        
        # Find Targeted Label
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
            except Exception as e:
                print(f"Error during targeted label search: {e}")
        
        # EARLY EXIT optimization
        if (date_str and 
            (not custom_search_term or custom_match_str) and 
            (not targeted_label_term or targeted_label_str)):
            print("[OPTIMIZATION] All required fields found, stopping early")
            break

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
        'timestamp': datetime.datetime.now().strftime('%H%M%S'),
        'original_filename': metadata.get('original_filename', 'file')  # NEW: Keep original name
    }
    
    for key in component_list:
        if value := component_map.get(key):
            name_parts.append(str(value))
            
    if not name_parts:
        name_parts.extend([datetime.date.today().strftime('%Y%m%d'), "EMPTY_OCR"])
            
    core_name = separator.join(name_parts)
    safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '', core_name).replace(' ', '_')
    
    return f"{safe_name}{original_extension}"
