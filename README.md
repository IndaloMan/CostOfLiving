# Cost of Living Tracker

A personal finance web app that scans receipts and invoices using AI, stores the extracted data in a local database, and generates spending reports and charts to track the cost of living over time.

Built with Python, Flask, SQLite, and the Anthropic Claude API.

---

## Features

- **Scan receipts & invoices** — upload JPG, PNG or PDF files; Claude Vision extracts the company name, date, and all line items automatically
- **Review & confirm** — check and edit extracted data before it is saved; edit any confirmed receipt at any time
- **Company templates** — categories are learned from confirmed receipts and auto-applied to future scans from the same company
- **Reports & charts** — spending over time (month/quarter/year), by category, by company, and a price tracker for individual items
- **Company filter** — filter all reports to a single company or view all companies together
- **Company-specific analysis** — deep analysis for utility bills; currently implemented for Energy Nordic electricity bills (consumption per tariff period, energy price trends, bill component breakdown)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.13 |
| Web framework | Flask 3.1 |
| Database | SQLite via Flask-SQLAlchemy |
| AI / OCR | Anthropic Claude API (claude-sonnet-4-6) |
| Charts | Chart.js 4.4 |
| PDF parsing | pypdf |

---

## Project Structure

```
CostOfLiving/
├── app/
│   ├── __init__.py               # Flask app factory
│   ├── models.py                 # SQLAlchemy models
│   ├── routes.py                 # All Flask routes + API endpoints
│   ├── extractor.py              # Claude Vision receipt extractor
│   ├── template_manager.py       # Company template auto-categorisation
│   ├── reports_data.py           # Report data queries
│   ├── company_analysers/
│   │   ├── __init__.py           # Analyser registry + name normalisation
│   │   └── energy_nordic.py      # Energy Nordic electricity bill analyser
│   ├── templates/                # Jinja2 HTML templates
│   └── static/                   # CSS and JavaScript
├── Receipts/                     # Uploaded receipt files (not committed)
├── config.py                     # App configuration
├── run.py                        # Entry point
├── requirements.txt
└── .env                          # API key (not committed)
```

---

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/IndaloMan/CostOfLiving.git
cd CostOfLiving
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Add your Anthropic API key

Create a `.env` file in the project root:
```
ANTHROPIC_API_KEY=your_api_key_here
```

Get an API key from [console.anthropic.com](https://console.anthropic.com).

### 4. Run the app
```bash
python run.py
```

Open **http://127.0.0.1:5000** in your browser.

---

## Usage

### Scanning a receipt
1. Go to **Scan** and upload a receipt image or PDF
2. Claude extracts the company, date, and all line items
3. Review and correct anything on the Review page
4. Click **Confirm & Save** — data is stored and the company template is updated

### Reports
- Go to **Reports** to see spending charts
- Use the **Company** dropdown to filter by a specific company
- Use the **Price Tracker** to search for any item and see its price trend over time

### Energy Nordic analysis
- Go to **Companies → ⚡ Analysis** for a detailed breakdown of electricity bills
- Tracks consumption per tariff period (P1/P2/P3), energy prices, and bill components
- Analysis runs automatically when a new Energy Nordic bill is confirmed

---

## Adding a new company analyser

1. Create `app/company_analysers/your_company.py` with an `analyse(filepath)` function
2. Register it in `app/company_analysers/__init__.py`:
   ```python
   ANALYSER_MAP = {
       "your company name": "your_company",
   }
   ```
3. The analyser will run automatically on confirm for that company

---

## Security notes

- The `.env` file (API key) is excluded from git
- The `database.db` file (personal financial data) is excluded from git
- The `Receipts/` folder (uploaded documents) is excluded from git
- This app is intended for local use only — do not deploy to a public server without adding authentication
