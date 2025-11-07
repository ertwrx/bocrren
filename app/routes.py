# app/routes.py

import os
# We need to import 'send_from_directory' and access the 'current_app'
from flask import Blueprint, request, jsonify, send_from_directory, current_app
from . import services

main_bp = Blueprint('main_bp', __name__)

# --- NEW CODE BLOCK TO SERVE THE HOMEPAGE ---
@main_bp.route('/')
def index():
    """Serves the index.html file from the static folder."""
    # current_app.static_folder points to the 'static' directory
    return send_from_directory(current_app.static_folder, 'index.html')
# --- END OF NEW CODE BLOCK ---


@main_bp.route('/ocr-rename', methods=['POST'])
def ocr_rename():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        # --- START OF MODIFIED LOGIC ---

        # 1. Get the raw configuration from the form
        custom_prefix = request.form.get('custom_prefix', '').strip()
        separator = request.form.get('separator', '_')
        component_list_str = request.form.get('component_list', 'date,vendor')
        component_list = [c.strip() for c in component_list_str.split(',') if c.strip()]
        custom_search_term = request.form.get('custom_search_term', '').strip()

        # 2. **INTELLIGENTLY MODIFY THE COMPONENT LIST**
        # If the user is searching for a custom term, we should USE it in the filename.
        # We'll put it at the very beginning of the list for priority.
        if custom_search_term and 'custom_match' not in component_list:
            component_list.insert(0, 'custom_match') # Prepend 'custom_match' to the list

        # --- END OF MODIFIED LOGIC ---

        original_filename = file.filename
        _, original_ext = os.path.splitext(original_filename.lower())
        
        # Process the file using the service
        extracted_text = services.process_file_stream(file.stream, original_ext)
        
        # Debugging print statement (can be removed later)
        print("----- TESSERACT RAW OUTPUT -----\n", extracted_text, "\n------------------------------")
        
        # Extract metadata and create a name
        metadata = services.extract_metadata(extracted_text, custom_search_term)
        
        # The component_list is now guaranteed to include 'custom_match' if it was used.
        suggested_name = services.create_suggested_name(
            metadata, original_ext, custom_prefix, separator, component_list
        )

        return jsonify({
            'original_name': original_filename,
            'extracted_text': extracted_text,
            'suggested_name': suggested_name,
            'metadata': metadata
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
