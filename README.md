# ZgubioneZnalezione

Portal zgłoszeń i wyszukiwania rzeczy znalezionych z widokiem obywatelskim oraz strefą urzędnika (import/edycja/publikacja zbiorów danych).

## Uruchomienie lokalne
1) Wymagania: Python 3.10+, pip, virtualenv (opcjonalnie).
2) Zainstaluj zależności:
```bash
pip install -r requirements.txt
```
3) Uruchom aplikację (dev):
```bash
python app.py
```
   Aplikacja startuje domyślnie na `http://127.0.0.1:5000`.

## Widok Obywatela
- Formularz zgłoszenia z podglądem zdjęcia i domyślną kategorią „Dokumenty”.
- Automatyczne wypełnianie pól po analizie zdjęcia.
- Wyszukiwarka z filtrem kategorii, daty, lokalizacji i rysowaniem koła na mapie; wyniki z wszystkich miast (dane oficjalne + zgłoszenia).
- Weryfikacja roszczeń pytaniem kontrolnym (widoczne w karcie i w modalu).

## Strefa Urzędnika
- Import plików CSV/JSON/JSONL, edycja tabelaryczna (w tym współrzędne, opis, kontakt).
- Publikacja zbiorów (zapis do `datasets/`) i automatyczne przyciski pobrań JSON: per zbiór, per miasto, wszystkie dane.
- Dostępny JSON Schema pod `GET /schema.json`.

## Dane przykładowe
- `sample_data.csv` oraz `sample_data.json` zgodne ze schematem; 
