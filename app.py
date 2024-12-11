from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for, flash, session
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import img_to_array, load_img
import numpy as np
import json
import os
from datetime import timedelta
import datetime
import gdown

app = Flask(__name__, static_folder='static', template_folder='templates')

app.secret_key = os.environ.get('SECRET_KEY', 'default_secret_key')
app.permanent_session_lifetime = timedelta(minutes=600)

model_path = '/var/data/coffee_plant_disease_model.keras'
if not os.path.exists(model_path):
    google_drive_file_id = '1ImDY6s5Cjux5YOgodQcDmW8U3mGbXgcq'
    download_url = f'https://drive.google.com/uc?export=download&id={google_drive_file_id}'
    gdown.download(download_url, model_path, quiet=False)


with open(os.path.join(app.root_path, 'data/diseases.json')) as f:
    diseases_info = json.load(f)

diseases = [item for item in diseases_info if item['name'] not in ['Healthy'] and item['name'] in ['Anthracnose', 'Brown Eye', 'Leaf Rust']]
pests = [item for item in diseases_info if item['name'] not in ['Healthy'] and item['name'] in ['Leaf Scale', 'Mealy Bug', 'Twig Borer']]
result_record_path = os.path.join(app.root_path, 'data/resultRecord.json')

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
            item.get('name', '').lower(),
            item.get('description', '').lower(),
            item.get('longDescription', '').lower(),
            item.get('cure', '').lower(),
            item.get('longCure', '').lower()
        ]
        return any(query in field for field in fields_to_search)
    
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
        record = {"date": str(datetime.date.today()), "account-id": session['account_id'], "results": predicted_disease_name, "farm": session.get('farm', 'Unknown')}
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

    result_file_path = os.path.join(app.root_path, 'data/resultRecord.json')
    with open(result_file_path) as f:
        result_records = json.load(f)

    return jsonify(result_records)

@app.route('/recordedResults.html')
def recorded_results():
    if 'account_id' not in session:
        flash('You need to log in first.', 'error')
        return redirect(url_for('login'))

    result_file_path = os.path.join(app.root_path, 'data/resultRecord.json')
    with open(result_file_path) as f:
        result_records = json.load(f)

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
        result_record_path = os.path.join(app.root_path, 'data/resultRecord.json')
        with open(result_record_path, 'r') as file:
            data = json.load(file)

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

        with open(result_record_path, 'r') as f:
            result_records = json.load(f)
        
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