from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for, flash, session
import numpy as np
import json
import os
import datetime
import gdown
import tensorflow.lite as tflite
from PIL import Image
from datetime import timedelta
import gc
import threading
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.oauth2 import service_account
import io

ACCOUNT_JSON_FILE_ID = '1uYdQhbuZxTRLBAn8GrAB6OKV8tUdpJow'
RESULT_RECORD_JSON_FILE_ID = '1wxxQWr28eKAGqECGpeBxJKvTxgzFhO-r'
SERVICE_ACCOUNT_FILE_ID = '1Ym9P1C7Gax2LXFdj5yohIVT-SZ8xp_Qu'

SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'data/well.json'

def download_service_account_file():
    """Download the service account JSON file using gdown."""
    gdown.download(f'https://drive.google.com/uc?id={SERVICE_ACCOUNT_FILE_ID}', SERVICE_ACCOUNT_FILE, quiet=False)

def initialize_drive_service():
    """Initialize Google Drive service using the downloaded service account credentials."""
    download_service_account_file() 
    credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    drive_service = build('drive', 'v3', credentials=credentials)
    return drive_service

def download_file(file_id, local_path):
    """Download a file from Google Drive to a local path."""
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.FileIO(local_path, 'wb')
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        status, done = downloader.next_chunk()
        print(f"Download progress: {int(status.progress() * 100)}%")

def upload_file(file_id, local_path):
    """Upload and overwrite a file in Google Drive."""
    media = MediaFileUpload(local_path, mimetype='application/json')
    drive_service.files().update(fileId=file_id, media_body=media).execute()

def load_accounts():
    """Load accounts from Google Drive."""
    download_file(ACCOUNT_JSON_FILE_ID, 'data/account.json')
    with open('data/account.json') as f:
        return json.load(f)['accounts']

def save_accounts(accounts):
    """Save accounts to Google Drive."""
    with open('data/account.json', 'w') as f:
        json.dump({'accounts': accounts}, f, indent=4)
    upload_file(ACCOUNT_JSON_FILE_ID, 'data/account.json')

def load_result_records():
    """Load result records from Google Drive."""
    try:
        download_file(RESULT_RECORD_JSON_FILE_ID, 'data/resultRecord.json')
        with open('data/resultRecord.json') as f:
            return json.load(f)
    except Exception as e:
        print("Error loading result records from file:", str(e)) 
        raise

