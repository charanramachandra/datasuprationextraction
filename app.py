import os
import io
import uuid
import cv2
import numpy as np
import openpyxl
import pandas as pd
from flask import Flask, current_app, json, render_template, request, jsonify, send_from_directory, redirect, url_for, flash, session, send_file
from flask_cors import CORS
import mysql.connector
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from google.cloud import vision
from image_processing import detect_text, find_first_coordinates, crop_and_save, detect_text_in_cropped_image,get_target_text_coordinates
from PIL import Image
from json import JSONDecodeError

app = Flask(__name__)
CORS(app)

app.secret_key = 'your_secret_key_here'  # Needed for flashing messages
UPLOAD_FOLDER = 'uploads'
CROPPED_FOLDER = 'cropped'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Ensure the upload and cropped folders exist
for folder in [UPLOAD_FOLDER, CROPPED_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CROPPED_FOLDER'] = CROPPED_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Google Cloud Vision client
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "C:/newprojectkatachi/dataseparationxtract-51a0f689437b.json"
client = vision.ImageAnnotatorClient()


def get_db_connection():
    return mysql.connector.connect(
        host='localhost',  # Use the public IP of your Cloud SQL instance
        database='katachinew',  # Your database name
        user='root',            # Your Cloud SQL username (can be 'root' or other)
        password=''  # Your Cloud SQL user password
    )

def detect_text(image_path):
    """Detects text in an image file using Google Cloud Vision API."""
    with io.open(image_path, 'rb') as image_file:
        content = image_file.read()
    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    return texts

def find_first_coordinates(texts, target_texts):
    """Finds coordinates of the first occurrence of specific texts."""
    for text in texts:
        detected_text = text.description.strip()
        if detected_text in target_texts:
            vertices = [(vertex.x, vertex.y) for vertex in text.bounding_poly.vertices]
            if len(vertices) == 4:
                return vertices
    return None

def crop_and_save(image_path, coordinates,top_offset, left_offset, right_offset, bottom_offset):
    """Crops the image based on coordinates and saves it."""
    if coordinates is None:
        return None

    image = cv2.imread(image_path)
    x_coords = [pt[0] for pt in coordinates]
    y_coords = [pt[1] for pt in coordinates]
        
    x_min = min(x_coords) - left_offset
    x_max = max(x_coords) + right_offset
    y_min = min(y_coords) - top_offset
    y_max = max(y_coords) + bottom_offset

    x_min = max(x_min, 0)
    x_max = min(x_max, image.shape[1])
    y_min = max(y_min, 0)
    y_max = min(y_max, image.shape[0])

    cropped_image = image[y_min:y_max, x_min:x_max]
    output_path = os.path.join(app.config['CROPPED_FOLDER'], 'cropped_image.jpg')
    cv2.imwrite(output_path, cropped_image)
    
    return output_path

def detect_text_in_cropped_image(cropped_image_path):
    """Detects text in the cropped image using Google Cloud Vision API."""
    with io.open(cropped_image_path, 'rb') as image_file:
        content = image_file.read()
    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    if texts:
        return texts[0].description.strip()
    else:
        return '切り取られた画像にテキストは検出されませんでした。'


@app.route('/userpage')
def userpage():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    return render_template('userpage.html')

#  ------------------------------------------------------- Records 1 to 4 dashbord section ----------------------------------------------------------#

@app.route('/record1')
def record1():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    return render_template('record1.html')

@app.route('/record2')
def record2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    return render_template('record2.html')

@app.route('/record3')
def record3():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    return render_template('record3.html')

@app.route('/record4')
def record4():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    return render_template('record4.html')


#  ------------------------------------------------------- End of the Records 1 to 4 dashbord section ----------------------------------------------------------#



#------------------------------------------------------------------- address section ----------------------------------------------------------------#

@app.route('/process_image')
def process_image():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the folder paths
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'
    
    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]
    # print("Image paths:", image_paths)
    
    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Fetch the count of distinct users who have an address for the current image
                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (address IS NOT NULL AND address <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""


                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません'
                    already_processed = True

                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'address'
                """, (image_name,))
                skipped_section_result = cur.fetchone()

                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません'
                    already_processed = True
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s 
                    AND (address IS NOT NULL AND address <> '')
                """, (image_name,))
                user_count_result = cur.fetchone()
                cur.fetchall()  # Ensure all results are fetched

                

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the address column is filled by at least two distinct users, set a flash message
                    flash_message = '処理済み.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()
                cur.fetchall()  # Ensure all results are fetched

                if result and result['address']:  # If address column is not empty
                    already_processed = True
                    flash('処理済み.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_texts = {'住', '住所'}  # Text patterns you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_texts)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=8, left_offset=80, right_offset=680, bottom_offset=22)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."
                
                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                   
                    return render_template('process_image.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=session['current_index'], 
                                           total_images=len(image_paths),
                                           already_processed=True)

                # Increment index for the next image
               
                return render_template('process_image.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=session['current_index'], 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()
    
    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/save_image_data', methods=['POST'])
def save_image_data():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = request.form['username']
    image_name = request.form['image_name']
    address = request.form['address']

    if not username:
        flash('Username is missing.')
        return redirect(url_for('process_image'))

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Handle user_images table
        cur.execute("""
            SELECT id FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s AND (address IS NULL OR address = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET address = %s
                WHERE id = %s
                """, (address, existing_record[0]))
            flash('Image data updated successfully.')
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, address) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, address))
            flash('Image data saved successfully.')

        connection.commit()

        # Now check and handle final_data table
        cur.execute("""
            SELECT address FROM user_images WHERE image_name = %s AND (address IS NOT NULL AND address <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        # Process results as tuples
        if len(existing_records) >= 2:
            address_list = [record[0] for record in existing_records]
            if len(set(address_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET address = %s
                        WHERE id = %s
                        """, (address_list[0], final_data_record[0]))
                    flash('Image data updated in final_data successfully.')
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, address)
                        VALUES (%s, %s)
                        """, (image_name, address_list[0]))
                    flash('Image data saved to final_data successfully.')

                connection.commit()
            else:
                flash('Addresses do not match; no data saved to final_data.')

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        flash('Failed to save image data.')
    finally:
        connection.close()
    
    return jsonify({'success': True}), 200




@app.route('/next_image')
def next_image():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
    return redirect(url_for('process_image'))

@app.route('/previous_image')
def previous_image():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
    return redirect(url_for('process_image'))



@app.route('/skip_section', methods=['POST'])
def skip_section():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'Address'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("""INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)""", (image_name, skipped_section,reason))
    connection.commit()
    connection.close()
    return jsonify({'success': True}), 200
    

# --------------------------------------------------- End of the addresss section ------------------------------------------------------ #



# ---------------------------------------------------- compony name section ------------------------------------------------------------ #

@app.route('/compony_name')
def compony_name():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'
    
    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    if current_index >= len(image_paths):
        flash('No more images to process.')
        return redirect(url_for('upload_files'))

    image_path = image_paths[current_index]
    image_name = os.path.basename(image_path)

    if not os.path.exists(image_path):
        flash(f'Image file not found: {image_path}')
        return redirect(url_for('upload_files'))

    connection = get_db_connection()
    try:
        with connection.cursor(dictionary=True) as cur:
            # Check how many distinct users have filled the company_name column for the current image

            cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (company_name IS NOT NULL AND company_name <> '')
                """, (image_name,))
            skipped_section = cur.fetchone()
            

            already_processed = False
            flash_message = ""

            if skipped_section:
                flash_message = 'この画像は適切ではありません。'
                already_processed = True

            cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'Company Name'
                """, (image_name,))
            skipped_section_result = cur.fetchone()
            
           

            if skipped_section_result:
                flash_message = 'この画像は適切ではありません。'
                already_processed = True

            cur.execute("""
                SELECT COUNT(DISTINCT user_id) as user_count
                FROM user_images
                WHERE image_name = %s
                AND (company_name IS NOT NULL AND company_name <> '');
            """, (image_name,))
            user_count_result = cur.fetchone()
            cur.fetchall()  # Discard any remaining unread results

           

            if user_count_result and user_count_result['user_count'] >= 2:
                # If the company_name column is filled by at least two distinct users, set a flash message
                flash_message = 'This image has been processed by multiple users and will not be shown again.'
                already_processed = True

            # Check if the image has been processed by the current user
            cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
            result = cur.fetchone()
            cur.fetchall()  # Discard any remaining unread results

            if result and result['company_name']:  # If company_name column is not empty
                already_processed = True
                flash('This image has already been processed and its company name has been added.')

            if not already_processed:
                # Process the image if it has not been processed yet
                target_texts = {'氏', '氏名'}  # Text patterns you want to detect
                if not os.path.exists(image_path):
                    flash(f'Image file not found: {image_path}')
                    return redirect(url_for('upload_files'))

                texts = detect_text(image_path)
                first_coordinates = find_first_coordinates(texts, target_texts)
                cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=8, left_offset=80, right_offset=680, bottom_offset=26)
                
                if cropped_image_path:
                    base_name = os.path.basename(cropped_image_path)
                    new_base_name = f"{uuid.uuid4()}_{base_name}"
                    new_cropped_image_path = os.path.join(static_folder, new_base_name)
                    
                    try:
                        if os.path.exists(cropped_image_path):
                            os.rename(cropped_image_path, new_cropped_image_path)
                            extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                            image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                        else:
                            flash('Cropped image file not found.')
                            extracted_text = "No target text found."
                    except Exception as e:
                        flash(f'Error processing image: {e}')
                        extracted_text = "No target text found."
                else:
                    extracted_text = "No target text found."

            if flash_message:
                flash(flash_message)
                return render_template('compony_name.html', 
                                       username=username,
                                       extracted_text=extracted_text,
                                       image_url=None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=True)

            return render_template('compony_name.html', 
                                   username=username,
                                   extracted_text=extracted_text, 
                                   image_url=image_url if not already_processed else None,
                                   image_name=image_name,
                                   current_index=current_index, 
                                   total_images=len(image_paths),
                                   already_processed=already_processed)
    
    finally:
        connection.close()


@app.route('/coponyname_save', methods=['POST'])
def coponyname_save():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = request.form['username']
    image_name = request.form['image_name']
    company_name = request.form['address']  # Corrected from 'address' to 'company_name'

    if not username:
        flash('Username is missing.')
        return redirect(url_for('compony_name'))

    connection = get_db_connection()
   
    try:
        cur = connection.cursor()

        # Search for existing record in user_images
        cur.execute("""
            SELECT id FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s AND (company_name IS NULL OR company_name = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET company_name = %s
                WHERE id = %s
                """, (company_name, existing_record[0]))
            flash('Company name updated successfully.')
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, company_name) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, company_name))
            flash('Company name saved successfully.')

        connection.commit()

        # Now check and handle final_data table
        cur.execute("""
            SELECT company_name FROM user_images WHERE image_name = %s AND (company_name IS NOT NULL AND company_name <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            company_list = [record[0] for record in existing_records]
            if len(set(company_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET company_name = %s
                        WHERE id = %s
                        """, (company_list[0], final_data_record[0]))
                    flash('Company name updated in final_data successfully.')
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, company_name)
                        VALUES (%s, %s)
                        """, (image_name, company_list[0]))
                    flash('Company name saved to final_data successfully.')

                connection.commit()
            else:
                flash('Company names do not match; no data saved to final_data.')

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        flash('Failed to save company name.')
    finally:
        connection.close()
    
    return jsonify({'success': True}), 200

    


@app.route('/next_image2')
def next_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
    return redirect(url_for('compony_name'))

@app.route('/previous_image2')
def previous_image2():
    if 'image_paths' in session and 'current_index' in session:
        # Ensure current_index is within the valid range
        if len(session['image_paths']) > 0:
            # Calculate the previous index, ensuring it wraps around correctly
            session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        else:
            flash('No images available to navigate.')
    else:
        flash('Session data not available.')

    # Redirect to the appropriate route. Make sure 'compony_name' is the correct endpoint.
    return redirect(url_for('compony_name'))



@app.route('/skip_section_name', methods=['POST'])
def skip_section_name():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'Company Name'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200

# ---------------------------------------------------- End of the compony name section -------------------------------------------------------#




# ---------------------------------------------------- compony owner name section ------------------------------------------------------------#

@app.route('/compony_owner_name')
def compony_owner_name():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the company_owner_name column for the current image
                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (company_owner_name IS NOT NULL AND company_owner_name <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True

                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'Company Owner Name'
                """, (image_name,))
                skipped_section_result = cur.fetchone()


                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True

                cur.execute("""
                        SELECT COUNT(DISTINCT user_id) as user_count
                        FROM user_images
                        WHERE image_name = %s
                        AND (company_owner_name IS NOT NULL AND company_owner_name <> '');
                    """, (image_name,))

                user_count_result = cur.fetchone()

                

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the company_owner_name column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['company_owner_name']:  # If company_owner_name column is not empty
                    already_processed = True
                    flash('This image has already been processed and its owner name has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_texts = {'氏', '氏名'}  # Text patterns you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_texts)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=6, left_offset=80, right_offset=680, bottom_offset=80)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                # Explicitly fetch all rows from the cursor to avoid unread results error
                cur.fetchall()

                if flash_message:
                    flash(flash_message)
                    return render_template('compony_owner_name.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('compony_owner_name.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/ownext_image2')
def ownext_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
    return redirect(url_for('compony_owner_name'))

@app.route('/owprevious_image2')
def owprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
    return redirect(url_for('compony_owner_name'))



@app.route('/company_owner_name_save', methods=['POST'])
def company_owner_name_save():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']
    username = request.form['username']
    image_name = request.form['image_name']
    company_owner_name = request.form['address']  # Assuming 'address' is the input field name for company owner name

    if not username:
        return jsonify({'error': 'Username is missing'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record in user_images
        cur.execute("""
            SELECT id FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s AND (company_owner_name IS NULL OR company_owner_name = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record in user_images
            cur.execute("""
                UPDATE user_images
                SET company_owner_name = %s
                WHERE id = %s
                """, (company_owner_name, existing_record[0]))
            message = 'Company owner name updated successfully.'
        else:
            # Insert a new record into user_images
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, company_owner_name) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, company_owner_name))
            message = 'Company owner name saved successfully.'

        connection.commit()

        # Now check and handle final_data table
        cur.execute("""
            SELECT company_owner_name FROM user_images WHERE image_name = %s AND (company_owner_name IS NOT NULL AND company_owner_name <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            owner_list = [record[0] for record in existing_records]
            if len(set(owner_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET company_owner_name = %s
                        WHERE id = %s
                        """, (owner_list[0], final_data_record[0]))
                    message = 'Company owner name updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, company_owner_name)
                        VALUES (%s, %s)
                        """, (image_name, owner_list[0]))
                    message = 'Company owner name saved to final_data successfully.'

                connection.commit()
            else:
                message = 'Company owner names do not match; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        message = 'Failed to save company owner name.'
        return jsonify({'error': message}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_section_ownname', methods=['POST'])
def skip_section_ownname():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'Company Owner Name'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()
    return jsonify({'success': True}), 200
    

# ---------------------------------------------------- End of the compony owner name section -------------------------------------------------#



# ---------------------------------------------------- Phone number section ------------------------------------------------------------------#
@app.route('/phone_number')
def phone_number():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the telephone_number column for the current image
                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (telephone_number IS NOT NULL AND telephone_number <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True



                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'Phone Number'
                """, (image_name,))
                skipped_section_result = cur.fetchone()


                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True


                cur.execute("""
                        SELECT COUNT(DISTINCT user_id) as user_count
                        FROM user_images
                        WHERE image_name = %s
                        AND (telephone_number IS NOT NULL AND telephone_number <> '');
                    """, (image_name,))

                user_count_result = cur.fetchone()

                

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the telephone_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['telephone_number']:  # If telephone_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its phone number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_texts = {'電話'}  # Text patterns you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_texts)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=8, left_offset=80, right_offset=680, bottom_offset=26)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('phone_number.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('phone_number.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))




@app.route('/phnext_image2')
def phnext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('phone_number'))

@app.route('/phprevious_image2')
def phprevious_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
     return redirect(url_for('phone_number'))



