# Cost of Living Tracker

A personal finance web app that scans receipts and invoices using AI, stores the extracted data in a local database, and generates spending reports and charts to track the cost of living over time.

Built with Python, Flask, SQLite, and the Anthropic Claude API.

---

## Features

- **Scan receipts & invoices** — upload JPG, PNG or PDF files; Claude Vision extracts the company name, date, and all line items automatically
- **Batch upload** — upload multiple files at once; duplicate detection skips already-imported files; results table shows company, date and total with a Review link per file
- **Pending queue** — unreviewed uploads appear in an orange Pending section on the Receipts page; **Process All** confirms the whole batch without individual review (runs company analysis automatically)
- **Review & confirm** — check and edit extracted data before it is saved; edit any confirmed receipt at any time; click the filename to open the original PDF in a new tab
- **Company templates** — categories are learned from confirmed receipts and auto-applied to future scans from the same company; template descriptions use prefix matching so short stable strings (e.g. `Energy P1`) match any bill regardless of variable values
- **Company types** — assign a type (Supermarket, Petrol, Utility, etc.) to each company via the Companies page
- **Grouped receipts** — toggle between flat list and Group by Company view with collapsible sections showing receipt count and total per company
- **Reports & charts** — spending over time (month/quarter/year), by category, by company, and a price tracker for individual items
- **Company filter** — filter all reports to a single company or view all companies together
- **Persistent date filters** — each analysis page (Reports, Mercadona, Energy Nordic) remembers the last date range you used via browser localStorage
- **Company-specific analysis** — deep analysis for utility bills; currently implemented for Energy Nordic electricity bills (consumption per tariff period, energy price trends, bill component breakdown, per-period avg €/kWh stats)
- **Mercadona shopping analysis** — spend per visit, category breakdown, top items, and price tracker with item autocomplete
- **Mobile responsive** — hamburger nav, stacked stats and full-width charts on screens 768px and below; access securely from anywhere via Tailscale HTTPS

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
│   │   ├── scan_batch.html       # Batch upload + results
│   │   └── ...                   # Other templates
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

### 5. Optional — HTTPS via Tailscale

To access the app securely from any device (including mobile):

1. Install [Tailscale](https://tailscale.com) on your PC and phone, sign in with the same account
2. Enable HTTPS in the [Tailscale admin DNS settings](https://login.tailscale.com/admin/dns)
3. Generate a certificate (run as Administrator):
   ```powershell
   tailscale cert your-machine-name.your-tailnet.ts.net
   ```
4. Place the `.crt` and `.key` files in the project root — `run.py` detects them automatically and starts in HTTPS mode

---

## Usage

### Scanning a single receipt
1. Go to **Scan** and upload a receipt image or PDF
2. Claude extracts the company, date, and all line items
3. Review and correct anything on the Review page (click the filename to view the original)
4. Click **Confirm & Save** — data is stored and the company template is updated

### Batch upload
1. Go to **Scan → Batch Upload** and drag in multiple files (or use the file chooser)
2. All files are extracted in one go — already-uploaded files are detected and skipped
3. The results table shows a **Review** button for each new file
4. Alternatively, go to **Receipts** and click **Process All** to confirm everything at once without reviewing

### Reports
- Go to **Reports** to see spending charts
- Use the **Company** dropdown to filter by a specific company
- Use the **Price Tracker** to search for any item and see its price trend over time
- Date range is remembered between visits

### Energy Nordic analysis
- Go to **Companies → ⚡ Analysis** for a detailed breakdown of electricity bills
- Tracks consumption per tariff period (P1/P2/P3), energy prices, and bill components
- Shows overall and per-period average €/kWh (energy costs only, excluding standing charges)
- Analysis runs automatically when a new Energy Nordic bill is confirmed
- Date filter is remembered between visits

### Mercadona shopping analysis
- Go to **Companies → 🛒 Analysis** for shopping trends
- Spend per visit, category breakdown, top items by total spend, and an item price tracker
- Type the first few characters of any item in the Price Tracker to search by autocomplete

### Managing companies
- Go to **Companies** to see all companies with receipt counts and template sizes
- Click **Edit Template** to set the company type and manage known line item descriptions
- Keep template descriptions short and stable (e.g. `Energy P1` not the full line with kWh values) so they match future receipts with different figures
- The **Group by Company** toggle on the Receipts page collapses the list into expandable company sections

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
