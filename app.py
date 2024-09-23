from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for, flash, session
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import img_to_array, load_img
import numpy as np
import json
import os

app = Flask(__name__, static_folder='static', template_folder='templates')

# Secret key for session management and flashing messages
app.secret_key = 'coffee_diseases_detection'

# Load disease information
with open(os.path.join(app.root_path, 'data/diseases.json')) as f:
    diseases_info = json.load(f)

# Load accounts for login
def load_accounts():
    with open(os.path.join(app.root_path, 'data/account.json')) as f:
        return json.load(f)['accounts']

# Load the model
model = load_model('coffee_plant_disease_model.keras')

# Categorize diseases and pests
diseases = [item for item in diseases_info if item['name'] not in ['Healthy'] and item['name'] in ['Anthracnose', 'Brown Eye', 'Leaf Rust']]
pests = [item for item in diseases_info if item['name'] not in ['Healthy'] and item['name'] in ['Leaf Scale', 'Mealy Bug', 'Twig Borer']]

# Make login page the root path
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        account_id = request.form['account-id']
        password = request.form['password']

        # Load account details from JSON
        accounts = load_accounts()

        # Check if account-id and password match
        for account in accounts:
            if account['account-id'] == account_id and account['password'] == password:
                # Store the account-id and position in the session
                session['account_id'] = account_id
                session['position'] = account['position']
                return redirect(url_for('tools'))

        # If login fails
        flash('Login failed. Please check your account ID and password.', 'error')

    return render_template('login.html')

@app.route('/tools.html')
def tools():
    # Get the position from the session
    position = session.get('position', '')
    return render_template('pages/tools.html', position=position)

@app.route('/resource.html')
def resource():
    return render_template('pages/resource.html', diseases=diseases, pests=pests)

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query', '').lower()

    filtered_diseases = [
        item for item in diseases_info
        if (query in item['name'].lower() or query in item['description'].lower())
        and item['name'] in ['Anthracnose', 'Brown Eye', 'Leaf Rust']
    ]

    filtered_pests = [
        item for item in diseases_info
        if (query in item['name'].lower() or query in item['description'].lower())
        and item['name'] in ['Leaf Scale', 'Mealy Bug', 'Twig Borer']
    ]
    
    no_results = len(filtered_diseases) == 0 and len(filtered_pests) == 0

    return render_template('pages/search_results.html', diseases=filtered_diseases, pests=filtered_pests, no_results=no_results, query=query)

@app.route('/detail/<name>')
def detail(name):
    item = next((item for item in diseases_info if item['name'] == name), None)
    return render_template('pages/detail.html', item=item) if item else "Item not found", 404

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@app.route('/predict', methods=['POST'])
def predict():
    file = request.files['file']

    file_path = os.path.join('uploads', file.filename)
    file.save(file_path)

    img = load_img(file_path, target_size=(299, 299))
    img_array = img_to_array(img) / 255.0
    img_array = np.expand_dims(img_array, axis=0)

    predictions = model.predict(img_array)
    predicted_class = np.argmax(predictions, axis=1)

    classes = ['Anthracnose', 'Brown Eye', 'Healthy', 'Leaf Rust', 'Leaf Scale', 'Mealy Bug', 'Twig Borer']
    predicted_disease_name = classes[predicted_class[0]]

    disease_info = next((item for item in diseases_info if item["name"] == predicted_disease_name), None)
    
    if disease_info:
        response = {
            'disease_name': disease_info['name'],
            'disease_description': disease_info['description'],
            'disease_cure': disease_info['cure'],
            'disease_image': disease_info['image']
        }
    else:
        response = {
            'error': 'Disease not found in the database.'
        }

    os.remove(file_path)

    return jsonify(response)

# Route to serve resultRecord.json
@app.route('/get-records', methods=['GET'])
def get_records():
    with open(os.path.join(app.root_path, 'data/resultRecord.json')) as f:
        records = json.load(f)
    return jsonify(records)

# Route for the recorded results page
@app.route('/recordedResults.html')
def recorded_results():
    return render_template('pages/recordedResults.html')

if __name__ == '__main__':
    app.run(debug=True)
