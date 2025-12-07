import os
import glob
import io
import json
from math import radians, sin, cos, sqrt, atan2
from flask import Flask, render_template, request, jsonify, url_for, Response, abort
import hashlib
from utils.ai_service import analyze_image
from utils.schema import FoundItemSchema
import uuid
from datetime import datetime
# Helper to calculate MD5 checksum of a file-like object

def calculate_md5(file_stream):
    """Calculate MD5 hash for the given file stream.
    The stream position will be reset to the start after reading.
    """
    file_stream.seek(0)
    md5 = hashlib.md5()
    for chunk in iter(lambda: file_stream.read(4096), b""):
        md5.update(chunk)
    file_stream.seek(0)
    return md5.hexdigest()

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
# Track dataset files for downloads
dataset_files = []
# Items originating from official datasets (used in search view)
official_items = []


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _slugify(text):
    slug = ''.join(ch.lower() if ch.isalnum() else '-' for ch in text)
    slug = '-'.join(filter(None, slug.split('-')))
    return slug or 'dataset'


def _sanitize_record(row: dict):
    """Keep only allowed fields, trim strings, normalize numeric coords/radius."""
    allowed_fields = set(FoundItemSchema.REQUIRED_FIELDS + FoundItemSchema.OPTIONAL_FIELDS)
    numeric_fields = {'location_lat', 'location_lng', 'location_radius'}
    cleaned = {}
    for key, value in row.items():
        if key not in allowed_fields:
            continue  # drop unknown fields like "null"
        if key in numeric_fields:
            num_val = _to_float(value)
            if num_val is None:
                cleaned[key] = None
            else:
                cleaned[key] = num_val
        else:
            # Preserve empty strings for required-field validation, but trim whitespace
            cleaned[key] = str(value).strip() if value is not None else ''
    return cleaned


def _build_official_items(raw_rows):
    """Convert raw CSV/JSON rows into searchable item dicts."""
    built = []
    start_id = len(items) + 1
    for idx, row in enumerate(raw_rows, start=start_id):
        built.append(build_item_from_row(row, idx))
    return built


def _annotate_specific_items():
    """
    Add security question + example answers to known records
    without touching source files.
    """
    for item in official_items:
        name_lower = (item.get('name') or '').lower()
        desc_lower = (item.get('description') or '').lower()
        if 'klucze' in name_lower and 'brelok' in desc_lower and 'mostowa' in (item.get('location') or '').lower():
            item['security_question'] = "W kształcie jakiego auta jest ten brelok?"


def build_item_from_row(row, item_id):
    city = row.get('miejsce_znalezienia_miasto') or row.get('city') or ''
    street = row.get('miejsce_znalezienia_ulica') or row.get('street') or ''
    location_parts = [part for part in [city, street] if part]
    location_label = ", ".join(location_parts) if location_parts else row.get('location', '')

    return {
        'id': item_id,
        'name': row.get('nazwa_przedmiotu') or row.get('name') or '',
        'category': row.get('kategoria') or row.get('category') or '',
        'date': row.get('data_znalezienia') or row.get('date') or '',
        'location': location_label,
        'location_city': city,
        'location_street': street,
        'location_lat': _to_float(row.get('location_lat') or row.get('lat')),
        'location_lng': _to_float(row.get('location_lng') or row.get('lng')),
        'location_radius': _to_float(row.get('location_radius')),
        'description': row.get('opis_szczegolowy') or row.get('opis') or row.get('description') or '',
        'contact': row.get('kontakt_email') or row.get('contact') or '',
        'status': row.get('status') or 'znaleziony',
        'security_question': row.get('pytanie_weryfikacyjne') or row.get('security_question') or '',
    }

# Dataset parsing helpers
def _validate_items(raw_items):
    valid = []
    errors = []
    for idx, row in enumerate(raw_items, start=1):
        row_errors = FoundItemSchema.validate_row(row)
        if row_errors:
            errors.append({'row': idx, 'errors': row_errors})
        else:
            valid.append(row)
    return valid, errors


