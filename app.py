import os
from flask import Flask, render_template, request, jsonify, url_for
from utils.ai_service import analyze_image
import uuid
from datetime import datetime

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
app.config['UPLOAD_FOLDER'] = 'uploads'

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Common categories list
CATEGORIES = [
    "Portfel", "Telefon", "Klucze", "Dokumenty", "Plecak", "Torebka", 
    "Słuchawki", "Laptop", "Tablet", "Zegarek", "Biżuteria", "Okulary", 
    "Karta płatnicza", "Dowód osobisty", "Paszport", "Prawo jazdy", 
    "Książka", "Ubranie", "Kurtka", "Czapka", "Szalik", "Rękawiczki", 
    "Buty", "Parasol", "Bagaż", "Walizka", "Torba sportowa", 
    "Wózek dziecięcy", "Zabawka", "Rower", "Hulajnoga", "Kask", 
    "Ładowarka", "Powerbank", "Kabel", "Aparat fotograficzny", 
    "Instrument muzyczny", "Sprzęt sportowy", "Kosmetyczka", "Leki", 
    "Jedzenie", "Napój"
]
CATEGORIES.sort()
CATEGORIES.append("Inne")

# In-memory storage for lost items
items = []

@app.route('/')
def index():
    return render_template('index.html', categories=CATEGORIES)

@app.route('/search')
def search():
    query = request.args.get('q', '').lower()
    category = request.args.get('category', '')
    location = request.args.get('location', '').lower()
    date = request.args.get('date', '')

    filtered_items = items

    if query:
        filtered_items = [i for i in filtered_items if query in i['name'].lower() or query in i['description'].lower()]
    
    if category:
        filtered_items = [i for i in filtered_items if i['category'] == category]
    
    if location:
        filtered_items = [i for i in filtered_items if location in i['location'].lower()]
    
    if date:
        filtered_items = [i for i in filtered_items if i['date'] == date]

    return render_template('search.html', items=filtered_items, categories=CATEGORIES)

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'image' not in request.files:
        return jsonify({'error': 'No image part'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file:
        # In a real app, we might save the file or process it in memory
        # For this mock, we just pass the filename or stream to the mock service
        result = analyze_image(file)
        return jsonify(result)

@app.route('/report', methods=['POST'])
def report():
    data = request.json
    
    # Basic validation
    if not data or not data.get('name') or not data.get('contact'):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Create item record
    item = {
        'id': len(items) + 1,
        'name': data.get('name'),
        'category': data.get('category'),
        'date': data.get('date'),
        'location': data.get('location'),
        'description': data.get('description'),
        'contact': data.get('contact'),
        'status': 'lost'
    }
    
    items.append(item)
    print(f"New Item Reported: {item}") # Log to console for verification
    
    return jsonify({'success': True, 'message': 'Item reported successfully!', 'id': item['id']})

# In-memory storage for datasets (Official Portal)
datasets = [
    {'title': 'Rzeczy znalezione - Październik 2023', 'date': '2023-11-01', 'count': 15, 'status': 'Opublikowany'},
    {'title': 'Rzeczy znalezione - Wrzesień 2023', 'date': '2023-10-01', 'count': 42, 'status': 'Opublikowany'}
]

@app.route('/urzad')
def urzad_dashboard():
    return render_template('official/dashboard.html', datasets=datasets)

@app.route('/urzad/upload')
def urzad_upload():
    return render_template('official/upload_wizard.html')

@app.route('/urzad/upload_csv', methods=['POST'])
def upload_csv():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file:
        from utils.schema import FoundItemSchema
        items, errors = FoundItemSchema.parse_csv(file.stream)
        
        return jsonify({
            'success': True,
            'items': items,
            'errors': errors,
            'count': len(items)
        })

@app.route('/urzad/publish', methods=['POST'])
def publish_dataset():
    data = request.json
    # Mock integration with dane.gov.pl API
    # In reality: requests.post('https://api.dane.gov.pl/datasets', json=data)
    
    new_dataset = {
        'title': data.get('title'),
        'date': datetime.now().strftime('%Y-%m-%d'),
        'count': len(data.get('items', [])),
        'status': 'Opublikowany'
    }
    datasets.insert(0, new_dataset) # Add to top of list
    
    print(f"PUBLISHING TO DANE.GOV.PL: {new_dataset}")
    
    return jsonify({'success': True, 'message': 'Zbiór danych został opublikowany w portalu dane.gov.pl'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