def save_result_records(new_record):
    """Save result records to Google Drive."""
    try:
        with open('data/resultRecord.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {'records': []}  
    data['records'].append(new_record)
    
    with open('data/resultRecord.json', 'w') as f:
        json.dump(data, f, indent=4)
    
    upload_file(RESULT_RECORD_JSON_FILE_ID, 'data/resultRecord.json')

drive_service = initialize_drive_service()

app = Flask(__name__, static_folder='static', template_folder='templates')

app.secret_key = os.environ.get('SECRET_KEY', 'default_secret_key')
app.permanent_session_lifetime = timedelta(minutes=600)

interpreter = None
input_details = None
output_details = None

tflite_model_path = os.path.join('var', 'data', 'coffee_plant_disease_model.tflite')
os.makedirs(os.path.dirname(tflite_model_path), exist_ok=True)

download_lock = threading.Lock()

def ensure_model_exists():
    """Ensure the TFLite model is available locally, downloading it if necessary."""
    if os.path.exists(tflite_model_path):
        print(f"File already exists at {tflite_model_path}. Skipping download.")
        return

    with download_lock:
        if os.path.exists(tflite_model_path):
            print(f"File already exists at {tflite_model_path} (post-lock). Skipping download.")
            return

        google_drive_file_id = '1tDXXzf7LR8STYl23iwRuQtcJXPiNP7i0'
        download_url = f'https://drive.google.com/uc?export=download&id={google_drive_file_id}'

        try:
            print(f"File not found at {tflite_model_path}. Downloading...")
            gdown.download(download_url, tflite_model_path, quiet=False)
            print(f"File downloaded to {tflite_model_path}")
        except Exception as e:
            print(f"Failed to download the file: {e}")
            raise

def load_model():
    """Load the TensorFlow Lite model into memory."""
    global interpreter, input_details, output_details
    if interpreter is None:
        print("Loading TensorFlow Lite model...")
        interpreter = tflite.Interpreter(model_path=tflite_model_path)
        interpreter.allocate_tensors()
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        print("Model loaded.")

ensure_model_exists()

with open(os.path.join(app.root_path, 'data/diseases.json')) as f:
    diseases_info = json.load(f)

diseases = [item for item in diseases_info if item['name'] not in ['Healthy'] and item['name'] in ['Anthracnose', 'Brown Eye', 'Leaf Rust']]
pests = [item for item in diseases_info if item['name'] not in ['Healthy'] and item['name'] in ['Leaf Scale', 'Mealy Bug', 'Twig Borer']]
result_record_path = os.path.join(app.root_path, 'data/resultRecord.json')

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'account_id' in session:
        return redirect(url_for('tools'))

    if request.method == 'POST':
        account_id = request.form['account-id']
        password = request.form['password']
        accounts = load_accounts()

        for account in accounts:
            if account['account-id'] == account_id and account['password'] == password:
                session['account_id'] = account_id
                session['position'] = account['position']
                session['farm'] = account.get('farm', '')
                session.permanent = True
                return redirect(url_for('tools'))

        flash('Login failed. Please check your account ID and password.', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/tools.html')
def tools():
    if 'account_id' not in session:
        flash('You need to log in first.', 'error')
        return redirect(url_for('login'))

    position = session.get('position', '')
    return render_template('pages/tools.html', position=position)

@app.route('/resource.html')
def resource():
    if 'account_id' not in session:
        flash('You need to log in first.', 'error')
        return redirect(url_for('login'))

    return render_template('pages/resource.html', diseases=diseases, pests=pests)

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query', '').lower()
    
    def matches_query(item):
        fields_to_search = [
            'name',  
            'description', 
            'longDescription',  
            'cure',  
            'longCure'  
        ]
        
        return any(
            query in str(field).lower() for field_list_name in fields_to_search
            for field in item.get(field_list_name, [])
        ) or query in item.get('name', '').lower()

    filtered_diseases = [
        item for item in diseases_info 
        if matches_query(item) and item['name'] in ['Anthracnose', 'Brown Eye', 'Leaf Rust']
    ]
    
    filtered_pests = [
        item for item in diseases_info 
        if matches_query(item) and item['name'] in ['Leaf Scale', 'Mealy Bug', 'Twig Borer']
    ]
    
    no_results = len(filtered_diseases) == 0 and len(filtered_pests) == 0
    
    return render_template(
        'pages/search_results.html',
        diseases=filtered_diseases,
        pests=filtered_pests,
        no_results=no_results,
        query=query
    )

@app.route('/detail/<name>')
def detail(name):
    if 'account_id' not in session:
        flash('You need to log in first.', 'error')
        return redirect(url_for('login'))

    item = next((item for item in diseases_info if item['name'] == name), None)
    
    if item:
        item['longDescription'] = '<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;' + '<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'.join(item['longDescription'])
        item['longCure'] = '<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;' + '<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'.join(item['longCure'])

    return render_template('pages/detail.html', item=item) if item else ("Item not found", 404)

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@app.route('/predict', methods=['POST'])
def predict():
    if 'account_id' not in session:
        flash('You need to log in first.', 'error')
        return redirect(url_for('login'))

    if 'file' not in request.files or request.files['file'].filename == '':
        return jsonify({'error': 'No file uploaded or invalid file.'}), 400

    file = request.files['file']
    file_path = os.path.join('uploads', file.filename)

    try:
        os.makedirs('uploads', exist_ok=True)
        file.save(file_path)
        app.logger.info(f"File saved successfully at {file_path}")
    except Exception as e:
        app.logger.error(f"File save error: {e}")
        return jsonify({'error': 'Failed to save the uploaded file.'}), 500

    try:
        load_model()

        img = Image.open(file_path).resize((299, 299)).convert('RGB')
        img_array = np.array(img) / 255.0
        img_array = np.expand_dims(img_array, axis=0).astype(np.float32)

        try:
            interpreter.set_tensor(input_details[0]['index'], img_array)
            interpreter.invoke()
            predictions = interpreter.get_tensor(output_details[0]['index'])
        except Exception as e:
            app.logger.error(f"Model prediction error: {e}")
            return jsonify({'error': 'Prediction failed during model inference.'}), 500

        predicted_class = np.argmax(predictions, axis=1)[0]
        classes = ['Anthracnose', 'Brown Eye', 'Healthy', 'Leaf Rust', 'Leaf Scale', 'Mealy Bug', 'Twig Borer']
        predicted_disease_name = classes[predicted_class]

        disease_info = next((item for item in diseases_info if item['name'] == predicted_disease_name), None)

        if disease_info:
            response = {
                'disease_name': disease_info['name'],
                'disease_description': disease_info['description'][0] if disease_info['description'] else '',
                'disease_cure': disease_info['cure'][0] if disease_info['cure'] else '',
                'disease_image': disease_info['image']
            }

            record = {
                "date": str(datetime.date.today()),
                "account-id": session['account_id'],
                "results": predicted_disease_name,
                "farm": session.get('farm', 'Unknown')
            }

            try:
                save_result_records(record)
            except Exception as e:
                app.logger.error(f"Error saving record: {e}")
                return jsonify({'error': 'Failed to save the record.'}), 500
        else:
            app.logger.warning("Disease not found in database.")
            response = {'error': 'Disease not found in the database.'}

        return jsonify(response)
    except Exception as e:
        app.logger.error(f"Unexpected error: {e}")
        return jsonify({'error': 'Prediction process failed.', 'details': str(e)}), 500
    finally:
        try:
            os.remove(file_path)
            app.logger.info(f"Temporary file {file_path} deleted successfully.")
        except Exception as e:
            app.logger.warning(f"Failed to delete file: {e}")

        gc.collect()


@app.route('/get-records', methods=['GET'])
def get_records():
    try:
        data = load_result_records()
        
        if isinstance(data, dict) and 'records' in data:
            records = data['records']
            
            if isinstance(records, list):
                return jsonify(records)
            else:
                raise ValueError("'records' is not a list")
        else:
            raise ValueError("'records' key not found in the data")
    except Exception as e:
        print("Error loading records:", str(e))
        return jsonify({"error": str(e)}), 500

    
@app.route('/recordedResults.html')
def recorded_results():
    if 'account_id' not in session:
        flash('You need to log in first.', 'error')
        return redirect(url_for('login'))

    result_records = load_result_records()

    farms = list(set([record['farm'] for record in result_records]))
    month_years = list(set([record['date'][:7] for record in result_records]))

    return render_template('pages/recordedResults.html', farms=farms, month_years=month_years)

@app.route('/admin.html')
def admin():
    if 'account_id' not in session:
        flash('You need to log in first.', 'error')
        return redirect(url_for('login'))

    if session.get('position') != 'Supervisor':
        flash('Access denied. Admins only.', 'error')
        return redirect(url_for('tools'))

    accounts = load_accounts()

    farms = list(set([account['farm'] for account in accounts]))

    return render_template('pages/admin.html', accounts=accounts, farms=farms)

@app.route('/delete_user/<account_id>', methods=['POST'])
def delete_user(account_id):
    accounts = load_accounts()
    updated_accounts = [account for account in accounts if account['account-id'] != account_id]

    if len(updated_accounts) == len(accounts):
        flash('User not found.', 'error')
    else:
        save_accounts(updated_accounts)
        flash('User deleted successfully.', 'success')

    return redirect(url_for('admin'))

@app.route('/add_user', methods=['POST'])
def add_user():
    account_id = request.form['account-id']
    password = request.form['password']
    position = request.form['position']
    
    farm = request.form['farm']
    if farm == 'add_new_farm':
        farm = request.form['newFarm']
    
    new_account = {
        "account-id": account_id,
        "password": password,
        "farm": farm,
        "position": position
    }

    accounts = load_accounts()
    accounts.append(new_account)
    save_accounts(accounts)
    
    flash('User added successfully.', 'success')
    return redirect(url_for('admin'))

@app.route('/edit_user/<account_id>', methods=['POST'])
def edit_user(account_id):
    password = request.form.get('password')
    farm = request.form.get('farm')
    new_farm = request.form.get('newFarm')
    position = request.form.get('position')

    if farm == 'add_new_farm' and new_farm:
        farm = new_farm  

    accounts = load_accounts()
    for user in accounts:
        if user['account-id'] == account_id:
            user['password'] = password
            user['farm'] = farm 
            user['position'] = position
            break

    save_accounts(accounts)
    flash('User updated successfully.', 'success')
    return redirect(url_for('admin'))

@app.route('/history', methods=['GET'])
def get_history():
    account_id = session.get('account_id') 
    if not account_id:
        return jsonify({"error": "User not logged in"}), 401

    try:
        data = load_result_records()

        user_history = [record for record in data if record['account-id'] == account_id]
        sorted_history = sorted(
            user_history,
            key=lambda x: datetime.datetime.strptime(x['date'], "%Y-%m-%d"),  
            reverse=True
        )
        return jsonify(sorted_history)

    except Exception as e:
        app.logger.error(f"Error in /history: {e}")
        return jsonify({"error": "An error occurred while fetching history."}), 500

@app.route('/count_results', methods=['GET'])
def count_results():
    try:
        accounts = load_accounts()
        total_farmers = sum(1 for acc in accounts if acc['position'] == 'Farmer')
        total_farms = len(set(acc['farm'] for acc in accounts))

        result_records = load_result_records()
        
        healthy_count = sum(1 for record in result_records if record['results'] == 'Healthy')
        unhealthy_count = len(result_records) - healthy_count

        result_counts = {
            'healthy': healthy_count,
            'unhealthy': unhealthy_count,
            'farm': total_farms,
            'farmer': total_farmers
        }

        return jsonify(result_counts)
    except Exception as e:
        return jsonify({'error': 'Failed to fetch results', 'details': str(e)}), 500
    
if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)