def parse_dataset_bytes(raw_bytes, filename):
    """Parse CSV/JSON/JSONL bytes into items + errors."""
    ext = os.path.splitext(filename.lower())[1]

    # CSV
    if ext == '.csv':
        try:
            items, errors = FoundItemSchema.parse_csv(io.BytesIO(raw_bytes))
            items = [_sanitize_record(r) for r in items]
            return items, errors
        except Exception as exc:
            return [], [{"row": 0, "errors": [f"CSV parse error: {exc}"]}]


    # JSON list
    if ext == '.json':
        try:
            data = json.loads(raw_bytes.decode('utf-8'))
            if not isinstance(data, list):
                return [], [{"row": 0, "errors": ["JSON must be an array of records"]}]
            data = [_sanitize_record(r) for r in data]
            return _validate_items(data)
        except Exception as exc:
            return [], [{"row": 0, "errors": [f"JSON parse error: {exc}"]}]

    # JSONL / NDJSON
    if ext in ('.jsonl', '.ndjson'):
        raw_items = []
        try:
            for idx, line in enumerate(raw_bytes.decode('utf-8').splitlines(), start=1):
                if not line.strip():
                    continue
                raw_items.append(_sanitize_record(json.loads(line)))
            return _validate_items(raw_items)
        except Exception as exc:
            return [], [{"row": 0, "errors": [f"JSONL parse error: {exc}"]}]

    return [], [{"row": 0, "errors": [f"Unsupported file type: {ext}"]}]


def load_sample_items():
    """Load initial dataset from sample_data.csv (used for localization demo)."""
    sample_path = os.path.join(os.path.dirname(__file__), 'sample_data.csv')
    if not os.path.exists(sample_path):
        return

    try:
        with open(sample_path, 'rb') as f:
            parsed_items, _ = FoundItemSchema.parse_csv(f)

        items.clear()
        for idx, row in enumerate(parsed_items, start=1):
            items.append(build_item_from_row(row, idx))
    except Exception as exc:
        # Keep the app running even if sample data failed to load
        print(f"Sample data could not be loaded: {exc}")


load_sample_items()


def load_official_datasets():
    """Load official CSV datasets into memory so the portal is pre-populated."""
    data_dir = os.path.join(os.path.dirname(__file__), 'datasets')
    if not os.path.isdir(data_dir):
        return

    loaded_datasets = []
    uploaded_items.clear()
    dataset_files.clear()
    official_items.clear()

    for file_path in sorted(glob.glob(os.path.join(data_dir, '*'))):
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in ('.csv', '.json', '.jsonl', '.ndjson'):
            continue
        try:
            with open(file_path, 'rb') as f:
                raw = f.read()
            parsed_items, _ = parse_dataset_bytes(raw, file_path)
            uploaded_items.extend(parsed_items)
            official_items.extend(_build_official_items(parsed_items))

            dataset_id = os.path.splitext(os.path.basename(file_path))[0]
            city_title = dataset_id.capitalize()
            loaded_datasets.append({
                'id': dataset_id,
                'title': f'Rzeczy znalezione - {city_title}',
                'date': '2023-11-15',
                'count': len(parsed_items),
                'status': 'Opublikowany'
            })
            dataset_files.append({'id': dataset_id, 'path': file_path})
        except Exception as exc:
            print(f"Could not load dataset from {file_path}: {exc}")

    if loaded_datasets:
        datasets.clear()
        datasets.extend(loaded_datasets)
        _annotate_specific_items()


def _find_dataset_path(dataset_id):
    for ds in dataset_files:
        if ds.get('id') == dataset_id:
            return ds.get('path')
    return None


def _load_items_from_file(file_path):
    with open(file_path, 'rb') as f:
        raw = f.read()
    items, _ = parse_dataset_bytes(raw, file_path)
    return items


def _all_dataset_items():
    combined = []
    for ds in dataset_files:
        try:
            combined.extend(_load_items_from_file(ds['path']))
        except Exception as exc:
            print(f"Could not load dataset {ds.get('id')}: {exc}")
    return combined


def _dataset_items_by_city():
    grouped = {}
    for ds in dataset_files:
        try:
            grouped[ds['id']] = _load_items_from_file(ds['path'])
        except Exception as exc:
            print(f"Could not load dataset {ds.get('id')}: {exc}")
    return grouped


@app.route('/')
def index():
    return render_template('index.html', categories=CATEGORIES)


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in meters between two lat/lng points."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)

    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


def within_circle(item, center_lat, center_lng, radius):
    if item.get('location_lat') is None or item.get('location_lng') is None:
        return False
    distance = haversine_distance(center_lat, center_lng, item['location_lat'], item['location_lng'])
    return distance <= radius


