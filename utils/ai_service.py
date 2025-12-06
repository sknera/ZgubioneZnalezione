import time
import random

def analyze_image(file_obj):
    """
    Simulates AI analysis of an image.
    Returns a dictionary with mock data.
    """
    # Simulate processing time
    time.sleep(1.5)
    
    # Mock data choices
    categories = ["Electronics", "Clothing", "Accessories", "Documents", "Keys"]
    colors = ["Czarny", "Niebieski", "Czerwony", "Biały", "Srebrny", "Brązowy"]
    conditions = ["Nowy", "Używany", "Uszkodzony", "Dobry"]
    
    # Deterministic-ish mock based on filename length to give varied but consistent results for same file
    seed = len(file_obj.filename)
    random.seed(seed)
    
    detected_category = random.choice(categories)
    detected_color = random.choice(colors)
    detected_condition = random.choice(conditions)
    
    return {
        "success": True,
        "data": {
            "name": f"{detected_color} {detected_category}",
            "category": detected_category,
            "description": f"Znaleziono: {detected_color.lower()} {detected_category.lower()}. Stan: {detected_condition.lower()}.",
            "location": "Główny Hol", # Default mock location
            "date": "2023-10-27" # Default mock date
        }
    }
