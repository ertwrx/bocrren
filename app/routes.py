# app/routes.py

import os
from flask import Blueprint, request, jsonify, send_from_directory, current_app
from . import services

main_bp = Blueprint('main_bp', __name__)

@main_bp.route('/')
def index():
    """Serves the index.html file from the static folder."""
    return send_from_directory(current_app.static_folder, 'index.html')


@main_bp.route('/ocr-rename', methods=['POST'])
def ocr_rename():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        # Get the original filename and extension
        original_filename = file.filename
        _, original_ext = os.path.splitext(original_filename.lower())
        
        # Get the raw configuration from the form
        custom_prefix = request.form.get('custom_prefix', '').strip()
        separator = request.form.get('separator', '_')
        
        # Get custom search terms
        custom_search_term = request.form.get('custom_search_term', '').strip()
        targeted_label_term = request.form.get('targeted_label_term', '').strip()
        
        # Get the user's component selections
        component_list_str = request.form.get('component_list', '')
        component_list = [c.strip() for c in component_list_str.split(',') if c.strip()]
        
        # Extract original filename without extension for the component
        original_name_only = os.path.splitext(original_filename)[0]
        
        # Process the file using the service WITH FORCED 100% SCAN FOR DEBUGGING
        extracted_text = services.process_file_stream(
            file.stream, 
            original_ext,
            crop_top_percent=100,  # FORCE FULL SCAN
            component_list=component_list
        )
        
        # Debugging print statement
        print("----- TESSERACT RAW OUTPUT -----\n", extracted_text, "\n------------------------------")
        
        # Extract metadata with both search terms
        metadata = services.extract_metadata(extracted_text, custom_search_term, targeted_label_term)
        
        # Add original filename to metadata
        metadata['original_filename'] = original_name_only
        
        # Create suggested filename
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