@app.route('/search')
def search():
    query = request.args.get('q', '').lower()
    category = request.args.get('category', '')
    location = request.args.get('location', '').lower()
    date = request.args.get('date', '')
    circle_lat = request.args.get('circle_lat', type=float)
    circle_lng = request.args.get('circle_lng', type=float)
    circle_radius = request.args.get('circle_radius', type=float)

    # Combine citizen-reported items with official dataset items
    filtered_items = items + official_items

    if query:
        filtered_items = [i for i in filtered_items if query in i['name'].lower() or query in i['description'].lower()]
    
    if category:
        filtered_items = [i for i in filtered_items if i['category'] == category]
    
    if location:
        filtered_items = [i for i in filtered_items if location in i['location'].lower()]
    
    if date:
        filtered_items = [i for i in filtered_items if i['date'] == date]

    # Prepare map markers before spatial narrowing so the map shows the broader distribution
    map_points = [
        {
            'lat': i['location_lat'],
            'lng': i['location_lng'],
            'name': i['name'],
            'category': i['category'],
            'date': i['date']
        }
        for i in filtered_items
        if i.get('location_lat') is not None and i.get('location_lng') is not None
    ]

    if circle_lat is not None and circle_lng is not None and circle_radius:
        filtered_items = [
            i for i in filtered_items
            if within_circle(i, circle_lat, circle_lng, circle_radius)
        ]

    circle_params = {
        'lat': circle_lat,
        'lng': circle_lng,
        'radius': circle_radius
    }

    return render_template(
        'search.html',
        items=filtered_items,
        categories=CATEGORIES,
        map_points=map_points,
        circle_params=circle_params
    )

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
        # Add MD5 checksum to the response
        result['md5'] = calculate_md5(file.stream)
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
    {'id': 'poznan', 'title': 'Rzeczy znalezione - Poznań', 'date': '2023-11-15', 'count': 10, 'status': 'Opublikowany'},
    {'id': 'warszawa', 'title': 'Rzeczy znalezione - Warszawa', 'date': '2023-11-12', 'count': 10, 'status': 'Opublikowany'},
    {'id': 'bydgoszcz', 'title': 'Rzeczy znalezione - Bydgoszcz', 'date': '2023-11-09', 'count': 10, 'status': 'Opublikowany'},
    {'id': 'wroclaw', 'title': 'Rzeczy znalezione - Wrocław', 'date': '2023-11-05', 'count': 10, 'status': 'Opublikowany'}
]

# Global storage for the most recently uploaded CSV items
uploaded_items = []

# Load official datasets after globals are declared
load_official_datasets()

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
        raw_bytes = file.stream.read()
        md5_checksum = hashlib.md5(raw_bytes).hexdigest()
        items, errors = parse_dataset_bytes(raw_bytes, file.filename)

        # Store parsed items for editing later
        uploaded_items.clear()
        uploaded_items.extend(items)
        
        return jsonify({
            'success': True,
            'items': items,
            'errors': errors,
            'count': len(items),
            'md5': md5_checksum
        })

@app.route('/urzad/publish', methods=['POST'])
def publish_dataset():
    data = request.json
    # Mock integration with dane.gov.pl API
    # In reality: requests.post('https://api.dane.gov.pl/datasets', json=data)
    
    dataset_title = data.get('title') or 'Nowy zbiór danych'
    dataset_id = _slugify(dataset_title)
    data_dir = os.path.join(os.path.dirname(__file__), 'datasets')
    os.makedirs(data_dir, exist_ok=True)

    # Persist items as JSON for download/export
    items_to_save = data.get('items', [])
    dataset_path = os.path.join(data_dir, f"{dataset_id}.json")
    try:
        with open(dataset_path, 'w', encoding='utf-8') as f:
            json.dump(items_to_save, f, ensure_ascii=False, indent=2)
        # refresh dataset_files entry
        dataset_files.insert(0, {'id': dataset_id, 'path': dataset_path})
        # update official search items in-memory
        official_items.extend(_build_official_items(items_to_save))
        _annotate_specific_items()
    except Exception as exc:
        print(f"Could not save dataset file: {exc}")

    new_dataset = {
        'id': dataset_id,
        'title': dataset_title,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'count': len(items_to_save),
        'status': 'Opublikowany'
    }
    datasets.insert(0, new_dataset) # Add to top of list
    
    print(f"PUBLISHING TO DANE.GOV.PL: {new_dataset}")
    
    return jsonify({'success': True, 'message': 'Zbiór danych został opublikowany w portalu dane.gov.pl'})

