from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for, flash, session
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import img_to_array, load_img
import numpy as np
import json
import os
from datetime import timedelta
import datetime

app = Flask(__name__, static_folder='static', template_folder='templates')

app.secret_key = 'coffee_diseases_detection'
app.permanent_session_lifetime = timedelta(minutes=600)

model = load_model('coffee_plant_disease_model.keras')

with open(os.path.join(app.root_path, 'data/diseases.json')) as f:
    diseases_info = json.load(f)

diseases = [item for item in diseases_info if item['name'] not in ['Healthy'] and item['name'] in ['Anthracnose', 'Brown Eye', 'Leaf Rust']]
pests = [item for item in diseases_info if item['name'] not in ['Healthy'] and item['name'] in ['Leaf Scale', 'Mealy Bug', 'Twig Borer']]

def load_accounts():
    with open(os.path.join(app.root_path, 'data/account.json')) as f:
        return json.load(f)['accounts']

def save_accounts(accounts):
    with open(os.path.join(app.root_path, 'data/account.json'), 'w') as f:
        json.dump({'accounts': accounts}, f, indent=4)

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
                session['affiliation'] = account.get('affiliation', '')
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
    filtered_diseases = [item for item in diseases_info if (query in item['name'].lower() or query in item['description'].lower()) and item['name'] in ['Anthracnose', 'Brown Eye', 'Leaf Rust']]
    filtered_pests = [item for item in diseases_info if (query in item['name'].lower() or query in item['description'].lower()) and item['name'] in ['Leaf Scale', 'Mealy Bug', 'Twig Borer']]
    no_results = len(filtered_diseases) == 0 and len(filtered_pests) == 0
    return render_template('pages/search_results.html', diseases=filtered_diseases, pests=filtered_pests, no_results=no_results, query=query)

@app.route('/detail/<name>')
def detail(name):
    if 'account_id' not in session:
        flash('You need to log in first.', 'error')
        return redirect(url_for('login'))
    item = next((item for item in diseases_info if item['name'] == name), None)
    return render_template('pages/detail.html', item=item) if item else "Item not found", 404

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@app.route('/predict', methods=['POST'])
def predict():
    if 'account_id' not in session:
        flash('You need to log in first.', 'error')
        return redirect(url_for('login'))

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
        response = {'disease_name': disease_info['name'], 'disease_description': disease_info['description'], 'disease_cure': disease_info['cure'], 'disease_image': disease_info['image']}
        record = {"date": str(datetime.date.today()), "account-id": session['account_id'], "results": predicted_disease_name, "affiliation": session.get('affiliation', 'Unknown')}
        result_record_path = os.path.join(app.root_path, 'data/resultRecord.json')
        if os.path.exists(result_record_path):
            with open(result_record_path, 'r+') as f:
                records = json.load(f)
                records.append(record)
                f.seek(0)
                json.dump(records, f, indent=4)
        else:
            with open(result_record_path, 'w') as f:
                json.dump([record], f, indent=4)
    else:
        response = {'error': 'Disease not found in the database.'}

    os.remove(file_path)
    return jsonify(response)

@app.route('/get-records', methods=['GET'])
def get_records():
    if 'account_id' not in session:
        flash('You need to log in first.', 'error')
        return redirect(url_for('login'))

    with open(os.path.join(app.root_path, 'data/resultRecord.json')) as f:
        records = json.load(f)
    return jsonify(records)

@app.route('/recordedResults.html')
def recorded_results():
    if 'account_id' not in session:
        flash('You need to log in first.', 'error')
        return redirect(url_for('login'))

    return render_template('pages/recordedResults.html')

@app.route('/admin.html')
def admin():
    if 'account_id' not in session:
        flash('You need to log in first.', 'error')
        return redirect(url_for('login'))

    if session.get('position') != 'Supervisor':
        flash('Access denied. Admins only.', 'error')
        return redirect(url_for('tools'))

    accounts = load_accounts()
    return render_template('pages/admin.html', accounts=accounts)

@app.route('/add_user', methods=['POST'])
def add_user():
    account_id = request.form['account-id']
    password = request.form['password']
    affiliation = request.form['affiliation']
    position = request.form['position'] 

    accounts = load_accounts()

    if any(account['account-id'] == account_id for account in accounts):
        flash('Account ID already exists.', 'error')
        return redirect(url_for('admin'))

    new_account = {'account-id': account_id, 'password': password, 'affiliation': affiliation, 'position': position}  # Capitalization here
    accounts.append(new_account)
    save_accounts(accounts)

    flash('User added successfully!', 'success')
    return redirect(url_for('admin'))


@app.route('/delete_user/<account_id>')
def delete_user(account_id):
    accounts = load_accounts()
    updated_accounts = [account for account in accounts if account['account-id'] != account_id]

    if len(updated_accounts) == len(accounts):
        flash('User not found.', 'error')
    else:
        save_accounts(updated_accounts)
        flash('User deleted successfully.', 'success')

    return redirect(url_for('admin'))

@app.route('/edit_user/<account_id>', methods=['POST'])
def edit_user(account_id):
    accounts = load_accounts()
    account = next((acc for acc in accounts if acc['account-id'] == account_id), None)

    if not account:
        flash('User not found.', 'error')
        return redirect(url_for('admin'))

    account['password'] = request.form['password']
    account['affiliation'] = request.form['affiliation']
    account['position'] = request.form['position']  
    save_accounts(accounts)

    flash('User updated successfully!', 'success')
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True)
