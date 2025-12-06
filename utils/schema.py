import json
import csv
import io
from datetime import datetime

class FoundItemSchema:
    REQUIRED_FIELDS = [
        'nazwa_przedmiotu',
        'kategoria',
        'data_znalezienia',
        'miejsce_znalezienia_miasto',
        'miejsce_znalezienia_ulica',
        'jednostka_przechowujaca',
        'kontakt_email',
        'status'
    ]

    OPTIONAL_FIELDS = [
        'opis_szczegolowy',
        'zdjecie_url',
        'kontakt_telefon',
        'sygnatura_sprawy'
    ]

    @staticmethod
    def validate_row(row):
        errors = []
        for field in FoundItemSchema.REQUIRED_FIELDS:
            if not row.get(field):
                errors.append(f"Brak wymaganego pola: {field}")
        
        # Validate date format YYYY-MM-DD
        date_str = row.get('data_znalezienia')
        if date_str:
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                errors.append(f"Nieprawidłowy format daty: {date_str}. Wymagany: YYYY-MM-DD")

        return errors

    @staticmethod
    def parse_csv(file_stream):
        """
        Parses a CSV file stream and returns a list of items and a list of errors.
        """
        items = []
        errors = []
        
        try:
            # Decode stream to string
            stream = io.StringIO(file_stream.read().decode('utf-8'))
            reader = csv.DictReader(stream)
            
            # Normalize headers (lowercase, strip)
            if reader.fieldnames:
                reader.fieldnames = [h.strip().lower().replace(' ', '_') for h in reader.fieldnames]

            for i, row in enumerate(reader, start=1):
                row_errors = FoundItemSchema.validate_row(row)
                if row_errors:
                    errors.append({'row': i, 'errors': row_errors})
                else:
                    items.append(row)
                    
        except Exception as e:
            errors.append({'row': 0, 'errors': [f"Błąd parsowania CSV: {str(e)}"]})

        return items, errors

    @staticmethod
    def to_json(items):
        return json.dumps(items, ensure_ascii=False, indent=2)
