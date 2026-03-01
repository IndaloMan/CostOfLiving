"""
Quick test: drop a receipt image or PDF into the Receipts folder,
then run:  python test_extractor.py Receipts/your_file.jpg
"""
import sys
import json
from app.extractor import extract_from_file, ExtractionError

if len(sys.argv) < 2:
    print("Usage: python test_extractor.py <path_to_receipt>")
    print("Example: python test_extractor.py Receipts/mercadona.jpg")
    sys.exit(1)

filepath = sys.argv[1]
print(f"\nExtracting: {filepath}\n")

try:
    result = extract_from_file(filepath)
    print(json.dumps(result, indent=2, ensure_ascii=False))
except ExtractionError as e:
    print(f"Extraction failed: {e}")
except FileNotFoundError:
    print(f"File not found: {filepath}")