@app.route('/phone_number_save', methods=['POST'])
def phone_number_save():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']
    username = request.form['username']
    image_name = request.form['image_name']
    telephone_number = request.form['address']  # Assuming 'address' is the correct field for telephone_number

    if not username:
        return jsonify({'error': 'Username is missing'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record in user_images
        cur.execute("""
            SELECT id FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s AND (telephone_number IS NULL OR telephone_number = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record in user_images
            cur.execute("""
                UPDATE user_images
                SET telephone_number = %s
                WHERE id = %s
                """, (telephone_number, existing_record[0]))
            message = 'Telephone number updated successfully.'
        else:
            # Insert a new record into user_images
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, telephone_number) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, telephone_number))
            message = 'Telephone number saved successfully.'

        connection.commit()

        # Now check and handle final_data table
        cur.execute("""
            SELECT telephone_number FROM user_images WHERE image_name = %s AND (telephone_number IS NOT NULL AND telephone_number <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            phone_list = [record[0] for record in existing_records]
            if len(set(phone_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET telephone_number = %s
                        WHERE id = %s
                        """, (phone_list[0], final_data_record[0]))
                    message = 'Telephone number updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, telephone_number)
                        VALUES (%s, %s)
                        """, (image_name, phone_list[0]))
                    message = 'Telephone number saved to final_data successfully.'

                connection.commit()
            else:
                message = 'Telephone numbers do not match; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        message = 'Failed to save telephone number.'
        return jsonify({'error': message}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200


@app.route('/skip_section_phone', methods=['POST'])
def skip_section_phone():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'Phone Number'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()
    return jsonify({'success': True}), 200
   

#

# ----------------------------------------------------End of  Phone number section ------------------------------------------------------------------#



# ---------------------------------------------------- Compony_name_2 section ------------------------------------------------------------------#

@app.route('/compony_name_2')
def compony_name_2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the company_name2 column for the current image

                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (company_name2 IS NOT NULL AND company_name2 <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True



                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'Company Name 2'
                """, (image_name,))
                skipped_section_result = cur.fetchone()


                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True



                cur.execute("""
                        SELECT COUNT(DISTINCT user_id) as user_count
                        FROM user_images
                        WHERE image_name = %s
                        AND (company_name2 IS NOT NULL AND company_name2 <> '');
                    """, (image_name,))

                user_count_result = cur.fetchone()

                

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the company_name2 column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['company_name2']:  # If company_name2 column is not empty
                    already_processed = True
                    flash('This image has already been processed and its company name has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = '事業場の名称'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-330, left_offset=200, right_offset=780, bottom_offset=360)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('compony_name_2.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('compony_name_2.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/connext_image2')
def connext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('compony_name_2'))

@app.route('/conprevious_image2')
def conprevious_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
     return redirect(url_for('compony_name_2'))



@app.route('/compony_name_2_save', methods=['POST'])
def compony_name_2_save():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']
    username = request.form['username']
    image_name = request.form['image_name']
    company_name2 = request.form['address']  # Assuming 'address' is the correct field for company_name2

    if not username:
        return jsonify({'error': 'Username is missing'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record in user_images
        cur.execute("""
            SELECT id FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s AND (company_name2 IS NULL OR company_name2 = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record in user_images
            cur.execute("""
                UPDATE user_images
                SET company_name2 = %s
                WHERE id = %s
                """, (company_name2, existing_record[0]))
            message = 'Company name 2 updated successfully.'
        else:
            # Insert a new record into user_images
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, company_name2) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, company_name2))
            message = 'Company name 2 saved successfully.'

        connection.commit()

        # Now check and handle final_data table
        cur.execute("""
            SELECT company_name2 FROM user_images WHERE image_name = %s AND (company_name2 IS NOT NULL AND company_name2 <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            company_list = [record[0] for record in existing_records]
            if len(set(company_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET company_name2 = %s
                        WHERE id = %s
                        """, (company_list[0], final_data_record[0]))
                    message = 'Company name 2 updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, company_name2)
                        VALUES (%s, %s)
                        """, (image_name, company_list[0]))
                    message = 'Company name 2 saved to final_data successfully.'

                connection.commit()
            else:
                message = 'Company name 2 does not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        message = 'Failed to save company name 2.'
        return jsonify({'error': message}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200


@app.route('/skip_section_cmpname2', methods=['POST'])
def skip_section_cmpname2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'Company Name 2'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()
    return jsonify({'success': True}), 200
    

# ------------------------------------------------------- End of the Compony_name_2 section ------------------------------------------------------------------#




# ---------------------------------------------------- Company_address_2 section ------------------------------------------------------------------#

@app.route('/company_address_2')
def company_address_2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the company_address2 column for the current image

                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (company_address2 IS NOT NULL AND company_address2 <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True

                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'Company Address 2'
                """, (image_name,))
                skipped_section_result = cur.fetchone()

                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = False


                cur.execute("""
                        SELECT COUNT(DISTINCT user_id) as user_count
                        FROM user_images
                        WHERE image_name = %s
                        AND (company_address2 IS NOT NULL AND company_address2 <> '');
                    """, (image_name,))

                user_count_result = cur.fetchone()

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the company_address2 column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['company_address2']:  # If company_address2 column is not empty
                    already_processed = True
                    flash('This image has already been processed and its address has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = '所在地'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=5, left_offset=200, right_offset=660, bottom_offset=20)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('company_address_2.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('company_address_2.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))




@app.route('/conadnext_image2')
def conadnext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('company_address_2'))

@app.route('/conadprevious_image2')
def conadprevious_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
     return redirect(url_for('company_address_2'))



@app.route('/compony_address_2_save', methods=['POST'])
def compony_address_2_save():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    company_address2 = request.form.get('address')  # Assuming 'address' is the company address

    if not username:
        return jsonify({'error': 'Username is missing'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record in user_images
        cur.execute("""
            SELECT id FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s AND (company_address2 IS NULL OR company_address2 = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record in user_images
            cur.execute("""
                UPDATE user_images
                SET company_address2 = %s
                WHERE id = %s
                """, (company_address2, existing_record[0]))
            message = 'Company address updated successfully.'
        else:
            # Insert a new record into user_images
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, company_address2) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, company_address2))
            message = 'Company address saved successfully.'

        connection.commit()

        # Now check and handle final_data table
        cur.execute("""
            SELECT company_address2 FROM user_images WHERE image_name = %s AND (company_address2 IS NOT NULL AND company_address2 <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            address_list = [record[0] for record in existing_records]
            if len(set(address_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET company_address2 = %s
                        WHERE id = %s
                        """, (address_list[0], final_data_record[0]))
                    message = 'Company address updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, company_address2)
                        VALUES (%s, %s)
                        """, (image_name, address_list[0]))
                    message = 'Company address saved to final_data successfully.'

                connection.commit()
            else:
                message = 'Company address does not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        message = 'Failed to save company address.'
        return jsonify({'error': message}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200




@app.route('/skip_section_cmpadd2', methods=['POST'])
def skip_section_cmpadd2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'Company Address 2'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()
    return jsonify({'success': True}), 200



# ------------------------------------------------------- End of the Company_address_2 section ------------------------------------------------------------------#



# ---------------------------------------------------- Code Number section ------------------------------------------------------------------#

@app.route('/code_number')
def code_number():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the code_number column for the current image

                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (code_number IS NOT NULL AND code_number <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True

                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'Code Number'
                """, (image_name,))
                skipped_section_result = cur.fetchone()

                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True

                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (code_number IS NOT NULL AND code_number <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the code_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['code_number']:  # If code_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its code number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = '業種'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=10, left_offset=150, right_offset=780, bottom_offset=24)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('code_number.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('code_number.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))


@app.route('/codnmnext_image2')
def codnmnext_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
    return redirect(url_for('code_number'))

@app.route('/codnmprevious_image2')
def codnmprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
    return redirect(url_for('code_number'))





@app.route('/codenum_save', methods=['POST'])
def codenum_save():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    code_number = request.form.get('address')  # Assuming 'address' is the code_number field

    if not username:
        return jsonify({'error': 'Username is missing'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record in user_images
        cur.execute("""
            SELECT id FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s AND (code_number IS NULL OR code_number = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record in user_images
            cur.execute("""
                UPDATE user_images
                SET code_number = %s
                WHERE id = %s
                """, (code_number, existing_record[0]))
            message = 'Code number updated successfully.'
        else:
            # Insert a new record into user_images
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, code_number) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, code_number))
            message = 'Code number saved successfully.'

        connection.commit()

        # Now check and handle final_data table
        cur.execute("""
            SELECT code_number FROM user_images WHERE image_name = %s AND (code_number IS NOT NULL AND code_number <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            code_list = [record[0] for record in existing_records]
            if len(set(code_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET code_number = %s
                        WHERE id = %s
                        """, (code_list[0], final_data_record[0]))
                    message = 'Code number updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, code_number)
                        VALUES (%s, %s)
                        """, (image_name, code_list[0]))
                    message = 'Code number saved to final_data successfully.'

                connection.commit()
            else:
                message = 'Code numbers do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        message = 'Failed to save code number.'
        return jsonify({'error': message}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200




@app.route('/skip_section_codenum', methods=['POST'])
def skip_section_codenum():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'Code Number'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()
    return jsonify({'success': True}), 200

# ------------------------------------------------------- End of the Code Number section ------------------------------------------------------------------#



# ------------------------------------------------------ Phone number 2 section ------------------------------------------------------------------#


def crop_and_save_new(image_path, coordinates, top_offset=8, left_offset=80, right_offset=200, bottom_offset=12):
    """
    Crop the image based on the provided coordinates and save the cropped image.
    """
    x_coords = [pt[0] for pt in coordinates]
    y_coords = [pt[1] for pt in coordinates]

    image = Image.open(image_path)
    x_min = max(min(x_coords) - left_offset, 0)
    x_max = min(max(x_coords) + right_offset, image.width)
    y_min = max(min(y_coords) - top_offset, 0)
    y_max = min(max(y_coords) + bottom_offset, image.height)

    cropped_image = image.crop((x_min, y_min, x_max, y_max))

    cropped_image_path = os.path.join('cropped', os.path.basename(image_path))
    cropped_image.save(cropped_image_path)

    return cropped_image_path

def find_all_coordinates_new(texts, target_texts):
    """
    Find all coordinates of target texts in the detected texts.
    """
    occurrences = []

    for text in texts:
        description = text.description  # Attribute access for 'description'
        if any(target in description for target in target_texts):
            vertices = text.bounding_poly.vertices  # Attribute access for 'boundingPoly'
            coordinates = [(v.x, v.y) for v in vertices]  # Attribute access for vertices
            occurrences.append((description, coordinates))

    return occurrences

@app.route('/phone_number_2')
def phone_number_2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        try:
            with get_db_connection() as connection:
                cur = connection.cursor(dictionary=True)
                
                # Check how many distinct users have filled the telephone_number2 column for the current image

                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (telephone_number2 IS NOT NULL AND telephone_number2 <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True


                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'Phone Number 2'
                """, (image_name,))
                skipped_section_result = cur.fetchone()

               
                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True



                cur.execute(
                    """SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (telephone_number2 IS NOT NULL AND telephone_number2 <> '');
                     """, (image_name,))
                user_count_result = cur.fetchone()

                
                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the telephone_number2 column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", 
                            (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['telephone_number2']:
                    already_processed = True
                    flash('This image has already been processed and its telephone number has been added.')

                if not already_processed:
                    target_texts = ['電話']  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    if texts is None:
                        flash('Text detection failed. Please try again.')
                        return redirect(url_for('upload_files'))

                    occurrences = find_all_coordinates_new(texts, target_texts)

                    # Debugging: Print all occurrences
                    for i, (description, coords) in enumerate(occurrences):
                        print(f"Coordinates: {coords}")

                    if len(occurrences) >= 3:
                        # Selecting the third occurrence
                        third_coordinates = occurrences[2][1]  # Index 2 for the third occurrence
                        cropped_image_path = crop_and_save_new(image_path, third_coordinates, 
                                                               top_offset=22, left_offset=80, 
                                                               right_offset=350, bottom_offset=20)

                        if cropped_image_path:
                            base_name = os.path.basename(cropped_image_path)
                            new_base_name = f"{uuid.uuid4()}_{base_name}"
                            new_cropped_image_path = os.path.join(static_folder, new_base_name)

                            try:
                                if os.path.exists(cropped_image_path):
                                    os.rename(cropped_image_path, new_cropped_image_path)
                                    extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                    image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                                else:
                                    flash('Cropped image file not found.')
                                    extracted_text = "No target text found."
                            except Exception as e:
                                flash(f'Error processing image: {e}')
                                extracted_text = "No target text found."
                        else:
                            extracted_text = "No target text found."
                    else:
                        flash('Not enough occurrences of the target text found.')

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('phone_number_2.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('phone_number_2.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)

        except Exception as e:
            flash(f'Error accessing the database: {e}')
            return redirect(url_for('upload_files'))

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/ph2next_image2')
def ph2next_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('phone_number_2'))

@app.route('/ph2previous_image2')
def ph2previous_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('phone_number_2'))




@app.route('/phone_number_save2', methods=['POST'])
def phone_number_save2():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    telephone_number2 = request.form.get('address')  # Assuming 'address' is the correct field for telephone_number2

    if not username:
        return jsonify({'error': 'Username is missing'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record in user_images
        cur.execute("""
            SELECT id FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s AND (telephone_number2 IS NULL OR telephone_number2 = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record in user_images
            cur.execute("""
                UPDATE user_images
                SET telephone_number2 = %s
                WHERE id = %s
                """, (telephone_number2, existing_record[0]))
            message = 'Telephone number updated successfully.'
        else:
            # Insert a new record into user_images
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, telephone_number2) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, telephone_number2))
            message = 'Telephone number saved successfully.'

        connection.commit()

        # Now check and handle final_data table
        cur.execute("""
            SELECT telephone_number2 FROM user_images WHERE image_name = %s AND (telephone_number2 IS NOT NULL AND telephone_number2 <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            phone_list = [record[0] for record in existing_records]
            if len(set(phone_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET telephone_number2 = %s
                        WHERE id = %s
                        """, (phone_list[0], final_data_record[0]))
                    message = 'Telephone number updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, telephone_number2)
                        VALUES (%s, %s)
                        """, (image_name, phone_list[0]))
                    message = 'Telephone number saved to final_data successfully.'

                connection.commit()
            else:
                message = 'Telephone numbers do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        message = 'Failed to save telephone number.'
        return jsonify({'error': message}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200




@app.route('/skip_section_phnum2', methods=['POST'])
def skip_section_phnum2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'Phone Number 2'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()
    return jsonify({'success': True}), 200


# ------------------------------------------------------End of Phone number 2 section ------------------------------------------------------------------#




# ------------------------------------------------------ R1 Record  number  section ------------------------------------------------------------------#

@app.route('/R1record_number', methods=['GET'])
def R1record_number():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (R1_record_number IS NOT NULL AND R1_record_number <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True


                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'R1 Record Number'
                """, (image_name,))
                skipped_section_result = cur.fetchone()

               
                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True

                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R1_record_number IS NOT NULL AND R1_record_number <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()


                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = '処理済み'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R1_record_number']:  # If record_number column is not empty
                    already_processed = True
                    flash('処理済み')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=16, left_offset=1250, right_offset=-230, bottom_offset=110)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R1recordnumber.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R1recordnumber.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/recnext_image2')
def recnext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R1record_number'))

@app.route('/recprevious_image2')
def recprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R1record_number'))



@app.route('/save_record', methods=['POST'])
def save_record():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    record_number = request.form.get('address')

    # Validate form data
    if not username or not image_name or not record_number:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record in user_images
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R1_record_number IS NULL OR R1_record_number = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record in user_images
            cur.execute("""
                UPDATE user_images
                SET R1_record_number = %s
                WHERE id = %s
                """, (record_number, existing_record[0]))
            message = 'Record number updated successfully.'
        else:
            # Insert a new record into user_images
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R1_record_number) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, record_number))
            message = 'Record number saved successfully.'

        connection.commit()

        # Check final_data for consistency
        cur.execute("""
            SELECT R1_record_number FROM user_images WHERE image_name = %s AND (R1_record_number IS NOT NULL AND R1_record_number <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            record_list = [record[0] for record in existing_records]
            if len(set(record_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R1_record_number = %s
                        WHERE id = %s
                        """, (record_list[0], final_data_record[0]))
                    message = 'Record number updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R1_record_number)
                        VALUES (%s, %s)
                        """, (image_name, record_list[0]))
                    message = 'Record number saved to final_data successfully.'

                connection.commit()
            else:
                message = 'Record numbers do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save record number'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200





@app.route('/skip_record', methods=['POST'])
def skip_record():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R1 Record Number'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200



# ------------------------------------------------------End of R1 Record  number  section -----------------------------------------------------------------------#



# ---------------------------------------------------------- R1 Type code section -------------------------------------------------------------------------------#

@app.route('/R1_Type_code', methods=['GET'])
def R1_Type_code():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image

                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (R1_type_code IS NOT NULL AND R1_type_code <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True


                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'R1 Type Code'
                """, (image_name,))
                skipped_section_result = cur.fetchone()

               
                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True



                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R1_type_code IS NOT NULL AND R1_type_code <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                already_processed = False
                flash_message = ""

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R1_type_code']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-88, left_offset=270, right_offset=-80, bottom_offset=115)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R1_Type_code.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R1_Type_code.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r1tcnext_image2')
def r1tcnext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R1_Type_code'))

@app.route('/r1tcprevious_image2')
def r1tcprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R1_Type_code'))



@app.route('/save_r1typecode', methods=['POST'])
def save_r1typecode():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    R1typecode = request.form.get('address')

    # Validate form data
    if not username or not image_name or not R1typecode:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R1_type_code IS NULL OR R1_type_code = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R1_type_code = %s
                WHERE id = %s
                """, (R1typecode, existing_record[0]))
            message = 'Record type code updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R1_type_code) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, R1typecode))
            message = 'Record type code saved successfully.'

        connection.commit()

        # Check consistency and save to final_data
        cur.execute("""
            SELECT R1_type_code FROM user_images 
            WHERE image_name = %s AND (R1_type_code IS NOT NULL AND R1_type_code <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            code_list = [record[0] for record in existing_records]
            if len(set(code_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R1_type_code = %s
                        WHERE id = %s
                        """, (code_list[0], final_data_record[0]))
                    message += ' Record type code updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R1_type_code)
                        VALUES (%s, %s)
                        """, (image_name, code_list[0]))
                    message += ' Record type code saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Record type codes do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save record type code'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R1typecode', methods=['POST'])
def skip_R1typecode():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R1 Type Code'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200

# ----------------------------------------------------------End of R1 Type code section -------------------------------------------------------------------------#




# ---------------------------------------------------------- R1 Weight Of The Garbage section -------------------------------------------------------------------#

@app.route('/R1_garbage_weight', methods=['GET'])
def R1_garbage_weight():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image

                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (R1_garbage_weight IS NOT NULL AND R1_garbage_weight <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True


                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'R1 garbage weight'
                """, (image_name,))
                skipped_section_result = cur.fetchone()

               
                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True

                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R1_garbage_weight IS NOT NULL AND R1_garbage_weight <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R1_garbage_weight']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-18, left_offset=100, right_offset=40, bottom_offset=120)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R1_garbage_weight.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R1_garbage_weight.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r1gbwtnext_image2')
def r1gbwtnext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R1_garbage_weight'))

@app.route('/r1gbwtprevious_image2')
def r1gbwtprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R1_garbage_weight'))




@app.route('/save_R1grbwet', methods=['POST'])
def save_R1grbwet():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    R1garbageweight = request.form.get('address')

    # Validate form data
    if not username or not image_name or not R1garbageweight:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R1_garbage_weight IS NULL OR R1_garbage_weight = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R1_garbage_weight = %s
                WHERE id = %s
                """, (R1garbageweight, existing_record[0]))
            message = 'Garbage weight updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R1_garbage_weight) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, R1garbageweight))
            message = 'Garbage weight saved successfully.'

        connection.commit()

        # Check consistency and save to final_data
        cur.execute("""
            SELECT R1_garbage_weight FROM user_images 
            WHERE image_name = %s AND (R1_garbage_weight IS NOT NULL AND R1_garbage_weight <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            weight_list = [record[0] for record in existing_records]
            if len(set(weight_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R1_garbage_weight = %s
                        WHERE id = %s
                        """, (weight_list[0], final_data_record[0]))
                    message += ' Garbage weight updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R1_garbage_weight)
                        VALUES (%s, %s)
                        """, (image_name, weight_list[0]))
                    message += ' Garbage weight saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Garbage weights do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save garbage weight'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R1grbwet', methods=['POST'])
def skip_R1grbwet():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R1 garbage weight'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()
    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End of R1 Weight Of The Garbage section --------------------------------------------------------------#



# ---------------------------------------------------------- R1 Number Of Items section --------------------------------------------------------------------------#

@app.route('/R1_number_of_items', methods=['GET'])
def R1_number_of_items():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image

                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (R1_number_of_items IS NOT NULL AND R1_number_of_items <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True


                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'R1 Number Of Items'
                """, (image_name,))
                skipped_section_result = cur.fetchone()

               
                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True

                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R1_number_of_items IS NOT NULL AND R1_number_of_items <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()


                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R1_number_of_items']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-18, left_offset=-18, right_offset=210, bottom_offset=120)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R1_number_of_items.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R1_number_of_items.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r1nuitmsnext_image2')
def r1nuitmsnext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R1_number_of_items'))

@app.route('/r1nuitmsprevious_image2')
def r1nuitmsprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R1_number_of_items'))



@app.route('/save_R1nmitms', methods=['POST'])
def save_R1nmitms():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    R1typecode = request.form.get('address')

    # Validate form data
    if not username or not image_name or not R1typecode:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R1_number_of_items IS NULL OR R1_number_of_items = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R1_number_of_items = %s
                WHERE id = %s
                """, (R1typecode, existing_record[0]))
            message = 'Record number updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R1_number_of_items) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, R1typecode))
            message = 'Record number saved successfully.'

        connection.commit()

        # Check consistency and save to final_data
        cur.execute("""
            SELECT R1_number_of_items FROM user_images 
            WHERE image_name = %s AND (R1_number_of_items IS NOT NULL AND R1_number_of_items <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            item_list = [record[0] for record in existing_records]
            if len(set(item_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R1_number_of_items = %s
                        WHERE id = %s
                        """, (item_list[0], final_data_record[0]))
                    message += ' Number of items updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R1_number_of_items)
                        VALUES (%s, %s)
                        """, (image_name, item_list[0]))
                    message += ' Number of items saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Number of items do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save record number'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R1nmitms', methods=['POST'])
def skip_R1nmitms():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R1 Number Of Items'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End of R1 Number Of Items section --------------------------------------------------------------------#



# ---------------------------------------------------------- R1 Registered Number section ------------------------------------------------------------------------#

@app.route('/R1_registered_number', methods=['GET'])
def R1_registered_number():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (R1_registered_number IS NOT NULL AND R1_registered_number <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True


                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'R1 Registered Number'
                """, (image_name,))
                skipped_section_result = cur.fetchone()

               
                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True

                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R1_registered_number IS NOT NULL AND R1_registered_number <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

               
                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R1_registered_number']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-18, left_offset=-188, right_offset=370, bottom_offset=120)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R1_registered_number.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R1_registered_number.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r1regnumnext_image2')
def r1regnumnext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R1_registered_number'))

@app.route('/r1regnumprevious_image2')
def r1regnumprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R1_registered_number'))




@app.route('/save_R1regnum', methods=['POST'])
def save_R1regnum():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    R1registerednumber = request.form.get('address')

    # Validate form data
    if not username or not image_name or not R1registerednumber:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R1_registered_number IS NULL OR R1_registered_number = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R1_registered_number = %s
                WHERE id = %s
                """, (R1registerednumber, existing_record[0]))
            message = 'Record number updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R1_registered_number) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, R1registerednumber))
            message = 'Record number saved successfully.'

        connection.commit()

        # Check consistency and save to final_data
        cur.execute("""
            SELECT R1_registered_number FROM user_images 
            WHERE image_name = %s AND (R1_registered_number IS NOT NULL AND R1_registered_number <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            registered_list = [record[0] for record in existing_records]
            if len(set(registered_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R1_registered_number = %s
                        WHERE id = %s
                        """, (registered_list[0], final_data_record[0]))
                    message += ' Record number updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R1_registered_number)
                        VALUES (%s, %s)
                        """, (image_name, registered_list[0]))
                    message += ' Record number saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Record numbers do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save record number'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200


@app.route('/skip_R1regnum', methods=['POST'])
def skip_R1regnum():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R1 Registered Number'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End of R1 Registered Number section ------------------------------------------------------------------#



# ---------------------------------------------------------- R1 Compony Name section -----------------------------------------------------------------------------#

@app.route('/R1_company_name', methods=['GET'])
def R1_company_name():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (R1_company_name IS NOT NULL AND R1_company_name <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True


                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'R1 Company Name'
                """, (image_name,))
                skipped_section_result = cur.fetchone()

               
                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True

                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R1_company_name IS NOT NULL AND R1_company_name <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()


                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R1_company_name']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-18, left_offset=-350, right_offset=540, bottom_offset=130)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R1_company_name.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R1_company_name.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r1compnamenext_image2')
def r1compnamenext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R1_company_name'))

@app.route('/r1compnameprevious_image2')
def r1compnameprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R1_company_name'))




@app.route('/save_R1compname', methods=['POST'])
def save_R1compname():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    R1companyname = request.form.get('address')

    # Validate form data
    if not username or not image_name or not R1companyname:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R1_company_name IS NULL OR R1_company_name = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R1_company_name = %s
                WHERE id = %s
                """, (R1companyname, existing_record[0]))
            message = 'Company name updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R1_company_name) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, R1companyname))
            message = 'Company name saved successfully.'

        connection.commit()

        # Check consistency and save to final_data
        cur.execute("""
            SELECT R1_company_name FROM user_images 
            WHERE image_name = %s AND (R1_company_name IS NOT NULL AND R1_company_name <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            company_list = [record[0] for record in existing_records]
            if len(set(company_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R1_company_name = %s
                        WHERE id = %s
                        """, (company_list[0], final_data_record[0]))
                    message += ' Company name updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R1_company_name)
                        VALUES (%s, %s)
                        """, (image_name, company_list[0]))
                    message += ' Company name saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Company names do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save company name'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R1compname', methods=['POST'])
def skip_R1compname():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R1 Company Name'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200



# ----------------------------------------------------------End of R1 Compony Name section -----------------------------------------------------------------------#



# ---------------------------------------------------------- R1 Compony Address section --------------------------------------------------------------------------#

@app.route('/R1_company_address', methods=['GET'])
def R1_company_address():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (R1_company_address IS NOT NULL AND R1_company_address <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True


                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'R1 Company Address'
                """, (image_name,))
                skipped_section_result = cur.fetchone()

               
                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True

                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R1_company_address IS NOT NULL AND R1_company_address <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()


                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R1_company_address']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-18, left_offset=-500, right_offset=720, bottom_offset=80)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R1_company_address.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R1_company_address.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r1compaddnext_image2')
def r1compaddnext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R1_company_address'))

@app.route('/r1compaddprevious_image2')
def r1compaddprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R1_company_address'))




@app.route('/save_R1compadd', methods=['POST'])
def save_R1compadd():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    R1companyaddress = request.form.get('address')

    # Validate form data
    if not username or not image_name or not R1companyaddress:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R1_company_address IS NULL OR R1_company_address = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R1_company_address = %s
                WHERE id = %s
                """, (R1companyaddress, existing_record[0]))
            message = 'Company address updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R1_company_address) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, R1companyaddress))
            message = 'Company address saved successfully.'

        connection.commit()

        # Check consistency and save to final_data
        cur.execute("""
            SELECT R1_company_address FROM user_images 
            WHERE image_name = %s AND (R1_company_address IS NOT NULL AND R1_company_address <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            address_list = [record[0] for record in existing_records]
            if len(set(address_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R1_company_address = %s
                        WHERE id = %s
                        """, (address_list[0], final_data_record[0]))
                    message += ' Company address updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R1_company_address)
                        VALUES (%s, %s)
                        """, (image_name, address_list[0]))
                    message += ' Company address saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Company addresses do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save company address'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R1compadd', methods=['POST'])
def skip_R1compadd():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R1 Company Address'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End of R1 Compony Address section --------------------------------------------------------------------#


# ---------------------------------------------------------- R1 Address Code section -----------------------------------------------------------------------------#

@app.route('/R1_address_code', methods=['GET'])
def R1_address_code():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image

                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (R1_address_code IS NOT NULL AND R1_address_code <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True


                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'R1 Address Code'
                """, (image_name,))
                skipped_section_result = cur.fetchone()

               
                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True

                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R1_address_code IS NOT NULL AND R1_address_code <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()


                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R1_address_code']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-85, left_offset=-500, right_offset=720, bottom_offset=120)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R1_address_code.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R1_address_code.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r1compaddcodenext_image2')
def r1compaddcodenext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R1_address_code'))

@app.route('/r1compaddcodeprevious_image2')
def r1compaddcodeprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R1_address_code'))




@app.route('/save_R1compaddcode', methods=['POST'])
def save_R1compaddcode():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    R1addresscode = request.form.get('address')

    # Validate form data
    if not username or not image_name or not R1addresscode:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R1_address_code IS NULL OR R1_address_code = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R1_address_code = %s
                WHERE id = %s
                """, (R1addresscode, existing_record[0]))
            message = 'Address code updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R1_address_code) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, R1addresscode))
            message = 'Address code saved successfully.'

        connection.commit()

        # Check consistency and save to final_data
        cur.execute("""
            SELECT R1_address_code FROM user_images 
            WHERE image_name = %s AND (R1_address_code IS NOT NULL AND R1_address_code <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            address_code_list = [record[0] for record in existing_records]
            if len(set(address_code_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R1_address_code = %s
                        WHERE id = %s
                        """, (address_code_list[0], final_data_record[0]))
                    message += ' Address code updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R1_address_code)
                        VALUES (%s, %s)
                        """, (image_name, address_code_list[0]))
                    message += ' Address code saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Address codes do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save address code'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R1compaddcode', methods=['POST'])
def skip_R1compaddcode():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R1 Address Code'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End of R1 Address Code section ------------------------------------------------------------------------#


# ---------------------------------------------------------- R1 Number Of Items Of The Compony section ------------------------------------------------------------#

@app.route('/R1_number_of_company_items', methods=['GET'])
def R1_number_of_company_items():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (R1_number_of_company_items IS NOT NULL AND R1_number_of_company_items <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True


                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'R1 Number Of Company Items'
                """, (image_name,))
                skipped_section_result = cur.fetchone()

               
                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True

                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R1_number_of_company_items IS NOT NULL AND R1_number_of_company_items <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R1_number_of_company_items']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-25, left_offset=-680, right_offset=900, bottom_offset=80)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R1_number_of_company_items.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R1_number_of_company_items.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r1cmpitmnext_image2')
def r1cmpitmnext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R1_number_of_company_items'))

@app.route('/r1cmpitmprevious_image2')
def r1cmpitmprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R1_number_of_company_items'))




@app.route('/save_R1cmpitm', methods=['POST'])
def save_R1cmpitm():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    R1typecode = request.form.get('address')

    # Validate form data
    if not username or not image_name or not R1typecode:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R1_number_of_company_items IS NULL OR R1_number_of_company_items = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R1_number_of_company_items = %s
                WHERE id = %s
                """, (R1typecode, existing_record[0]))
            message = 'Number of company items updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R1_number_of_company_items) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, R1typecode))
            message = 'Number of company items saved successfully.'

        connection.commit()

        # Check consistency and save to final_data
        cur.execute("""
            SELECT R1_number_of_company_items FROM user_images 
            WHERE image_name = %s AND (R1_number_of_company_items IS NOT NULL AND R1_number_of_company_items <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            items_list = [record[0] for record in existing_records]
            if len(set(items_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R1_number_of_company_items = %s
                        WHERE id = %s
                        """, (items_list[0], final_data_record[0]))
                    message += ' Number of company items updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R1_number_of_company_items)
                        VALUES (%s, %s)
                        """, (image_name, items_list[0]))
                    message += ' Number of company items saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Company item numbers do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save number of company items'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R1cmpitm', methods=['POST'])
def skip_R1cmpitm():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R1 Number Of Company Items'
    reason = data['reason']

    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200

# ----------------------------------------------------------End of R1 Number Of Items Of The Compony section -------------------------------------------------------#



# ---------------------------------------------------------- R1 Code Of Items Of The Compony section ----------------------------------------------------------------#

@app.route('/R1_company_item_code', methods=['GET'])
def R1_company_item_code():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (R1_company_item_code IS NOT NULL AND R1_company_item_code <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True


                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'R1 Company Item Code'
                """, (image_name,))
                skipped_section_result = cur.fetchone()

               
                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True

                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R1_company_item_code IS NOT NULL AND R1_company_item_code <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R1_company_item_code']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-85, left_offset=-700, right_offset=900, bottom_offset=130)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R1_company_item_code.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R1_company_item_code.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r1copmitmcodenext_image2')
def r1copmitmcodenext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R1_company_item_code'))

@app.route('/r1copmitmcodeprevious_image2')
def r1copmitmcodeprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R1_company_item_code'))




@app.route('/save_R1copmitmcode', methods=['POST'])
def save_R1copmitmcode():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    R1typecode = request.form.get('address')

    # Validate form data
    if not username or not image_name or not R1typecode:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R1_company_item_code IS NULL OR R1_company_item_code = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R1_company_item_code = %s
                WHERE id = %s
                """, (R1typecode, existing_record[0]))
            message = 'Company item code updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R1_company_item_code) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, R1typecode))
            message = 'Company item code saved successfully.'

        connection.commit()

        # Check consistency and save to final_data
        cur.execute("""
            SELECT R1_company_item_code FROM user_images 
            WHERE image_name = %s AND (R1_company_item_code IS NOT NULL AND R1_company_item_code <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            codes_list = [record[0] for record in existing_records]
            if len(set(codes_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R1_company_item_code = %s
                        WHERE id = %s
                        """, (codes_list[0], final_data_record[0]))
                    message += ' Company item code updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R1_company_item_code)
                        VALUES (%s, %s)
                        """, (image_name, codes_list[0]))
                    message += ' Company item code saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Company item codes do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save company item code'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R1copmitmcode', methods=['POST'])
def skip_R1copmitmcode():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R1 Company Item Code'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200

# ----------------------------------------------------------End of R1 Code Of Items Of The Compony section -----------------------------------------------------------#


# ---------------------------------------------------------- R1 Compony Name 2 section -------------------------------------------------------------------------------#

@app.route('/R1_company_name_2', methods=['GET'])
def R1_company_name_2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (R1_company_name_2 IS NOT NULL AND R1_company_name_2 <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True


                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'R1 Company Name 2'
                """, (image_name,))
                skipped_section_result = cur.fetchone()

               
                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True


                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R1_company_name_2 IS NOT NULL AND R1_company_name_2 <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

               
                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R1_company_name_2']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-35, left_offset=-750, right_offset=1080, bottom_offset=130)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R1_company_name_2.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R1_company_name_2.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r1cmpname2next_image2')
def r1cmpname2next_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R1_company_name_2'))

@app.route('/r1cmpname2previous_image2')
def r1cmpname2previous_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R1_company_name_2'))




@app.route('/save_R1cmpname2', methods=['POST'])
def save_R1cmpname2():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    R1typecode = request.form.get('address')

    # Validate form data
    if not username or not image_name or not R1typecode:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R1_company_name_2 IS NULL OR R1_company_name_2 = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R1_company_name_2 = %s
                WHERE id = %s
                """, (R1typecode, existing_record[0]))
            message = 'Company name updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R1_company_name_2) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, R1typecode))
            message = 'Company name saved successfully.'

        connection.commit()

        # Check consistency and save to final_data
        cur.execute("""
            SELECT R1_company_name_2 FROM user_images 
            WHERE image_name = %s AND (R1_company_name_2 IS NOT NULL AND R1_company_name_2 <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            names_list = [record[0] for record in existing_records]
            if len(set(names_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R1_company_name_2 = %s
                        WHERE id = %s
                        """, (names_list[0], final_data_record[0]))
                    message += ' Company name updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R1_company_name_2)
                        VALUES (%s, %s)
                        """, (image_name, names_list[0]))
                    message += ' Company name saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Company names do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save company name'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200





@app.route('/skip_R1cmpname2', methods=['POST'])
def skip_R1cmpname2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R1 Company Name 2'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End of R1 Compony Name 2 section -------------------------------------------------------------------------#


# ----------------------------------------------------------R1 Compony address 2 section -------------------------------------------------------------------------#

@app.route('/R1_company_address2', methods=['GET'])
def R1_company_address2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (R1_company_address2 IS NOT NULL AND R1_company_address2 <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True


                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'R1 Company Address 2'
                """, (image_name,))
                skipped_section_result = cur.fetchone()

               
                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True

                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R1_company_address2 IS NOT NULL AND R1_company_address2 <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R1_company_address2']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-35, left_offset=-1020, right_offset=1300, bottom_offset=85)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R1_company_address2.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R1_company_address2.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r1cmpadd2next_image2')
def r1cmpadd2next_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R1_company_address2'))

@app.route('/r1cmpadd2previous_image2')
def r1cmpadd2previous_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R1_company_address2'))




@app.route('/save_R1cmpadd2', methods=['POST'])
def save_R1cmpadd2():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    R1typecode = request.form.get('address')

    # Validate form data
    if not username or not image_name or not R1typecode:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R1_company_address2 IS NULL OR R1_company_address2 = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R1_company_address2 = %s
                WHERE id = %s
                """, (R1typecode, existing_record[0]))
            message = 'Company address updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R1_company_address2) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, R1typecode))
            message = 'Company address saved successfully.'

        connection.commit()

        # Check consistency and save to final_data
        cur.execute("""
            SELECT R1_company_address2 FROM user_images 
            WHERE image_name = %s AND (R1_company_address2 IS NOT NULL AND R1_company_address2 <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            addresses_list = [record[0] for record in existing_records]
            if len(set(addresses_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R1_company_address2 = %s
                        WHERE id = %s
                        """, (addresses_list[0], final_data_record[0]))
                    message += ' Company address updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R1_company_address2)
                        VALUES (%s, %s)
                        """, (image_name, addresses_list[0]))
                    message += ' Company address saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Company addresses do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save company address'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200





@app.route('/skip_R1cmpadd2', methods=['POST'])
def skip_R1cmpadd2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R1 Company Address 2'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End Of R1 Compony address 2 section -------------------------------------------------------------------------#



# ----------------------------------------------------------R1  Address Code 2 section -------------------------------------------------------------------------#


@app.route('/R1_address_code2', methods=['GET'])
def R1_address_code2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (R1_address_code2 IS NOT NULL AND R1_address_code2 <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True


                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'R1 Address Code 2'
                """, (image_name,))
                skipped_section_result = cur.fetchone()

               
                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True

                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R1_address_code2 IS NOT NULL AND R1_address_code2 <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R1_address_code2']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-98, left_offset=-1020, right_offset=1300, bottom_offset=120)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R1_address_code2.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R1_address_code2.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r1addcode2next_image2')
def r1addcode2next_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R1_address_code2'))

@app.route('/r1addcode2previous_image2')
def r1addcode2previous_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R1_address_code2'))




@app.route('/save_R1addcode2', methods=['POST'])
def save_R1addcode2():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    R1typecode = request.form.get('address')

    # Validate form data
    if not username or not image_name or not R1typecode:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R1_address_code2 IS NULL OR R1_address_code2 = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R1_address_code2 = %s
                WHERE id = %s
                """, (R1typecode, existing_record[0]))
            message = 'Address code updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R1_address_code2) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, R1typecode))
            message = 'Address code saved successfully.'

        connection.commit()

        # Check consistency and save to final_data
        cur.execute("""
            SELECT R1_address_code2 FROM user_images 
            WHERE image_name = %s AND (R1_address_code2 IS NOT NULL AND R1_address_code2 <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            codes_list = [record[0] for record in existing_records]
            if len(set(codes_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R1_address_code2 = %s
                        WHERE id = %s
                        """, (codes_list[0], final_data_record[0]))
                    message += ' Address code updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R1_address_code2)
                        VALUES (%s, %s)
                        """, (image_name, codes_list[0]))
                    message += ' Address code saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Address codes do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save address code'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R1addcode2', methods=['POST'])
def skip_R1addcode2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R1 Address Code 2'
    reason = data['reason']

    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End Of R1 Address Code 2 section -------------------------------------------------------------------------#



# ------------------------------------------------------ R2 Record  number  section ------------------------------------------------------------------#

@app.route('/R2_record_number', methods=['GET'])
def R2_record_number():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (R2_record_number IS NOT NULL AND R2_record_number <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True


                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'R2 Record Number'
                """, (image_name,))
                skipped_section_result = cur.fetchone()

               
                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True

                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R2_record_number IS NOT NULL AND R2_record_number <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R2_record_number']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-120, left_offset=1250, right_offset=-230, bottom_offset=207)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R2_record_number.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R2_record_number.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/rec2next_image2')
def rec2next_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R2_record_number'))

@app.route('/rec2previous_image2')
def rec2previous_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R2_record_number'))



@app.route('/save_record2', methods=['POST'])
def save_record2():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    record_number = request.form.get('address')

    # Validate form data
    if not username or not image_name or not record_number:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R2_record_number IS NULL OR R2_record_number = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R2_record_number = %s
                WHERE id = %s
                """, (record_number, existing_record[0]))
            message = 'Record number updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R2_record_number) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, record_number))
            message = 'Record number saved successfully.'

        connection.commit()

        # Check consistency and save to final_data
        cur.execute("""
            SELECT R2_record_number FROM user_images 
            WHERE image_name = %s AND (R2_record_number IS NOT NULL AND R2_record_number <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            records_list = [record[0] for record in existing_records]
            if len(set(records_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R2_record_number = %s
                        WHERE id = %s
                        """, (records_list[0], final_data_record[0]))
                    message += ' Record number updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R2_record_number)
                        VALUES (%s, %s)
                        """, (image_name, records_list[0]))
                    message += ' Record number saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Record numbers do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save record number'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_record2', methods=['POST'])
def skip_record2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R2 Record Number'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200



# ------------------------------------------------------End of R2 Record  number  section -----------------------------------------------------------------------#



# ---------------------------------------------------------- R2 Type code section -------------------------------------------------------------------------------#

@app.route('/R2_type_code', methods=['GET'])
def R2_type_code():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (R2_type_code IS NOT NULL AND R2_type_code <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True


                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'R2 Type Code'
                """, (image_name,))
                skipped_section_result = cur.fetchone()

               
                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True


                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R2_type_code IS NOT NULL AND R2_type_code <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R2_type_code']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-178, left_offset=270, right_offset=-80, bottom_offset=208)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R2_type_code.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R2_type_code.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r2tcnext_image2')
def r2tcnext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R2_type_code'))

@app.route('/r2tcprevious_image2')
def r2tcprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R2_type_code'))



@app.route('/save_r2typecode', methods=['POST'])
def save_r2typecode():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    R2typecode = request.form.get('address')

    # Validate form data
    if not username or not image_name or not R2typecode:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R2_type_code IS NULL OR R2_type_code = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R2_type_code = %s
                WHERE id = %s
                """, (R2typecode, existing_record[0]))
            message = 'Record type code updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R2_type_code) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, R2typecode))
            message = 'Record type code saved successfully.'

        connection.commit()

        # Check consistency and save to final_data
        cur.execute("""
            SELECT R2_type_code FROM user_images 
            WHERE image_name = %s AND (R2_type_code IS NOT NULL AND R2_type_code <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            type_codes_list = [record[0] for record in existing_records]
            if len(set(type_codes_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R2_type_code = %s
                        WHERE id = %s
                        """, (type_codes_list[0], final_data_record[0]))
                    message += ' Record type code updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R2_type_code)
                        VALUES (%s, %s)
                        """, (image_name, type_codes_list[0]))
                    message += ' Record type code saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Record type codes do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save record type code'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R2typecode', methods=['POST'])
def skip_R2typecode():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R2 Type Code'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200

# ----------------------------------------------------------End of R2 Type code section -------------------------------------------------------------------------#



# ---------------------------------------------------------- R2 Weight Of The Garbage section -------------------------------------------------------------------#

@app.route('/R2_garbage_weight', methods=['GET'])
def R2_garbage_weight():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image

                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (R2_garbage_weight IS NOT NULL AND R2_garbage_weight <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True


                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'R2 garbage weight'
                """, (image_name,))
                skipped_section_result = cur.fetchone()

               
                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True

                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R2_garbage_weight IS NOT NULL AND R2_garbage_weight <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()


                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R2_garbage_weight']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-120, left_offset=100, right_offset=40, bottom_offset=205)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R2_garbage_weight.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R2_garbage_weight.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r2gbwtnext_image2')
def r2gbwtnext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R2_garbage_weight'))

@app.route('/r2gbwtprevious_image2')
def r2gbwtprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R2_garbage_weight'))




@app.route('/save_R2grbwet', methods=['POST'])
def save_R2grbwet():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    garbage_weight = request.form.get('address')

    # Validate form data
    if not username or not image_name or not garbage_weight:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R2_garbage_weight IS NULL OR R2_garbage_weight = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R2_garbage_weight = %s
                WHERE id = %s
                """, (garbage_weight, existing_record[0]))
            message = 'Garbage weight updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R2_garbage_weight) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, garbage_weight))
            message = 'Garbage weight saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R2_garbage_weight FROM user_images 
            WHERE image_name = %s AND (R2_garbage_weight IS NOT NULL AND R2_garbage_weight <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            weights_list = [record[0] for record in existing_records]
            if len(set(weights_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R2_garbage_weight = %s
                        WHERE id = %s
                        """, (weights_list[0], final_data_record[0]))
                    message += ' Garbage weight updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R2_garbage_weight)
                        VALUES (%s, %s)
                        """, (image_name, weights_list[0]))
                    message += ' Garbage weight saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Garbage weights do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save garbage weight'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R2grbwet', methods=['POST'])
def skip_R2grbwet():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R2 garbage weight'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End of R2 Weight Of The Garbage section --------------------------------------------------------------#



# ---------------------------------------------------------- R2 Number Of Items section --------------------------------------------------------------------------#

@app.route('/R2_number_of_items', methods=['GET'])
def R2_number_of_items():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image

                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (R2_number_of_items IS NOT NULL AND R2_number_of_items <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True


                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'R2 Number Of Items'
                """, (image_name,))
                skipped_section_result = cur.fetchone()

               
                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True


                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R2_number_of_items IS NOT NULL AND R2_number_of_items <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R2_number_of_items']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-120, left_offset=-18, right_offset=210, bottom_offset=218)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R2_number_of_items.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R2_number_of_items.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r2nuitmsnext_image2')
def r2nuitmsnext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R2_number_of_items'))

@app.route('/r2nuitmsprevious_image2')
def r2nuitmsprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R2_number_of_items'))



@app.route('/save_R2nmitms', methods=['POST'])
def save_R2nmitms():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    number_of_items = request.form.get('address')

    # Validate form data
    if not username or not image_name or not number_of_items:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R2_number_of_items IS NULL OR R2_number_of_items = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R2_number_of_items = %s
                WHERE id = %s
                """, (number_of_items, existing_record[0]))
            message = 'Number of items updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R2_number_of_items) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, number_of_items))
            message = 'Number of items saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R2_number_of_items FROM user_images 
            WHERE image_name = %s AND (R2_number_of_items IS NOT NULL AND R2_number_of_items <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            items_list = [record[0] for record in existing_records]
            if len(set(items_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R2_number_of_items = %s
                        WHERE id = %s
                        """, (items_list[0], final_data_record[0]))
                    message += ' Number of items updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R2_number_of_items)
                        VALUES (%s, %s)
                        """, (image_name, items_list[0]))
                    message += ' Number of items saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Number of items do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save number of items'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R2nmitms', methods=['POST'])
def skip_R2nmitms():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R2 Number Of Items'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End of R2 Number Of Items section --------------------------------------------------------------------#




# ---------------------------------------------------------- R2 Registered Number section ------------------------------------------------------------------------#

@app.route('/R2_registered_number', methods=['GET'])
def R2_registered_number():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                   SELECT * FROM final_data WHERE image_name = %s AND (R2_number_of_items IS NOT NULL AND R2_number_of_items <> '')
                """, (image_name,))
                skipped_section = cur.fetchone()

                already_processed = False
                flash_message = ""

                if skipped_section:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True


                cur.execute("""
                    SELECT * FROM skipped_sections
                    WHERE image_name = %s 
                    AND skipped_section = 'R2 Number Of Items'
                """, (image_name,))
                skipped_section_result = cur.fetchone()

               
                if skipped_section_result:
                    # Show a message indicating the image is not proper
                    flash_message = 'この画像は適切ではありません。'
                    already_processed = True

                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R2_registered_number IS NOT NULL AND R2_registered_number <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R2_registered_number']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-120, left_offset=-188, right_offset=370, bottom_offset=218)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R2_registered_number.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R2_registered_number.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r2regnumnext_image2')
def r2regnumnext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R2_registered_number'))

@app.route('/r2regnumprevious_image2')
def r2regnumprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R2_registered_number'))




@app.route('/save_R2regnum', methods=['POST'])
def save_R2regnum():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    registered_number = request.form.get('address')

    # Validate form data
    if not username or not image_name or not registered_number:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R2_registered_number IS NULL OR R2_registered_number = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R2_registered_number = %s
                WHERE id = %s
                """, (registered_number, existing_record[0]))
            message = 'Registered number updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R2_registered_number) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, registered_number))
            message = 'Registered number saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R2_registered_number FROM user_images 
            WHERE image_name = %s AND (R2_registered_number IS NOT NULL AND R2_registered_number <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            numbers_list = [record[0] for record in existing_records]
            if len(set(numbers_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R2_registered_number = %s
                        WHERE id = %s
                        """, (numbers_list[0], final_data_record[0]))
                    message += ' Registered number updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R2_registered_number)
                        VALUES (%s, %s)
                        """, (image_name, numbers_list[0]))
                    message += ' Registered number saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Registered number does not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save registered number'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R2regnum', methods=['POST'])
def skip_R2regnum():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R2 Registered Number'
    reason = data['reason']
    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    sql_query = """INSERT INTO skipped_sections (image_name, skipped_section, Reasons) VALUES (%s, %s, %s)"""
    values = (image_name, skipped_section, reason)
    cur.execute(sql_query, values)
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End of R2 Registered Number section ------------------------------------------------------------------#




# ---------------------------------------------------------- R2 Compony Name section -----------------------------------------------------------------------------#

@app.route('/R2_company_name', methods=['GET'])
def R2_company_name():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R2_company_name IS NOT NULL AND R2_company_name <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                already_processed = False
                flash_message = ""

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R2_company_name']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-120, left_offset=-350, right_offset=540, bottom_offset=220)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R2_company_name.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R2_company_name.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r2compnamenext_image2')
def r2compnamenext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R2_company_name'))

@app.route('/r2compnameprevious_image2')
def r2compnameprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R2_company_name'))




@app.route('/save_R2compname', methods=['POST'])
def save_R2compname():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    company_name = request.form.get('address')

    # Validate form data
    if not username or not image_name or not company_name:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R2_company_name IS NULL OR R2_company_name = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R2_company_name = %s
                WHERE id = %s
                """, (company_name, existing_record[0]))
            message = 'Company name updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R2_company_name) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, company_name))
            message = 'Company name saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R2_company_name FROM user_images 
            WHERE image_name = %s AND (R2_company_name IS NOT NULL AND R2_company_name <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            names_list = [record[0] for record in existing_records]
            if len(set(names_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R2_company_name = %s
                        WHERE id = %s
                        """, (names_list[0], final_data_record[0]))
                    message += ' Company name updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R2_company_name)
                        VALUES (%s, %s)
                        """, (image_name, names_list[0]))
                    message += ' Company name saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Company name does not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save company name'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R2compname', methods=['POST'])
def skip_R2compname():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R2 Company Name'

    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("""INSERT INTO skipped_sections (image_name, skipped_section) VALUES (%s, %s)""", (image_name, skipped_section))
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200



# ----------------------------------------------------------End of R2 Compony Name section -----------------------------------------------------------------------#



# ---------------------------------------------------------- R2 Compony Address section --------------------------------------------------------------------------#

@app.route('/R2_company_address', methods=['GET'])
def R2_company_address():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R2_company_address IS NOT NULL AND R2_company_address <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                already_processed = False
                flash_message = ""

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R2_company_address']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-125, left_offset=-500, right_offset=720, bottom_offset=175)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R2_company_address.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R2_company_address.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r2compaddnext_image2')
def r2compaddnext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R2_company_address'))

@app.route('/r2compaddprevious_image2')
def r2compaddprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R2_company_address'))




@app.route('/save_R2compadd', methods=['POST'])
def save_R2compadd():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    company_address = request.form.get('address')

    # Validate form data
    if not username or not image_name or not company_address:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R2_company_address IS NULL OR R2_company_address = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R2_company_address = %s
                WHERE id = %s
                """, (company_address, existing_record[0]))
            message = 'Company address updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R2_company_address) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, company_address))
            message = 'Company address saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R2_company_address FROM user_images 
            WHERE image_name = %s AND (R2_company_address IS NOT NULL AND R2_company_address <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            addresses_list = [record[0] for record in existing_records]
            if len(set(addresses_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R2_company_address = %s
                        WHERE id = %s
                        """, (addresses_list[0], final_data_record[0]))
                    message += ' Company address updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R2_company_address)
                        VALUES (%s, %s)
                        """, (image_name, addresses_list[0]))
                    message += ' Company address saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Company address does not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save company address'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R2compadd', methods=['POST'])
def skip_R2compadd():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R2 Company Address'

    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("""INSERT INTO skipped_sections (image_name, skipped_section) VALUES (%s, %s)""", (image_name, skipped_section))
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End of R2 Compony Address section --------------------------------------------------------------------#




# ---------------------------------------------------------- R2 Address Code section -----------------------------------------------------------------------------#

@app.route('/R2_address_code', methods=['GET'])
def R2_address_code():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R2_address_code IS NOT NULL AND R2_address_code <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                already_processed = False
                flash_message = ""

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R2_address_code']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-178, left_offset=-500, right_offset=720, bottom_offset=210)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R2_address_code.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R2_address_code.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r2compaddcodenext_image2')
def r2compaddcodenext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R2_address_code'))

@app.route('/r2compaddcodeprevious_image2')
def r2compaddcodeprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R2_address_code'))




@app.route('/save_R2compaddcode', methods=['POST'])
def save_R2compaddcode():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    address_code = request.form.get('address')

    # Validate form data
    if not username or not image_name or not address_code:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R2_address_code IS NULL OR R2_address_code = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R2_address_code = %s
                WHERE id = %s
                """, (address_code, existing_record[0]))
            message = 'Address code updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R2_address_code) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, address_code))
            message = 'Address code saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R2_address_code FROM user_images 
            WHERE image_name = %s AND (R2_address_code IS NOT NULL AND R2_address_code <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            address_codes_list = [record[0] for record in existing_records]
            if len(set(address_codes_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R2_address_code = %s
                        WHERE id = %s
                        """, (address_codes_list[0], final_data_record[0]))
                    message += ' Address code updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R2_address_code)
                        VALUES (%s, %s)
                        """, (image_name, address_codes_list[0]))
                    message += ' Address code saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Address code does not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save address code'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200


@app.route('/skip_R2compaddcode', methods=['POST'])
def skip_R2compaddcode():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R2 Address Code'

    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("""INSERT INTO skipped_sections (image_name, skipped_section) VALUES (%s, %s)""", (image_name, skipped_section))
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End of R2 Address Code section ------------------------------------------------------------------------#



# ---------------------------------------------------------- R2 Number Of Items Of The Compony section ------------------------------------------------------------#

@app.route('/R2_number_of_company_items', methods=['GET'])
def R2_number_of_company_items():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R2_number_of_company_items IS NOT NULL AND R2_number_of_company_items <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                already_processed = False
                flash_message = ""

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R2_number_of_company_items']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-125, left_offset=-680, right_offset=900, bottom_offset=180)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R2_number_of_company_items.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R2_number_of_company_items.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r2cmpitmnext_image2')
def r2cmpitmnext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R2_number_of_company_items'))

@app.route('/r2cmpitmprevious_image2')
def r2cmpitmprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R2_number_of_company_items'))




@app.route('/save_R2cmpitm', methods=['POST'])
def save_R2cmpitm():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    number_of_company_items = request.form.get('address')

    # Validate form data
    if not username or not image_name or not number_of_company_items:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R2_number_of_company_items IS NULL OR R2_number_of_company_items = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R2_number_of_company_items = %s
                WHERE id = %s
                """, (number_of_company_items, existing_record[0]))
            message = 'Number of company items updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R2_number_of_company_items) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, number_of_company_items))
            message = 'Number of company items saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R2_number_of_company_items FROM user_images 
            WHERE image_name = %s AND (R2_number_of_company_items IS NOT NULL AND R2_number_of_company_items <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            company_items_list = [record[0] for record in existing_records]
            if len(set(company_items_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R2_number_of_company_items = %s
                        WHERE id = %s
                        """, (company_items_list[0], final_data_record[0]))
                    message += ' Number of company items updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R2_number_of_company_items)
                        VALUES (%s, %s)
                        """, (image_name, company_items_list[0]))
                    message += ' Number of company items saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Number of company items does not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save number of company items'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R2cmpitm', methods=['POST'])
def skip_R2cmpitm():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R2 Number Of Company Items'

    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("""INSERT INTO skipped_sections (image_name, skipped_section) VALUES (%s, %s)""", (image_name, skipped_section))
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200

# ----------------------------------------------------------End of R2 Number Of Items Of The Compony section -------------------------------------------------------#



# ---------------------------------------------------------- R2 Code Of Items Of The Compony section ----------------------------------------------------------------#

@app.route('/R2_company_item_code', methods=['GET'])
def R2_company_item_code():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R2_company_item_code IS NOT NULL AND R2_company_item_code <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                already_processed = False
                flash_message = ""

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R2_company_item_code']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-180, left_offset=-700, right_offset=900, bottom_offset=210)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R2_company_item_code.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)
                return render_template('R2_company_item_code.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r2copmitmcodenext_image2')
def r2copmitmcodenext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R2_company_item_code'))

@app.route('/r2copmitmcodeprevious_image2')
def r2copmitmcodeprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R2_company_item_code'))




@app.route('/save_R2copmitmcode', methods=['POST'])
def save_R2copmitmcode():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    company_item_code = request.form.get('address')

    # Validate form data
    if not username or not image_name or not company_item_code:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R2_company_item_code IS NULL OR R2_company_item_code = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R2_company_item_code = %s
                WHERE id = %s
                """, (company_item_code, existing_record[0]))
            message = 'Company item code updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R2_company_item_code) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, company_item_code))
            message = 'Company item code saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R2_company_item_code FROM user_images 
            WHERE image_name = %s AND (R2_company_item_code IS NOT NULL AND R2_company_item_code <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            company_item_codes_list = [record[0] for record in existing_records]
            if len(set(company_item_codes_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R2_company_item_code = %s
                        WHERE id = %s
                        """, (company_item_codes_list[0], final_data_record[0]))
                    message += ' Company item code updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R2_company_item_code)
                        VALUES (%s, %s)
                        """, (image_name, company_item_codes_list[0]))
                    message += ' Company item code saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Company item codes do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save company item code'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R2copmitmcode', methods=['POST'])
def skip_R2copmitmcode():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R2 Company Item Code'

    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("""INSERT INTO skipped_sections (image_name, skipped_section) VALUES (%s, %s)""", (image_name, skipped_section))
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200

# ----------------------------------------------------------End of R2 Code Of Items Of The Compony section -----------------------------------------------------------#



# ---------------------------------------------------------- R2 Compony Name 2 section -------------------------------------------------------------------------------#

@app.route('/R2_company_name_2', methods=['GET'])
def R2_company_name_2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R2_company_name_2 IS NOT NULL AND R2_company_name_2 <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                already_processed = False
                flash_message = ""

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R2_company_name_2']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-125, left_offset=-750, right_offset=1080, bottom_offset=200)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R2_company_name_2.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R2_company_name_2.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r2cmpname2next_image2')
def r2cmpname2next_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R2_company_name_2'))

@app.route('/r2cmpname2previous_image2')
def r2cmpname2previous_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R2_company_name_2'))




@app.route('/save_R2cmpname2', methods=['POST'])
def save_R2cmpname2():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    company_name_2 = request.form.get('address')

    # Validate form data
    if not username or not image_name or not company_name_2:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R2_company_name_2 IS NULL OR R2_company_name_2 = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R2_company_name_2 = %s
                WHERE id = %s
                """, (company_name_2, existing_record[0]))
            message = 'Company name 2 updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R2_company_name_2) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, company_name_2))
            message = 'Company name 2 saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R2_company_name_2 FROM user_images 
            WHERE image_name = %s AND (R2_company_name_2 IS NOT NULL AND R2_company_name_2 <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            company_names_list = [record[0] for record in existing_records]
            if len(set(company_names_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R2_company_name_2 = %s
                        WHERE id = %s
                        """, (company_names_list[0], final_data_record[0]))
                    message += ' Company name 2 updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R2_company_name_2)
                        VALUES (%s, %s)
                        """, (image_name, company_names_list[0]))
                    message += ' Company name 2 saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Company names do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save company name 2'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R2cmpname2', methods=['POST'])
def skip_R2cmpname2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R2 Company Name 2'

    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("""INSERT INTO skipped_sections (image_name, skipped_section) VALUES (%s, %s)""", (image_name, skipped_section))
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End of R2 Compony Name 2 section -------------------------------------------------------------------------#




# ----------------------------------------------------------R2 Compony address 2 section -------------------------------------------------------------------------#

@app.route('/R2_company_address2', methods=['GET'])
def R2_company_address2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R2_company_address2 IS NOT NULL AND R2_company_address2 <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                already_processed = False
                flash_message = ""

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R2_company_address2']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-135, left_offset=-1020, right_offset=1300, bottom_offset=180)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R2_company_address2.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R2_company_address2.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r2cmpadd2next_image2')
def r2cmpadd2next_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R2_company_address2'))

@app.route('/r2cmpadd2previous_image2')
def r2cmpadd2previous_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R2_company_address2'))




@app.route('/save_R2cmpadd2', methods=['POST'])
def save_R2cmpadd2():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    company_address2 = request.form.get('address')

    # Validate form data
    if not username or not image_name or not company_address2:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R2_company_address2 IS NULL OR R2_company_address2 = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R2_company_address2 = %s
                WHERE id = %s
                """, (company_address2, existing_record[0]))
            message = 'Company address 2 updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R2_company_address2) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, company_address2))
            message = 'Company address 2 saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R2_company_address2 FROM user_images 
            WHERE image_name = %s AND (R2_company_address2 IS NOT NULL AND R2_company_address2 <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            company_addresses_list = [record[0] for record in existing_records]
            if len(set(company_addresses_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R2_company_address2 = %s
                        WHERE id = %s
                        """, (company_addresses_list[0], final_data_record[0]))
                    message += ' Company address 2 updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R2_company_address2)
                        VALUES (%s, %s)
                        """, (image_name, company_addresses_list[0]))
                    message += ' Company address 2 saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Company addresses do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save company address 2'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200




@app.route('/skip_R2cmpadd2', methods=['POST'])
def skip_R2cmpadd2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R2 Company Address 2'

    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("""INSERT INTO skipped_sections (image_name, skipped_section) VALUES (%s, %s)""", (image_name, skipped_section))
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End Of R2 Compony address 2 section -------------------------------------------------------------------------#




# ----------------------------------------------------------R2  Address Code 2 section -------------------------------------------------------------------------#


@app.route('/R2_address_code2', methods=['GET'])
def R2_address_code2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R2_address_code2 IS NOT NULL AND R2_address_code2 <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                already_processed = False
                flash_message = ""

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R2_address_code2']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-180, left_offset=-1020, right_offset=1300, bottom_offset=200)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R2_address_code2.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R2_address_code2.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r2addcode2next_image2')
def r2addcode2next_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R2_address_code2'))

@app.route('/r2addcode2previous_image2')
def r2addcode2previous_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R2_address_code2'))




@app.route('/save_R2addcode2', methods=['POST'])
def save_R2addcode2():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    address_code2 = request.form.get('address')

    # Validate form data
    if not username or not image_name or not address_code2:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R2_address_code2 IS NULL OR R2_address_code2 = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R2_address_code2 = %s
                WHERE id = %s
                """, (address_code2, existing_record[0]))
            message = 'Address code 2 updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R2_address_code2) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, address_code2))
            message = 'Address code 2 saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R2_address_code2 FROM user_images 
            WHERE image_name = %s AND (R2_address_code2 IS NOT NULL AND R2_address_code2 <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            address_codes_list = [record[0] for record in existing_records]
            if len(set(address_codes_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R2_address_code2 = %s
                        WHERE id = %s
                        """, (address_codes_list[0], final_data_record[0]))
                    message += ' Address code 2 updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R2_address_code2)
                        VALUES (%s, %s)
                        """, (image_name, address_codes_list[0]))
                    message += ' Address code 2 saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Address codes do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save address code 2'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200




@app.route('/skip_R2addcode2', methods=['POST'])
def skip_R2addcode2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R2 Address Code 2'

    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("""INSERT INTO skipped_sections (image_name, skipped_section) VALUES (%s, %s)""", (image_name, skipped_section))
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End Of R2 Address Code 2 section -------------------------------------------------------------------------#



# ------------------------------------------------------ R3 Record  number  section ------------------------------------------------------------------#

@app.route('/R3_record_number', methods=['GET'])
def R3_record_number():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R3_record_number IS NOT NULL AND R3_record_number <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                already_processed = False
                flash_message = ""

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R3_record_number']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-210, left_offset=1250, right_offset=-230, bottom_offset=290)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R3_record_number.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R3_record_number.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/rec3next_image2')
def rec3next_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R3_record_number'))

@app.route('/rec3previous_image2')
def rec3previous_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R3_record_number'))



@app.route('/save_record3', methods=['POST'])
def save_record3():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    record_number = request.form.get('address')

    # Validate form data
    if not username or not image_name or not record_number:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R3_record_number IS NULL OR R3_record_number = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R3_record_number = %s
                WHERE id = %s
                """, (record_number, existing_record[0]))
            message = 'Record number updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R3_record_number) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, record_number))
            message = 'Record number saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R3_record_number FROM user_images 
            WHERE image_name = %s AND (R3_record_number IS NOT NULL AND R3_record_number <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            record_numbers_list = [record[0] for record in existing_records]
            if len(set(record_numbers_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R3_record_number = %s
                        WHERE id = %s
                        """, (record_numbers_list[0], final_data_record[0]))
                    message += ' Record number updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R3_record_number)
                        VALUES (%s, %s)
                        """, (image_name, record_numbers_list[0]))
                    message += ' Record number saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Record numbers do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save record number'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_record3', methods=['POST'])
def skip_record3():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R3 Record Number'

    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("""INSERT INTO skipped_sections (image_name, skipped_section) VALUES (%s, %s)""", (image_name, skipped_section))
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200



# ------------------------------------------------------End of R3 Record  number  section -----------------------------------------------------------------------3



# ---------------------------------------------------------- R3 Type code section -------------------------------------------------------------------------------#

@app.route('/R3_type_code', methods=['GET'])
def R3_type_code():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R3_type_code IS NOT NULL AND R3_type_code <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                already_processed = False
                flash_message = ""

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R3_type_code']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-278, left_offset=270, right_offset=-80, bottom_offset=300)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R3_type_code.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R3_type_code.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r3tcnext_image2')
def r3tcnext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R3_type_code'))

@app.route('/r3tcprevious_image2')
def r3tcprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R3_type_code'))



@app.route('/save_r3typecode', methods=['POST'])
def save_r3typecode():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    r3_type_code = request.form.get('address')

    # Validate form data
    if not username or not image_name or not r3_type_code:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R3_type_code IS NULL OR R3_type_code = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R3_type_code = %s
                WHERE id = %s
                """, (r3_type_code, existing_record[0]))
            message = 'R3 type code updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R3_type_code) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, r3_type_code))
            message = 'R3 type code saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R3_type_code FROM user_images 
            WHERE image_name = %s AND (R3_type_code IS NOT NULL AND R3_type_code <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            r3_type_codes_list = [record[0] for record in existing_records]
            if len(set(r3_type_codes_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R3_type_code = %s
                        WHERE id = %s
                        """, (r3_type_codes_list[0], final_data_record[0]))
                    message += ' R3 type code updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R3_type_code)
                        VALUES (%s, %s)
                        """, (image_name, r3_type_codes_list[0]))
                    message += ' R3 type code saved to final_data successfully.'

                connection.commit()
            else:
                message += ' R3 type codes do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save R3 type code'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200


@app.route('/skip_R3typecode', methods=['POST'])
def skip_R3typecode():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R3 Type Code'

    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("""INSERT INTO skipped_sections (image_name, skipped_section) VALUES (%s, %s)""", (image_name, skipped_section))
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200

# ----------------------------------------------------------End of R3 Type code section -------------------------------------------------------------------------3




# ---------------------------------------------------------- R3 Weight Of The Garbage section -------------------------------------------------------------------#

@app.route('/R3_garbage_weight', methods=['GET'])
def R3_garbage_weight():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R3_garbage_weight IS NOT NULL AND R3_garbage_weight <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                already_processed = False
                flash_message = ""

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R3_garbage_weight']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-200, left_offset=100, right_offset=40, bottom_offset=300)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R3_garbage_weight.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R3_garbage_weight.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r3gbwtnext_image2')
def r3gbwtnext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R3_garbage_weight'))

@app.route('/r3gbwtprevious_image2')
def r3gbwtprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R3_garbage_weight'))




@app.route('/save_R3grbwet', methods=['POST'])
def save_R3grbwet():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    r3_garbage_weight = request.form.get('address')

    # Validate form data
    if not username or not image_name or not r3_garbage_weight:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R3_garbage_weight IS NULL OR R3_garbage_weight = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R3_garbage_weight = %s
                WHERE id = %s
                """, (r3_garbage_weight, existing_record[0]))
            message = 'Garbage weight updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R3_garbage_weight) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, r3_garbage_weight))
            message = 'Garbage weight saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R3_garbage_weight FROM user_images 
            WHERE image_name = %s AND (R3_garbage_weight IS NOT NULL AND R3_garbage_weight <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            r3_garbage_weights_list = [record[0] for record in existing_records]
            if len(set(r3_garbage_weights_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R3_garbage_weight = %s
                        WHERE id = %s
                        """, (r3_garbage_weights_list[0], final_data_record[0]))
                    message += ' Garbage weight updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R3_garbage_weight)
                        VALUES (%s, %s)
                        """, (image_name, r3_garbage_weights_list[0]))
                    message += ' Garbage weight saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Garbage weights do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save garbage weight'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R3grbwet', methods=['POST'])
def skip_R3grbwet():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R3 garbage weight'

    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("""INSERT INTO skipped_sections (image_name, skipped_section) VALUES (%s, %s)""", (image_name, skipped_section))
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End of R3 Weight Of The Garbage section --------------------------------------------------------------#3



# ---------------------------------------------------------- R3 Number Of Items section --------------------------------------------------------------------------#

@app.route('/R3_number_of_items', methods=['GET'])
def R3_number_of_items():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R3_number_of_items IS NOT NULL AND R3_number_of_items <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                already_processed = False
                flash_message = ""

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R3_number_of_items']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-220, left_offset=-18, right_offset=210, bottom_offset=300)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R3_number_of_items.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R3_number_of_items.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r3nuitmsnext_image2')
def r3nuitmsnext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R3_number_of_items'))

@app.route('/r3nuitmsprevious_image2')
def r3nuitmsprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R3_number_of_items'))



@app.route('/save_R3nmitms', methods=['POST'])
def save_R3nmitms():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    r3_number_of_items = request.form.get('address')

    # Validate form data
    if not username or not image_name or not r3_number_of_items:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R3_number_of_items IS NULL OR R3_number_of_items = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R3_number_of_items = %s
                WHERE id = %s
                """, (r3_number_of_items, existing_record[0]))
            message = 'Number of items updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R3_number_of_items) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, r3_number_of_items))
            message = 'Number of items saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R3_number_of_items FROM user_images 
            WHERE image_name = %s AND (R3_number_of_items IS NOT NULL AND R3_number_of_items <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            r3_number_of_items_list = [record[0] for record in existing_records]
            if len(set(r3_number_of_items_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R3_number_of_items = %s
                        WHERE id = %s
                        """, (r3_number_of_items_list[0], final_data_record[0]))
                    message += ' Number of items updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R3_number_of_items)
                        VALUES (%s, %s)
                        """, (image_name, r3_number_of_items_list[0]))
                    message += ' Number of items saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Number of items do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save number of items'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R3nmitms', methods=['POST'])
def skip_R3nmitms():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R3 Number Of Items'

    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("""INSERT INTO skipped_sections (image_name, skipped_section) VALUES (%s, %s)""", (image_name, skipped_section))
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End of R3 Number Of Items section --------------------------------------------------------------------#3




# ---------------------------------------------------------- R3 Registered Number section ------------------------------------------------------------------------#

@app.route('/R3_registered_number', methods=['GET'])
def R3_registered_number():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R3_registered_number IS NOT NULL AND R3_registered_number <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                already_processed = False
                flash_message = ""

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R3_registered_number']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-220, left_offset=-188, right_offset=370, bottom_offset=310)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R3_registered_number.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R3_registered_number.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r3regnumnext_image2')
def r3regnumnext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R3_registered_number'))

@app.route('/r3regnumprevious_image2')
def r3regnumprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R3_registered_number'))




@app.route('/save_R3regnum', methods=['POST'])
def save_R3regnum():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    r3_registered_number = request.form.get('address')

    # Validate form data
    if not username or not image_name or not r3_registered_number:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R3_registered_number IS NULL OR R3_registered_number = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R3_registered_number = %s
                WHERE id = %s
                """, (r3_registered_number, existing_record[0]))
            message = 'Registered number updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R3_registered_number) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, r3_registered_number))
            message = 'Registered number saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R3_registered_number FROM user_images 
            WHERE image_name = %s AND (R3_registered_number IS NOT NULL AND R3_registered_number <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            r3_registered_number_list = [record[0] for record in existing_records]
            if len(set(r3_registered_number_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R3_registered_number = %s
                        WHERE id = %s
                        """, (r3_registered_number_list[0], final_data_record[0]))
                    message += ' Registered number updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R3_registered_number)
                        VALUES (%s, %s)
                        """, (image_name, r3_registered_number_list[0]))
                    message += ' Registered number saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Registered numbers do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save registered number'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R3regnum', methods=['POST'])
def skip_R3regnum():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R3 Registered Number'

    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("""INSERT INTO skipped_sections (image_name, skipped_section) VALUES (%s, %s)""", (image_name, skipped_section))
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End of R3 Registered Number section ------------------------------------------------------------------#




# ---------------------------------------------------------- R3 Compony Name section -----------------------------------------------------------------------------#

@app.route('/R3_company_name', methods=['GET'])
def R3_company_name():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R3_company_name IS NOT NULL AND R3_company_name <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                already_processed = False
                flash_message = ""

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R3_company_name']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-220, left_offset=-350, right_offset=540, bottom_offset=300)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R3_company_name.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R3_company_name.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r3compnamenext_image2')
def r3compnamenext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R3_company_name'))

@app.route('/r3compnameprevious_image2')
def r3compnameprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R3_company_name'))




@app.route('/save_R3compname', methods=['POST'])
def save_R3compname():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    r3_company_name = request.form.get('address')

    # Validate form data
    if not username or not image_name or not r3_company_name:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R3_company_name IS NULL OR R3_company_name = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R3_company_name = %s
                WHERE id = %s
                """, (r3_company_name, existing_record[0]))
            message = 'Company name updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R3_company_name) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, r3_company_name))
            message = 'Company name saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R3_company_name FROM user_images 
            WHERE image_name = %s AND (R3_company_name IS NOT NULL AND R3_company_name <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            r3_company_name_list = [record[0] for record in existing_records]
            if len(set(r3_company_name_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R3_company_name = %s
                        WHERE id = %s
                        """, (r3_company_name_list[0], final_data_record[0]))
                    message += ' Company name updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R3_company_name)
                        VALUES (%s, %s)
                        """, (image_name, r3_company_name_list[0]))
                    message += ' Company name saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Company names do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save company name'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200


@app.route('/skip_R3compname', methods=['POST'])
def skip_R3compname():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R3 Company Name'

    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("""INSERT INTO skipped_sections (image_name, skipped_section) VALUES (%s, %s)""", (image_name, skipped_section))
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200



# ----------------------------------------------------------End of R3 Compony Name section -----------------------------------------------------------------------#3



# ---------------------------------------------------------- R3 Compony Address section --------------------------------------------------------------------------#

@app.route('/R3_company_address', methods=['GET'])
def R3_company_address():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R3_company_address IS NOT NULL AND R3_company_address <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                already_processed = False
                flash_message = ""

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R3_company_address']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-218, left_offset=-500, right_offset=720, bottom_offset=260)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R3_company_address.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R3_company_address.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r3compaddnext_image2')
def r3compaddnext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R3_company_address'))

@app.route('/r3compaddprevious_image2')
def r3compaddprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R3_company_address'))




@app.route('/save_R3compadd', methods=['POST'])
def save_R3compadd():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    r3_company_address = request.form.get('address')

    # Validate form data
    if not username or not image_name or not r3_company_address:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R3_company_address IS NULL OR R3_company_address = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R3_company_address = %s
                WHERE id = %s
                """, (r3_company_address, existing_record[0]))
            message = 'Company address updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R3_company_address) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, r3_company_address))
            message = 'Company address saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R3_company_address FROM user_images 
            WHERE image_name = %s AND (R3_company_address IS NOT NULL AND R3_company_address <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            r3_company_address_list = [record[0] for record in existing_records]
            if len(set(r3_company_address_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R3_company_address = %s
                        WHERE id = %s
                        """, (r3_company_address_list[0], final_data_record[0]))
                    message += ' Company address updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R3_company_address)
                        VALUES (%s, %s)
                        """, (image_name, r3_company_address_list[0]))
                    message += ' Company address saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Company addresses do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save company address'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R3compadd', methods=['POST'])
def skip_R3compadd():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R3 Company Address'

    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("""INSERT INTO skipped_sections (image_name, skipped_section) VALUES (%s, %s)""", (image_name, skipped_section))
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End of R3 Compony Address section --------------------------------------------------------------------3



# ---------------------------------------------------------- R3 Address Code section -----------------------------------------------------------------------------#

@app.route('/R3_address_code', methods=['GET'])
def R3_address_code():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R3_address_code IS NOT NULL AND R3_address_code <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                already_processed = False
                flash_message = ""

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R3_address_code']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-270, left_offset=-500, right_offset=720, bottom_offset=300)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R3_address_code.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R3_address_code.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r3compaddcodenext_image2')
def r3compaddcodenext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R3_address_code'))

@app.route('/r3compaddcodeprevious_image2')
def r3compaddcodeprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R3_address_code'))




@app.route('/save_R3compaddcode', methods=['POST'])
def save_R3compaddcode():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    r3_address_code = request.form.get('address')

    # Validate form data
    if not username or not image_name or not r3_address_code:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R3_address_code IS NULL OR R3_address_code = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R3_address_code = %s
                WHERE id = %s
                """, (r3_address_code, existing_record[0]))
            message = 'Address code updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R3_address_code) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, r3_address_code))
            message = 'Address code saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R3_address_code FROM user_images 
            WHERE image_name = %s AND (R3_address_code IS NOT NULL AND R3_address_code <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            r3_address_code_list = [record[0] for record in existing_records]
            if len(set(r3_address_code_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R3_address_code = %s
                        WHERE id = %s
                        """, (r3_address_code_list[0], final_data_record[0]))
                    message += ' Address code updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R3_address_code)
                        VALUES (%s, %s)
                        """, (image_name, r3_address_code_list[0]))
                    message += ' Address code saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Address codes do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save address code'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R3compaddcode', methods=['POST'])
def skip_R3compaddcode():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R3 Address Code'

    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("""INSERT INTO skipped_sections (image_name, skipped_section) VALUES (%s, %s)""", (image_name, skipped_section))
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End of R3 Address Code section ------------------------------------------------------------------------#



# ---------------------------------------------------------- R3 Number Of Items Of The Compony section ------------------------------------------------------------#

@app.route('/R3_number_of_company_items', methods=['GET'])
def R3_number_of_company_items():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R3_number_of_company_items IS NOT NULL AND R3_number_of_company_items <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                already_processed = False
                flash_message = ""

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R3_number_of_company_items']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-225, left_offset=-680, right_offset=900, bottom_offset=265)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R3_number_of_company_items.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R3_number_of_company_items.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r3cmpitmnext_image2')
def r3cmpitmnext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R3_number_of_company_items'))

@app.route('/r3cmpitmprevious_image2')
def r3cmpitmprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R3_number_of_company_items'))




@app.route('/save_R3cmpitm', methods=['POST'])
def save_R3cmpitm():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    r3_number_of_company_items = request.form.get('address')

    # Validate form data
    if not username or not image_name or not r3_number_of_company_items:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R3_number_of_company_items IS NULL OR R3_number_of_company_items = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R3_number_of_company_items = %s
                WHERE id = %s
                """, (r3_number_of_company_items, existing_record[0]))
            message = 'Number of company items updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R3_number_of_company_items) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, r3_number_of_company_items))
            message = 'Number of company items saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R3_number_of_company_items FROM user_images 
            WHERE image_name = %s AND (R3_number_of_company_items IS NOT NULL AND R3_number_of_company_items <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            r3_number_of_company_items_list = [record[0] for record in existing_records]
            if len(set(r3_number_of_company_items_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R3_number_of_company_items = %s
                        WHERE id = %s
                        """, (r3_number_of_company_items_list[0], final_data_record[0]))
                    message += ' Number of company items updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R3_number_of_company_items)
                        VALUES (%s, %s)
                        """, (image_name, r3_number_of_company_items_list[0]))
                    message += ' Number of company items saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Company item counts do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save number of company items'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R3cmpitm', methods=['POST'])
def skip_R3cmpitm():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R3 Number Of Company Items'

    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("""INSERT INTO skipped_sections (image_name, skipped_section) VALUES (%s, %s)""", (image_name, skipped_section))
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200

# ----------------------------------------------------------End of R3 Number Of Items Of The Compony section -------------------------------------------------------#




# ---------------------------------------------------------- R3 Code Of Items Of The Compony section ----------------------------------------------------------------#

@app.route('/R3_company_item_code', methods=['GET'])
def R3_company_item_code():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R3_company_item_code IS NOT NULL AND R3_company_item_code <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                already_processed = False
                flash_message = ""

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R3_company_item_code']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-270, left_offset=-700, right_offset=900, bottom_offset=310)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R3_company_item_code.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)
                return render_template('R3_company_item_code.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r3copmitmcodenext_image2')
def r3copmitmcodenext_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R3_company_item_code'))

@app.route('/r3copmitmcodeprevious_image2')
def r3copmitmcodeprevious_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R3_company_item_code'))




@app.route('/save_R3copmitmcode', methods=['POST'])
def save_R3copmitmcode():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    r3_company_item_code = request.form.get('address')

    # Validate form data
    if not username or not image_name or not r3_company_item_code:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R3_company_item_code IS NULL OR R3_company_item_code = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R3_company_item_code = %s
                WHERE id = %s
                """, (r3_company_item_code, existing_record[0]))
            message = 'Company item code updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R3_company_item_code) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, r3_company_item_code))
            message = 'Company item code saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R3_company_item_code FROM user_images 
            WHERE image_name = %s AND (R3_company_item_code IS NOT NULL AND R3_company_item_code <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            r3_company_item_code_list = [record[0] for record in existing_records]
            if len(set(r3_company_item_code_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R3_company_item_code = %s
                        WHERE id = %s
                        """, (r3_company_item_code_list[0], final_data_record[0]))
                    message += ' Company item code updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R3_company_item_code)
                        VALUES (%s, %s)
                        """, (image_name, r3_company_item_code_list[0]))
                    message += ' Company item code saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Company item codes do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save company item code'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R3copmitmcode', methods=['POST'])
def skip_R3copmitmcode():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R3 Company Item Code'

    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("""INSERT INTO skipped_sections (image_name, skipped_section) VALUES (%s, %s)""", (image_name, skipped_section))
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200

# ----------------------------------------------------------End of R3 Code Of Items Of The Compony section -----------------------------------------------------------#




# ---------------------------------------------------------- R3 Compony Name 2 section -------------------------------------------------------------------------------#

@app.route('/R3_company_name_2', methods=['GET'])
def R3_company_name_2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R3_company_name_2 IS NOT NULL AND R3_company_name_2 <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                already_processed = False
                flash_message = ""

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R3_company_name_2']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-205, left_offset=-750, right_offset=1080, bottom_offset=300)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R3_company_name_2.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R3_company_name_2.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r3cmpname2next_image2')
def r3cmpname2next_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R3_company_name_2'))

@app.route('/r3cmpname2previous_image2')
def r3cmpname2previous_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R3_company_name_2'))




@app.route('/save_R3cmpname2', methods=['POST'])
def save_R3cmpname2():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    r3_company_name_2 = request.form.get('address')

    # Validate form data
    if not username or not image_name or not r3_company_name_2:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R3_company_name_2 IS NULL OR R3_company_name_2 = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R3_company_name_2 = %s
                WHERE id = %s
                """, (r3_company_name_2, existing_record[0]))
            message = 'Company name 2 updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R3_company_name_2) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, r3_company_name_2))
            message = 'Company name 2 saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R3_company_name_2 FROM user_images 
            WHERE image_name = %s AND (R3_company_name_2 IS NOT NULL AND R3_company_name_2 <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            r3_company_name_2_list = [record[0] for record in existing_records]
            if len(set(r3_company_name_2_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R3_company_name_2 = %s
                        WHERE id = %s
                        """, (r3_company_name_2_list[0], final_data_record[0]))
                    message += ' Company name 2 updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R3_company_name_2)
                        VALUES (%s, %s)
                        """, (image_name, r3_company_name_2_list[0]))
                    message += ' Company name 2 saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Company names 2 do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save company name 2'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200




@app.route('/skip_R3cmpname2', methods=['POST'])
def skip_R3cmpname2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R3 Company Name 2'

    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("""INSERT INTO skipped_sections (image_name, skipped_section) VALUES (%s, %s)""", (image_name, skipped_section))
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End of R3 Compony Name 2 section -------------------------------------------------------------------------3



# ----------------------------------------------------------R3 Compony address 2 section -------------------------------------------------------------------------#

@app.route('/R3_company_address2', methods=['GET'])
def R3_company_address2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R3_company_address2 IS NOT NULL AND R3_company_address2 <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                already_processed = False
                flash_message = ""

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R3_company_address2']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-210, left_offset=-1020, right_offset=1300, bottom_offset=260)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R3_company_address2.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R3_company_address2.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r3cmpadd2next_image2')
def r3cmpadd2next_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R3_company_address2'))

@app.route('/r3cmpadd2previous_image2')
def r3cmpadd2previous_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R3_company_address2'))




@app.route('/save_R3cmpadd2', methods=['POST'])
def save_R3cmpadd2():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    r3_company_address2 = request.form.get('address')

    # Validate form data
    if not username or not image_name or not r3_company_address2:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R3_company_address2 IS NULL OR R3_company_address2 = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R3_company_address2 = %s
                WHERE id = %s
                """, (r3_company_address2, existing_record[0]))
            message = 'Company address 2 updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R3_company_address2) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, r3_company_address2))
            message = 'Company address 2 saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R3_company_address2 FROM user_images 
            WHERE image_name = %s AND (R3_company_address2 IS NOT NULL AND R3_company_address2 <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            r3_company_address2_list = [record[0] for record in existing_records]
            if len(set(r3_company_address2_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R3_company_address2 = %s
                        WHERE id = %s
                        """, (r3_company_address2_list[0], final_data_record[0]))
                    message += ' Company address 2 updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R3_company_address2)
                        VALUES (%s, %s)
                        """, (image_name, r3_company_address2_list[0]))
                    message += ' Company address 2 saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Company addresses 2 do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save company address 2'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200




@app.route('/skip_R3cmpadd2', methods=['POST'])
def skip_R3cmpadd2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R3 Company Address 2'

    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("""INSERT INTO skipped_sections (image_name, skipped_section) VALUES (%s, %s)""", (image_name, skipped_section))
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End Of R3 Compony address 2 section -------------------------------------------------------------------------#




# ----------------------------------------------------------R3  Address Code 2 section -------------------------------------------------------------------------#


@app.route('/R3_address_code2', methods=['GET'])
def R3_address_code2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    username = session.get('username', 'Guest')

    # Define the uploads folder path
    uploads_folder = 'uploads'
    static_folder = 'static/images'
    cropped_folder = 'cropped'

    # Ensure directories exist
    os.makedirs(cropped_folder, exist_ok=True)
    os.makedirs(static_folder, exist_ok=True)

    # Get all image paths from the uploads folder
    image_paths = [os.path.join(uploads_folder, f) for f in os.listdir(uploads_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]

    # Initialize session variables if not already set
    if 'image_paths' not in session:
        if not image_paths:
            flash('No images found in the uploads folder.')
            return redirect(url_for('upload_files'))
        session['image_paths'] = image_paths
        session['current_index'] = 0  # Set to the first image by default

    if 'current_index' not in session:
        flash('Current index not set.')
        return redirect(url_for('upload_files'))

    current_index = session.get('current_index')
    image_paths = session.get('image_paths')

    extracted_text = ""  # Initialize variable here
    image_url = None

    while current_index < len(image_paths):
        image_path = image_paths[current_index]
        image_name = os.path.basename(image_path)

        connection = get_db_connection()
        try:
            with connection.cursor(dictionary=True) as cur:
                # Check how many distinct users have filled the section column for the current image
                cur.execute("""
                    SELECT COUNT(DISTINCT user_id) as user_count
                    FROM user_images
                    WHERE image_name = %s AND (R3_address_code2 IS NOT NULL AND R3_address_code2 <> '');
                """, (image_name,))
                user_count_result = cur.fetchone()

                already_processed = False
                flash_message = ""

                if user_count_result and user_count_result['user_count'] >= 2:
                    # If the record_number column is filled by at least two distinct users, set a flash message
                    flash_message = 'This image has been processed by multiple users and will not be shown again.'
                    already_processed = True

                # Check if the image has been processed by the current user
                cur.execute("SELECT * FROM user_images WHERE user_id = %s AND username = %s AND image_name = %s", (user_id, username, image_name))
                result = cur.fetchone()

                if result and result['R3_address_code2']:  # If record_number column is not empty
                    already_processed = True
                    flash('This image has already been processed and its record number has been added.')

                if not already_processed:
                    # Process the image if it has not been processed yet
                    target_text = 't'  # Text pattern you want to detect
                    texts = detect_text(image_path)
                    first_coordinates = find_first_coordinates(texts, target_text)
                    cropped_image_path = crop_and_save(image_path, first_coordinates, top_offset=-260, left_offset=-1020, right_offset=1300, bottom_offset=300)
                    
                    if cropped_image_path:
                        base_name = os.path.basename(cropped_image_path)
                        new_base_name = f"{uuid.uuid4()}_{base_name}"
                        new_cropped_image_path = os.path.join(static_folder, new_base_name)
                        
                        try:
                            if os.path.exists(cropped_image_path):
                                os.rename(cropped_image_path, new_cropped_image_path)
                                extracted_text = detect_text_in_cropped_image(new_cropped_image_path)
                                image_url = url_for('static', filename='images/' + os.path.basename(new_cropped_image_path))
                            else:
                                flash('Cropped image file not found.')
                                extracted_text = "No target text found."
                        except Exception as e:
                            flash(f'Error processing image: {e}')
                            extracted_text = "No target text found."
                    else:
                        extracted_text = "No target text found."

                if flash_message:
                    flash(flash_message)
                    # Increment index to move to the next image
                    return render_template('R3_address_code2.html', 
                                           username=username,
                                           extracted_text=extracted_text,
                                           image_url=None,
                                           image_name=image_name,
                                           current_index=current_index, 
                                           total_images=len(image_paths),
                                           already_processed=True)

                return render_template('R3_address_code2.html', 
                                       username=username,
                                       extracted_text=extracted_text, 
                                       image_url=image_url if not already_processed else None,
                                       image_name=image_name,
                                       current_index=current_index, 
                                       total_images=len(image_paths),
                                       already_processed=already_processed)
        finally:
            connection.close()

    # If no valid image is found, return to upload page
    flash('No valid images found.')
    return redirect(url_for('upload_files'))



@app.route('/r3addcode2next_image2')
def r3addcode2next_image2():
     if 'image_paths' in session:
        session['current_index'] = (session['current_index'] + 1) % len(session['image_paths'])
     return redirect(url_for('R3_address_code2'))

@app.route('/r3addcode2previous_image2')
def r3addcode2previous_image2():
    if 'image_paths' in session:
        session['current_index'] = (session['current_index'] - 1) % len(session['image_paths'])
        return redirect(url_for('R3_address_code2'))



@app.route('/save_R3addcode2', methods=['POST'])
def save_R3addcode2():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user_id = session['user_id']

    # Get form data
    username = request.form.get('username')
    image_name = request.form.get('image_name')
    r3_address_code2 = request.form.get('address')

    # Validate form data
    if not username or not image_name or not r3_address_code2:
        return jsonify({'error': 'Missing required fields'}), 400

    connection = get_db_connection()
    try:
        cur = connection.cursor()

        # Search for existing record
        cur.execute("""
            SELECT id FROM user_images 
            WHERE user_id = %s AND username = %s AND image_name = %s 
            AND (R3_address_code2 IS NULL OR R3_address_code2 = '')
            """, (user_id, username, image_name))
        existing_record = cur.fetchone()

        if existing_record:
            # Update the existing record
            cur.execute("""
                UPDATE user_images
                SET R3_address_code2 = %s
                WHERE id = %s
                """, (r3_address_code2, existing_record[0]))
            message = 'Address code 2 updated successfully.'
        else:
            # Insert a new record
            cur.execute("""
                INSERT INTO user_images (user_id, username, image_name, R3_address_code2) 
                VALUES (%s, %s, %s, %s)
                """, (user_id, username, image_name, r3_address_code2))
            message = 'Address code 2 saved successfully.'

        connection.commit()

        # Check consistency and save to final_data if applicable
        cur.execute("""
            SELECT R3_address_code2 FROM user_images 
            WHERE image_name = %s AND (R3_address_code2 IS NOT NULL AND R3_address_code2 <> '')
            """, (image_name,))
        existing_records = cur.fetchall()

        if len(existing_records) >= 2:
            address_code2_list = [record[0] for record in existing_records]
            if len(set(address_code2_list)) == 1:
                # Check if the image_name already exists in final_data
                cur.execute("""
                    SELECT id FROM final_data WHERE image_name = %s
                    """, (image_name,))
                final_data_record = cur.fetchone()

                if final_data_record:
                    # Update the existing record in final_data
                    cur.execute("""
                        UPDATE final_data
                        SET R3_address_code2 = %s
                        WHERE id = %s
                        """, (address_code2_list[0], final_data_record[0]))
                    message += ' Address code 2 updated in final_data successfully.'
                else:
                    # Insert a new record into final_data
                    cur.execute("""
                        INSERT INTO final_data (image_name, R3_address_code2)
                        VALUES (%s, %s)
                        """, (image_name, address_code2_list[0]))
                    message += ' Address code 2 saved to final_data successfully.'

                connection.commit()
            else:
                message += ' Address codes 2 do not match across records; no data saved to final_data.'

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Failed to save address code 2'}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    finally:
        connection.close()

    return jsonify({'success': True, 'message': message}), 200



@app.route('/skip_R3addcode2', methods=['POST'])
def skip_R3addcode2():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    # Ensure the request is in JSON format
    data = request.get_json()
    
    # Validate that `image_name` is present
    if 'image_name' not in data:
        return jsonify({'error': 'Missing image_name'}), 400

    image_name = data['image_name']
    skipped_section = 'R3 Address Code 2'

    # Database operation
    connection = get_db_connection()
    cur = connection.cursor()
    cur.execute("""INSERT INTO skipped_sections (image_name, skipped_section) VALUES (%s, %s)""", (image_name, skipped_section))
    connection.commit()
    connection.close()

    # Return a success message
    return jsonify({'success': True}), 200


# ----------------------------------------------------------End Of R3 Address Code 2 section -------------------------------------------------------------------------#




# the first page of the program 

@app.route('/')
def index():
    return render_template('user_login.html')


# this the admin main page function

@app.route('/admin')
def admin():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    connection = get_db_connection()
    try:
        cur = connection.cursor()
        query = "SELECT id, username FROM users WHERE DATE(created_at) = CURDATE()"
        cur.execute(query)
        users = cur.fetchall()
        cur.close()
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        users = []
    finally:
        connection.close()
    return render_template('admin.html', users=users)



# this function help the admin to create the accounts of both users and admins 

@app.route('/create_accounts', methods=['GET', 'POST'])
def create_accounts():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        plaintext_password = password
        hashed_password = generate_password_hash(password, method='sha256')
        connection = get_db_connection()
        cur = connection.cursor()
        if role == 'admin':
            cur.execute("INSERT INTO admins (username, password, plaintext_password) VALUES (%s, %s, %s)", (username, hashed_password, plaintext_password))
        elif role == 'user':
            cur.execute("INSERT INTO users (username, password, plaintext_password) VALUES (%s, %s, %s)", (username, hashed_password, plaintext_password))
        connection.commit()
        cur.close()
        connection.close()
        return redirect(url_for('view_accounts'))
    return render_template('create_accounts.html')




# here is the function which helps to show all the users and the admins account details to the admin 

@app.route('/view_accounts')
def view_accounts():
    connection = get_db_connection()
    cur = connection.cursor(dictionary=True)
    cur.execute("SELECT * FROM users")
    users = cur.fetchall()
    cur.execute("SELECT * FROM admins")
    admins = cur.fetchall()
    connection.close()
    return render_template('view_accounts.html', users=users, admins=admins)




# here is where the data will be superated as i wanted and can be able to download it asin teh excel formated 

@app.route('/select_record')
def select_record():
    return render_template('select_record.html')


@app.route('/select_record_data', methods=['POST'])
def select_record_data():
    option = request.form.get('option')
    if not option:
        return jsonify({'success': False, 'error': 'No option provided'}), 400

    # Validate option to be one of the allowed columns
    
    connection = get_db_connection()
    cur = connection.cursor(dictionary=True)
    
    # Adjust the query to fit the selected option
    query = f"""
    SELECT DISTINCT u1.image_name, u1.{option} AS {option}_1, u2.{option} AS {option}_2
    FROM user_images u1
    JOIN user_images u2
    ON u1.image_name = u2.image_name
    AND u1.{option} != u2.{option}
    AND u1.{option} < u2.{option}
    ORDER BY u1.image_name
    """
    
    cur.execute(query)
    data = cur.fetchall()
    connection.close()
    
    return jsonify({'success': True, 'data': data})




@app.route('/store_data', methods=['POST'])
def store_data():
    image_name = request.form['imageName']
    data_input = request.form['dataInput']
    
    connection = get_db_connection()
    cursor = connection.cursor()
    
    # Insert or update data in the final_data table
    query = """
        INSERT INTO final_data (image_name, data)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE data = VALUES(data)
    """
    cursor.execute(query, (image_name, data_input))
    connection.commit()
    
    cursor.close()
    connection.close()
    return jsonify({'message': 'Data stored successfully!'})


# this is where the data will be compared from one file to another file 

@app.route('/compare', methods=['GET', 'POST'])
def compare():
    if request.method == 'POST':
        file1 = request.files['file1']
        file2 = request.files['file2']

        if file1 and file2:
            filepath1 = os.path.join(app.config['UPLOAD_FOLDER'], file1.filename)
            filepath2 = os.path.join(app.config['UPLOAD_FOLDER'], file2.filename)

            file1.save(filepath1)
            file2.save(filepath2)

            print(f"Saved File 1: {filepath1} with size {os.path.getsize(filepath1)}")
            print(f"Saved File 2: {filepath2} with size {os.path.getsize(filepath2)}")

            differences = compare_excel_files(filepath1, filepath2)
            return render_template('compare.html', differences=differences)

    return render_template('compare.html', differences=None)

def compare_excel_files(filepath1, filepath2):
    try:
        df1 = pd.read_excel(filepath1, header=None)
        df2 = pd.read_excel(filepath2, header=None)

        # print("File 1 DataFrame:")
        # print(df1)
        # print("File 2 DataFrame:")
        # print(df2)
    except Exception as e:
        print(f"Error reading files: {e}")
        return []

    differences = []
    max_rows = max(len(df1), len(df2))
    max_cols = max(len(df1.columns), len(df2.columns))

    for row in range(max_rows):
        for col in range(max_cols):
            cell1 = df1.iat[row, col] if row < len(df1) and col < len(df1.columns) else None
            cell2 = df2.iat[row, col] if row < len(df2) and col < len(df2.columns) else None
            if cell1 != cell2:
                cell_ref = f"{chr(65 + col)}{row + 2}"
                differences.append((cell_ref,
                                     cell1.item() if isinstance(cell1, (np.integer, np.floating)) else cell1,
                                     cell2.item() if isinstance(cell2, (np.integer, np.floating)) else cell2))

    return differences



# here is the button which will helps to delete the accounts 

@app.route('/delete_account/<role>/<int:account_id>', methods=['POST'])
def delete_account(role, account_id):
    connection = get_db_connection()
    cur = connection.cursor()
    if role == 'admin':
        cur.execute("DELETE FROM admins WHERE id = %s", (account_id,))
    elif role == 'user':
        cur.execute("DELETE FROM users WHERE id = %s", (account_id,))
    connection.commit()
    cur.close()
    connection.close()
    return redirect(url_for('view_accounts'))



# this is where only todays data of the particular user has processed

@app.route('/user_work/<int:user_id>')
def user_work(user_id):
    connection = get_db_connection()
    cur = connection.cursor()
    query = """  
    SELECT id, user_id, username, image_name, todays_work, address, company_name, company_owner_name, 
           telephone_number, company_name2, company_address2, code_number, telephone_number2, 
           R1_record_number, R1_type_code, R1_garbage_weight, R1_number_of_items, R1_registered_number, 
           R1_company_name, R1_company_address, R1_address_code, R1_number_of_company_items, 
           R1_company_item_code, R1_company_name_2,R1_company_address2, R1_address_code2, R2_record_number, R2_type_code, R2_garbage_weight, 
           R2_number_of_items, R2_registered_number, R2_company_name, R2_company_address, R2_address_code, 
           R2_number_of_company_items, R2_company_item_code, R2_company_name_2,R2_company_address2, R2_address_code2, R3_record_number, 
           R3_type_code, R3_garbage_weight, R3_number_of_items, R3_registered_number, R3_company_name, 
           R3_company_address, R3_address_code, R3_number_of_company_items, R3_company_item_code, 
           R3_company_name_2,R3_company_address2, R3_address_code2, R4_record_number, R4_type_code, R4_garbage_weight, R4_number_of_items, 
           R4_registered_number, R4_company_name, R4_company_address, R4_address_code, 
           R4_number_of_company_items, R4_company_item_code, R4_company_name_2,R4_company_address2, R4_address_code2
    FROM `user_images`
    WHERE DATE(todays_work) = CURDATE() AND user_id = %s
    """
    cur.execute(query, (user_id,))
    work_data = cur.fetchall()
    cur.close()
    connection.close()
    return render_template('user_work.html', work_data=work_data)



# this is where all the data of the particular user has processed

@app.route('/user_work2/<int:user_id>')
def user_work2(user_id):
    connection = get_db_connection()
    cur = connection.cursor()
    query = "SELECT * FROM `user_images` WHERE user_id = %s"
    cur.execute(query, (user_id,))

    work_data = cur.fetchall()
    cur.close()
    connection.close()
    return render_template('user_work2.html', work_data=work_data)



# this is where the files that admin upload will processed 

@app.route('/upload_files', methods=['GET', 'POST'])
def upload_files():
    if request.method == 'POST':
        files = request.files.getlist('images')
        if not files:
            flash('No file selected.')
            return redirect(request.url)

        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)

        # Get all image paths in the UPLOAD_FOLDER
        all_image_paths = [os.path.join(app.config['UPLOAD_FOLDER'], f) for f in os.listdir(app.config['UPLOAD_FOLDER']) if allowed_file(f)]

        if all_image_paths:
            session['image_paths'] = all_image_paths
            session['current_index'] = 0  # Start with the first image
            flash('Files successfully uploaded and session initialized.')
        else:
            flash('No valid images found in the upload folder.')
            return redirect(request.url)

        return redirect(url_for('upload_files'))  # Correct endpoint

    return render_template('upload.html')



# this where the list of the uploaded files will be shown 

@app.route('/list_files')
def list_uploaded_files():
    uploads_folder = app.config['UPLOAD_FOLDER']
    files = [f for f in os.listdir(uploads_folder) if os.path.isfile(os.path.join(uploads_folder, f))]
    return render_template('list_files.html', files=files)



# this is where the file uploads is shown 

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)



# this is the entire record that that is visible in the admin page 

@app.route('/view_all_records')
def view_all_records():
    connection = get_db_connection()
    try:
        with connection.cursor() as cur:
            # Query should match the structure of your user_images table
            query = """
                SELECT 
                        id, user_id, username, image_name, todays_work, address, 
                        company_name, company_owner_name, telephone_number, company_name2, 
                        company_address2, code_number, telephone_number2,
                        R1_record_number, R1_type_code, R1_garbage_weight, R1_number_of_items, R1_registered_number, 
           R1_company_name, R1_company_address, R1_address_code, R1_number_of_company_items, 
           R1_company_item_code, R1_company_name_2,R1_company_address2, R1_address_code2, R2_record_number, R2_type_code, R2_garbage_weight, 
           R2_number_of_items, R2_registered_number, R2_company_name, R2_company_address, R2_address_code, 
           R2_number_of_company_items, R2_company_item_code, R2_company_name_2,R2_company_address2, R2_address_code2, R3_record_number, 
           R3_type_code, R3_garbage_weight, R3_number_of_items, R3_registered_number, R3_company_name, 
           R3_company_address, R3_address_code, R3_number_of_company_items, R3_company_item_code, 
           R3_company_name_2,R3_company_address2, R3_address_code2, R4_record_number, R4_type_code, R4_garbage_weight, R4_number_of_items, 
           R4_registered_number, R4_company_name, R4_company_address, R4_address_code, 
           R4_number_of_company_items, R4_company_item_code, R4_company_name_2,R4_company_address2, R4_address_code2
                    FROM user_images

            """
            cur.execute(query)
            records = cur.fetchall()
            # print(records)
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        records = []
    finally:
        connection.close()
    return render_template('view_all_records.html', records=records)



# here is where all the skipped data will be shown

@app.route('/view_all_skipdata')
def view_all_skipdata():
    connection = get_db_connection()
    try:
        with connection.cursor() as cur:
            # Query should match the structure of your user_images table
            query = """ SELECT * FROM skipped_sections"""
            cur.execute(query)
            records = cur.fetchall()
            # print(records)
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        records = []
    finally:
        connection.close()
    return render_template('view_all_skipdata.html', records=records)



@app.route('/get_image/<filename>')
def get_image(filename):
    # Ensure the upload folder is within your project directory
    upload_folder = os.path.join(current_app.root_path, 'uploads')
    return send_from_directory(upload_folder, filename)



@app.route('/skip_update', methods=['POST'])
def skip_update():
    data = request.get_json()
    image_name = data.get('image_name')
    skipped_section = data.get('skipped_section')
    reason = data.get('reason')

    if not image_name or not skipped_section or not reason:
        return jsonify(success=False, error="Missing data"), 400

    # Mapping of human-readable skipped_section to final_data columns
    section_to_column = {
        'Address': 'address',
        'Company Name': 'company_name',
        'Company Owner Name': 'company_owner_name',
        'Telephone Number': 'telephone_number',
        'Company Name 2': 'company_name2',
        'Company Address 2': 'company_address2',
        'Code Number': 'code_number',
        'Telephone Number 2': 'telephone_number2',
        'R1 Record Number': 'R1_record_number',
        'R1 Type Code': 'R1_type_code',
        'R1 Garbage Weight': 'R1_garbage_weight',
        'R1 Number of Items': 'R1_number_of_items',
        'R1 Registered Number': 'R1_registered_number',
        'R1 Company Name': 'R1_company_name',
        'R1 Company Address': 'R1_company_address',
        'R1 Address Code': 'R1_address_code',
        'R1 Number of Company Items': 'R1_number_of_company_items',
        'R1 Company Item Code': 'R1_company_item_code',
        'R1 Company Name 2': 'R1_company_name_2',
        'R1 Company Address 2': 'R1_company_address2',
        'R1 Address Code 2': 'R1_address_code2',
        'R2 Record Number': 'R2_record_number',
        'R2 Type Code': 'R2_type_code',
        'R2 Garbage Weight': 'R2_garbage_weight',
        'R2 Number of Items': 'R2_number_of_items',
        'R2 Registered Number': 'R2_registered_number',
        'R2 Company Name': 'R2_company_name',
        'R2 Company Address': 'R2_company_address',
        'R2 Address Code': 'R2_address_code',
        'R2 Number of Company Items': 'R2_number_of_company_items',
        'R2 Company Item Code': 'R2_company_item_code',
        'R2 Company Name 2': 'R2_company_name_2',
        'R2 Company Address 2': 'R2_company_address2',
        'R2 Address Code 2': 'R2_address_code2',
        'R3 Record Number': 'R3_record_number',
        'R3 Type Code': 'R3_type_code',
        'R3 Garbage Weight': 'R3_garbage_weight',
        'R3 Number of Items': 'R3_number_of_items',
        'R3 Registered Number': 'R3_registered_number',
        'R3 Company Name': 'R3_company_name',
        'R3 Company Address': 'R3_company_address',
        'R3 Address Code': 'R3_address_code',
        'R3 Number of Company Items': 'R3_number_of_company_items',
        'R3 Company Item Code': 'R3_company_item_code',
        'R3 Company Name 2': 'R3_company_name_2',
        'R3 Company Address 2': 'R3_company_address2',
        'R3 Address Code 2': 'R3_address_code2',
        'R4 Record Number': 'R4_record_number',
        'R4 Type Code': 'R4_type_code',
        'R4 Garbage Weight': 'R4_garbage_weight',
        'R4 Number of Items': 'R4_number_of_items',
        'R4 Registered Number': 'R4_registered_number',
        'R4 Company Name': 'R4_company_name',
        'R4 Company Address': 'R4_company_address',
        'R4 Address Code': 'R4_address_code',
        'R4 Number of Company Items': 'R4_number_of_company_items',
        'R4 Company Item Code': 'R4_company_item_code',
        'R4 Company Name 2': 'R4_company_name_2',
        'R4 Company Address 2': 'R4_company_address2',
        'R4 Address Code 2': 'R4_address_code2'
    }

    # Get the column that corresponds to the skipped section
    column_to_update = section_to_column.get(skipped_section)
    if not column_to_update:
        return jsonify({'success': False, 'error': 'Invalid skipped section'}), 400

    try:
        connection = get_db_connection()
        with connection.cursor() as cur:
            # Check if a record with the given image_name exists
            check_query = "SELECT COUNT(*) FROM final_data WHERE image_name = %s"
            cur.execute(check_query, (image_name,))
            record_exists = cur.fetchone()[0] > 0

            if record_exists:
                # Update the specific column in the final_data table
                update_query = f"UPDATE final_data SET {column_to_update} = %s WHERE image_name = %s"
                cur.execute(update_query, (reason, image_name))
            else:
                # Insert a new row if no existing record found
                insert_query = f"INSERT INTO final_data (image_name, {column_to_update}) VALUES (%s, %s)"
                cur.execute(insert_query, (image_name, reason))
            
            # Always remove the record from skipped_sections
            delete_query = "DELETE FROM skipped_sections WHERE image_name = %s AND skipped_section = %s"
            cur.execute(delete_query, (image_name, skipped_section))
        
        connection.commit()

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return jsonify({'success': False, 'error': 'Database error'}), 500

    finally:
        if 'connection' in locals():
            connection.close()

    # Return success response
    return jsonify({'success': True}), 200



@app.route('/download_excel')
def download_excel():
    connection = get_db_connection()
    query = """SELECT 
                        id, user_id, username, image_name, todays_work, address, 
                        company_name, company_owner_name, telephone_number, company_name2, 
                        company_address2, code_number, telephone_number2,
                        R1_record_number, R1_type_code, R1_garbage_weight, R1_number_of_items, R1_registered_number, 
           R1_company_name, R1_company_address, R1_address_code, R1_number_of_company_items, 
           R1_company_item_code, R1_company_name_2,R1_company_address2, R1_address_code2, R2_record_number, R2_type_code, R2_garbage_weight, 
           R2_number_of_items, R2_registered_number, R2_company_name, R2_company_address, R2_address_code, 
           R2_number_of_company_items, R2_company_item_code, R2_company_name_2,R2_company_address2, R2_address_code2, R3_record_number, 
           R3_type_code, R3_garbage_weight, R3_number_of_items, R3_registered_number, R3_company_name, 
           R3_company_address, R3_address_code, R3_number_of_company_items, R3_company_item_code, 
           R3_company_name_2,R3_company_address2, R3_address_code2, R4_record_number, R4_type_code, R4_garbage_weight, R4_number_of_items, 
           R4_registered_number, R4_company_name, R4_company_address, R4_address_code, 
           R4_number_of_company_items, R4_company_item_code, R4_company_name_2,R4_company_address2, R4_address_code2
                    FROM user_images"""
    df = pd.read_sql(query, connection)
    
    # Define custom headers
    custom_headers = ['id', 'user_id', 'username', 'image_name', 'todays_work', 'address', 
                        'company_name', 'company_owner_name', 'telephone_number', 'company_name2', 
                        'company_address2', 'code_number', 'telephone_number2',
                        'R1_record_number', 'R1_type_code', 'R1_garbage_weight', 'R1_number_of_items', 
                        'R1_registered_number', 'R1_company_name', 'R1_company_address', 'R1_address_code', 
                        'R1_number_of_company_items', 'R1_company_item_code', 'R1_company_name_2','R1_company_address2', 'R1_address_code2',
                        'R2_record_number', 'R2_type_code', 'R2_garbage_weight', 'R2_number_of_items', 
                        'R2_registered_number', 'R2_company_name', 'R2_company_address', 'R2_address_code', 
                        'R2_number_of_company_items', 'R2_company_item_code', 'R2_company_name_2','R2_company_address2', 'R2_address_code2',
                        'R3_record_number', 'R3_type_code', 'R3_garbage_weight', 'R3_number_of_items', 
                        'R3_registered_number', 'R3_company_name', 'R3_company_address', 'R3_address_code', 
                        'R3_number_of_company_items', 'R3_company_item_code', 'R3_company_name_2','R3_company_address2', 'R3_address_code2',
                        'R4_record_number', 'R4_type_code', 'R4_garbage_weight', 'R4_number_of_items', 
                        'R4_registered_number', 'R4_company_name', 'R4_company_address', 'R4_address_code', 
                        'R4_number_of_company_items', 'R4_company_item_code', 'R4_company_name_2','R4_company_address2', 'R4_address_code2']  
    # Replace with your desired headers

    # Assign the custom headers to the DataFrame
    df.columns = custom_headers
    
    file_path = 'exported_data.xlsx'
    df.to_excel(file_path, index=False)
    connection.close()
    
    return send_file(file_path, as_attachment=True)



# this is the admin log in function 

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        connection = get_db_connection()

        try:
            cur = connection.cursor(dictionary=True)
            cur.execute("SELECT * FROM admins WHERE username = %s", (username,))
            admin = cur.fetchone()
            cur.close()

            if admin and check_password_hash(admin['password'], password):
                # Update the timestamp if the password matches
                cur = connection.cursor()
                cur.execute("UPDATE admins SET created_at = CURRENT_TIMESTAMP WHERE username = %s", (username,))
                connection.commit()
                cur.close()

                # Set the session
                session['admin_id'] = admin['id']
                return redirect(url_for('admin'))
            else:
                flash('Invalid credentials')
        except mysql.connector.Error as err:
            print(f"Error: {err}")
            flash('An error occurred. Please try again.')
        finally:
            connection.close()

    return render_template('admin_login.html')



# this is the user log in function
 
@app.route('/user_login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        connection = get_db_connection()

        try:
            cur = connection.cursor(dictionary=True)
            # Fetch user data
            cur.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cur.fetchone()
            cur.close()

            if user and check_password_hash(user['password'], password):
                # Update the timestamp if the password matches
                cur = connection.cursor()
                cur.execute("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE username = %s", (username,))
                connection.commit()
                cur.close()

                # Set the session
                session['user_id'] = user['id']
                session['username'] = username
                return redirect(url_for('userpage', user_id=user['id']))
            else:
                flash('Invalid credentials')
        except mysql.connector.Error as err:
            print(f"Error: {err}")
            flash('An error occurred. Please try again.')
        finally:
            connection.close()

    return render_template('user_login.html')



# this is the log out function 

@app.route('/logout')
def logout():
    session.pop('admin_id', None)
    session.pop('user_id', None)
    return redirect(url_for('index'))


if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)