# Dataset downloads
@app.route('/urzad/download/dataset/<dataset_id>.json')
def download_dataset(dataset_id):
    file_path = _find_dataset_path(dataset_id)
    if file_path and os.path.isfile(file_path):
        items = _load_items_from_file(file_path)
    elif uploaded_items:
        # Fallback to in-memory uploaded items if not yet saved to disk
        items = uploaded_items
    else:
        abort(404)
    payload = json.dumps(items, ensure_ascii=False, indent=2)
    return Response(
        payload,
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename=\"{dataset_id}.json\"'}
    )


@app.route('/urzad/download/by_city.json')
def download_by_city():
    grouped = _dataset_items_by_city()
    payload = json.dumps(grouped, ensure_ascii=False, indent=2)
    return Response(
        payload,
        mimetype='application/json',
        headers={'Content-Disposition': 'attachment; filename=\"datasets_by_city.json\"'}
    )


@app.route('/urzad/download/all.json')
def download_all():
    items = _all_dataset_items()
    payload = json.dumps(items, ensure_ascii=False, indent=2)
    return Response(
        payload,
        mimetype='application/json',
        headers={'Content-Disposition': 'attachment; filename=\"datasets_all.json\"'}
    )

# JSON Schema exposure
@app.route('/schema.json')
def json_schema():
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "FoundItem",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "nazwa_przedmiotu": {"type": "string"},
            "kategoria": {"type": "string"},
            "data_znalezienia": {"type": "string", "format": "date"},
            "miejsce_znalezienia_miasto": {"type": "string"},
            "miejsce_znalezienia_ulica": {"type": "string"},
            "jednostka_przechowujaca": {"type": "string"},
            "kontakt_email": {"type": "string", "format": "email"},
            "status": {"type": "string", "enum": ["znaleziony", "nieznaleziony", "oddane"]},
            "opis_szczegolowy": {"type": "string"},
            "zdjecie_url": {"type": "string", "format": "uri"},
            "kontakt_telefon": {"type": "string"},
            "sygnatura_sprawy": {"type": "string"},
            "location_lat": {"type": "number"},
            "location_lng": {"type": "number"},
            "location_radius": {"type": "number"}
        },
        "required": FoundItemSchema.REQUIRED_FIELDS
    }
    return jsonify(schema)

# Route to display edit page for the uploaded CSV items
@app.route('/urzad/edit_csv')
def edit_csv():
    return render_template('official/edit_csv.html', items=uploaded_items)

# Route to receive edited items and update stored list
@app.route('/urzad/save_csv_edits', methods=['POST'])
def save_csv_edits():
    edited = request.json.get('items', [])
    formatted_items = []

    for item in edited:
        lat = item.get('location_lat') or ''
        lng = item.get('location_lng') or ''
        city = item.get('miejsce_znalezienia_miasto') or item.get('location_city') or ''
        street = item.get('miejsce_znalezienia_ulica') or item.get('location_street') or ''

        location_parts = []
        if lat and lng:
            location_parts.append(f"{lat}, {lng}")
        if city:
            location_parts.append(city)
        if street:
            location_parts.append(street)

        description = item.get('opis_szczegolowy') or item.get('opis') or item.get('description') or ''
        contact_raw = item.get('kontakt') or item.get('contact') or ''

        # Normalize core fields
        item['location'] = ", ".join(location_parts)
        item['miejsce_znalezienia_miasto'] = city
        item['miejsce_znalezienia_ulica'] = street
        item['opis_szczegolowy'] = description
        item['opis'] = description
        item['description'] = description
        item['kontakt'] = contact_raw
        item['contact'] = contact_raw
        if contact_raw and '@' in contact_raw and not item.get('kontakt_email'):
            item['kontakt_email'] = contact_raw
        if contact_raw and '@' not in contact_raw and not item.get('kontakt_telefon'):
            item['kontakt_telefon'] = contact_raw

        formatted_items.append(item)

    # Replace the global uploaded_items with edited data
    uploaded_items.clear()
    uploaded_items.extend(formatted_items)
    return jsonify({'success': True, 'message': 'Edits saved.'})

@app.route('/urzad/get_uploaded_items')
def get_uploaded_items():
    return jsonify({'items': uploaded_items})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
