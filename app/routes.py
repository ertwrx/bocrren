# app/routes.py

import os
# We need to import 'send_from_directory' and access the 'current_app'
from flask import Blueprint, request, jsonify, send_from_directory, current_app
from . import services

main_bp = Blueprint('main_bp', __name__)

# --- NEW CODE BLOCK TO SERVE THE HOMEPAGE ---
@main_bp.route('/ocr-rename', methods=['POST'])
def ocr_rename():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        # Get file extension first
        _, file_extension = os.path.splitext(file.filename.lower())
        
        # 1. Get the raw configuration from the form
        custom_prefix = request.form.get('custom_prefix', '').strip()
        separator = request.form.get('separator', '_')
        component_list = []  # Initialize empty list
        
        # Get the user's component selections from the checkboxes
        component_list_str = request.form.get('component_list', '')
        selected_components = [c.strip() for c in component_list_str.split(',') if c.strip()]
        
        # Check which pattern matching is being used
        targeted_label_term = request.form.get('targeted_label_term', '').strip()
        custom_search_term = request.form.get('custom_search_term', '').strip()

        # Process the file
        extracted_text = services.process_file_stream(file.stream, file_extension)
        print("----- TESSERACT RAW OUTPUT -----\n", extracted_text, "\n------------------------------")
        
        # Extract metadata with both search terms
        metadata = services.extract_metadata(extracted_text, custom_search_term, targeted_label_term)
        
        # Use only one pattern matching component
        if targeted_label_term and metadata.get('targeted_label'):
            component_list = ['targeted_label']  # Use only targeted label if it found a match
        elif custom_search_term and metadata.get('custom_match'):
            component_list = ['custom_match']    # Use custom match as fallback
        
        # Add other selected components after the pattern match
        component_list.extend([c for c in selected_components if c not in component_list])
        
        # Create the suggested name
        suggested_name = services.create_suggested_name(
            metadata, file_extension, custom_prefix, separator, component_list
        )

        return jsonify({
            'original_name': file.filename,
            'extracted_text': extracted_text,
            'suggested_name': suggested_name,
            'metadata': metadata
        })

    except Exception as e:
        print(f"Error in ocr_rename: {str(e)}")  # Add debug print
        return jsonify({'error': str(e)}), 500
