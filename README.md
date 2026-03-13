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
- **Company types & categories** — assign a type (Supermarket, Petrol, Utility, etc.) to each company; manage company types and categories from the **Settings** page without touching code
- **Grouped receipts** — toggle between flat list and Group by Company view; groups start collapsed showing name/count/total; expanded state and view preference persist across page loads and receipt edits
- **Receipt modified timestamp** — receipts table shows the date and time of the last edit in a Modified column
- **Reports & charts** — spending over time (month/quarter/year), by category and by company
- **Price Tracker** — dedicated full-page view accessible from the nav; search any item to see its price trend with % change vs previous price shown in the hover tooltip
- **Company filter** — filter all reports to a single company or view all companies together
- **Persistent date filters** — each analysis page (Reports, Mercadona, Energy Nordic) remembers the last date range you used; saved immediately when dates are changed
- **Save indicator** — a spinner and message appear while a receipt is being confirmed, since AI analysis can take several seconds
- **Company-specific analysis** — deep analysis for utility bills; currently implemented for Energy Nordic electricity bills (consumption per tariff period, energy price trends, bill component breakdown, per-period avg €/kWh stats)
- **Mercadona shopping analysis** — spend per visit, category breakdown, and top items by spend
- **Item Analysis** — on the Reports page; shows all supermarket items with qty (number of receipts), price low/high, % price change, and category; sortable columns; uses the same date/company filters as the charts above
- **Column sorting** — Bill Breakdown table on the Energy Nordic analysis page is fully sortable by any column
- **Google Translate** — widget in the nav bar translates the entire UI to English; useful for Spanish supermarket item names
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
- Date range is remembered between visits

### Price Tracker
- Available from the **Price Tracker** link in the nav bar
- Type any item name (autocomplete suggestions appear after 2 characters) and click **Track Item**
- Chart fills the full page; hover tooltip shows price and % change vs the previous data point

### Energy Nordic analysis
- Go to **Companies → ⚡ Analysis** for a detailed breakdown of electricity bills
- Tracks consumption per tariff period (P1/P2/P3), energy prices, and bill components
- Shows overall and per-period average €/kWh (energy costs only, excluding standing charges)
- Analysis runs automatically when a new Energy Nordic bill is confirmed
- Date filter is remembered between visits

### Mercadona shopping analysis
- Go to **Companies → 🛒 Analysis** for shopping trends
- Spend per visit, category breakdown, and top items by total spend

### Managing companies
- Go to **Companies** to see all companies with receipt counts and template sizes
- Click **Edit Template** to set the company type and manage known line item descriptions
- Keep template descriptions short and stable (e.g. `Energy P1` not the full line with kWh values) so they match future receipts with different figures
- The **Group by Company** toggle on the Receipts page collapses the list into expandable company sections; expanded state is remembered

### Settings
- Go to **Settings** to manage the Company Types and Categories dropdown lists
- Add, rename or delete any value without touching code
- Renaming cascades automatically to existing receipts, line items and company templates
- Deleting a category clears it from existing line items; deleting a company type clears it from existing companies

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

---

## Release Notes

### v1.35 — 13 March 2026
- **Item Analysis click-to-search fix** — Item Search page now reads the q= URL param on load, populates the description box and auto-runs the search

### v1.34 — 13 March 2026
- **Item Analysis clickable descriptions** — clicking a description in the Item Analysis table opens Item Search pre-filtered to that item in a new tab

### v1.33 — 13 March 2026
- **Self-registration** — new /register page lets anyone create an account; generates a unique anon-NNNNNN login ID and a memorable two-word passphrase; users can optionally set a custom password, email, gender and age range
- **Anonymous login IDs** — login now accepts anon-NNNNNN login IDs as well as email addresses; Shopper model gains login_id, gender and age_range columns; email and full name are now optional
- **Account self-deletion** — non-admin users can deactivate their own account from the Change Password page (GDPR Article 17 soft-delete); confirms by typing nickname
- **Shopper edit improvements** — gender and age range dropdowns added to add/edit shopper form; email and full name now optional
- **Item Analysis — hide zero % diff** — checkbox on Reports page to filter out items with no price change

### v1.32 — 11 March 2026
- **Item Search** — admin-only page to search line items across all receipts; blank search finds items with no description; results show company, date, qty, unit price, total, category, and a link to the receipt; sortable columns
- **Weighed items extraction** — extraction prompt now correctly handles supermarket weighed items (e.g. "0,362 kg  2,50 €/kg  0,91"), extracting weight as qty and price-per-kg as unit_price

### v1.31 — 11 March 2026
- **Generic company analysis** — every company now has an Analysis page showing spend per visit, by category, top items, and price tracker with % change tooltip; works for all current and future companies
- **Price tracker on analysis page** — item search with autocomplete filtered to that company, uses the same date range as the other charts
- **Mercadona duplicate button removed** — generic Analysis replaces it; Energy Nordic keeps its specialist button
- **YTD/date preset timezone fix** — date presets (Month, Qtr, YTD, Prev Yr) now use local date instead of UTC, fixing off-by-one day for Spain (UTC+1)
- **Timestamps use local time** — all created_at/updated_at now store local time instead of UTC, fixing Modified column showing 1 hour behind
- **Unit price fix for qty=1** — extraction prompt now sets unit_price = total_price when qty is 1 and no unit price is printed on the receipt

### v1.30 — 11 March 2026
- **Company alias** — admin can set a display name for each company (e.g. "Iceland" for "Overseas - Vera"), shown on receipts, reports, and all views while preserving the original extracted name for matching

### v1.29 — 11 March 2026
- app/templates/quick_scan.html

### v1.28 — 11 March 2026
- app/templates/review.html

### v1.27 — 11 March 2026
- app/templates/review.html

### v1.26 — 11 March 2026
- app/extractor.py

### v1.25 — 11 March 2026
- app/templates/review.html

### v1.24 — 11 March 2026
- app/templates/quick_scan.html

### v1.23 — 11 March 2026
- **Quick Scan redesign** — two separate buttons (Take Photo / Upload Image) replace the single ambiguous button; buttons stack vertically in portrait mode; Extract Data hidden until file selected

### v1.22 — 11 March 2026
- app/static/502.html, app/templates/login.html

### v1.21 — 11 March 2026
- **Change password** — all logged-in users can change their own password via nav Password link
- **Admin password reset** — admin can reset any shopper's password from the shopper edit page
- **Show/hide password toggle** — eye icon on all password fields across login, change password and shopper pages
- **YYYYMMDDHHMMSS filenames** — uploaded receipt files saved with timestamp filename instead of original camera filename
- **Custom 502 error page** — friendly "Server temporarily unavailable" page shown when Flask is down instead of raw nginx error

### v1.20 — 11 March 2026
- app/templates/quick_scan.html

### v1.19 — 11 March 2026
- app/routes.py

### v1.18 — 11 March 2026
- see commit

### v1.17 — 11 March 2026
- see commit

### v1.16 — 11 March 2026
- **Quick Scan page** — new minimal mobile-friendly `/quick-scan` page with a large camera button; non-admin Scan nav link and Scan Now card point here automatically
- **Mobile camera capture** — file input on scan pages uses `capture="environment"` so mobile browsers open the camera directly
- **Quick Confirm button** — full-width confirm button added at the top of the Review page for one-tap confirmation without scrolling

### v1.15 — 11 March 2026
- **Multi-shopper support** — Shoppers table (email, full name, nickname, password, admin flag, active flag); each receipt is owned by the shopper who uploaded it
- **Authentication** — flask-login session-based login/logout; all routes protected; stable SECRET_KEY via .env
- **Admin controls** — admin sees all shoppers data; View As dropdown lets admin switch to any shopper's view; Shoppers management page (add, edit, activate/deactivate)
- **Per-shopper data filtering** — receipts list, dashboard counts, companies page, reports & charts, price tracker all filtered to current shopper's own data
- **Non-admin nav** — simplified to Expenditure, Scan, Reports; Settings, Income, Accounts, Transactions, Shoppers restricted to admin only
- **App logging** — login/logout (with IP), upload, confirm, delete and shopper changes logged to console and rotating app.log

### v1.14 — 11 March 2026
- Add extra_head block to base template

### v1.13 — 10 March 2026
- **Date presets on filter pages** — Month, Qtr, YTD and Prev Yr buttons on Reports, Mercadona Analysis, Energy Nordic Analysis and Income Reports; clicking auto-applies the date range
- **Clickable stat boxes on Expenditure dashboard** — Receipts Saved links to /receipts, Companies links to /companies

### v1.12 — 10 March 2026
- app/__init__.py, app/models.py, app/reports_data.py, app/routes.py, app/statement_parsers/__init__.py, app/statement_parsers/sabadell_pdf.py, app/statement_parsers/wise_csv.py, app/static/js/analysis_mercadona.js, app/templates/accounts.html, app/templates/accounts_edit.html, app/templates/base.html, app/templates/import_preview.html, app/templates/import_statement.html, app/templates/income.html, app/templates/income_dashboard.html, app/templates/income_edit.html, app/templates/income_reports.html, app/templates/index.html, app/templates/review.html, app/templates/settings.html, app/templates/transaction_edit.html, app/templates/transactions.html

### v1.11 — 6 March 2026
- see commit

### v1.10 — 6 March 2026
- app/static/css/style.css, app/templates/base.html, app/templates/company_detail.html, app/templates/receipts.html, app/templates/review.html, app/templates/settings.html

### v1.10 — 6 March 2026
- **Sortable columns everywhere** — Known Items (company detail), Receipts flat list, and Settings categories tables all support click-to-sort on any column
- **Receipts grouped view fix** — editing then cancelling a receipt now correctly returns to the grouped view
- **Receipts table polish** — Date, Type and File columns no longer wrap; EUR replaced with € symbol
- **Remove Google Translate** — widget removed from nav bar

### v1.9 — 6 March 2026
- **Settings sortable columns** — Category and Rename columns in Settings are sortable
- **Receipts sort and polish** — all flat-list columns sortable; nowrap on Date/Type/File; € symbol

### v1.8 — 6 March 2026
- **Item Analysis table** — new section on the Reports page showing supermarket items with qty, price low/high, % price diff (red/green), and category; groups by description only; sortable columns
- **Date range label** — displays the active from/to dates and number of days above the Item Analysis table
- **Analyse on demand** — Item Analysis loads only when the Analyse button is clicked, using the top-level filter dates and company
- **Energy Nordic column sorting** — all columns in the Bill Breakdown table are now sortable with ▲/▼ indicators
- **Price Tracker removed from Mercadona page** — use the dedicated Price Tracker page instead

### v1.7 — 6 March 2026
- **Prompt caching** — extraction system prompt now uses Anthropic ephemeral caching (1h TTL) to reduce API costs on repeated scans; template hints moved to a separate helper and only appended when present

### v1.6 — 6 March 2026
- **Price Tracker full page** — moved from a Dashboard card to a dedicated /price-tracker route with its own nav link; chart fills the available screen height
- **Hover % change** — Price Tracker tooltip now shows price and % change vs the previous data point
- **Google Translate widget** — added to the nav bar on all pages; translates ES→EN with one click; preference persists via cookie
- **Dashboard card simplified** — Price Tracker card on the Dashboard replaced with an Open Price Tracker button

### v1.5 — 3 March 2026
- **Twitter/X upload support** — social upload triggers added to daily, weekly and monthly jobs
- **Persistent date filters** — Reports, Mercadona and Energy Nordic pages save date filters to localStorage on change (not just on Apply)

### v1.4 — 3 March 2026
- **Mobile navigation** — hamburger menu added for screens 768px and below; nav links collapse into a dropdown
- **Responsive layout improvements** — stats row, filters, charts and tables optimised for mobile

### v1.3 — 3 March 2026
- **Date range validation** — all screens with date filters now show an inline error if From is after To instead of failing silently
- **Date picker restricted to relevant years** — pickers no longer show future years; range limited to today and 4 years back
- **Shared date filter logic** — validation and date picker constraints live once in `base.html` and apply automatically to all company analysis pages past and future; no per-page duplication

### v1.2 — 3 March 2026
- **Utility bill description fix** — Claude now extracts only the stable charge name into the description field (e.g. `Energy P1`, `Contracted Power P1`, `Meter Hire`) rather than embedding quantities and rates; variable data is placed in qty and unit_price where it belongs, so company templates match correctly across bills
- **Cancel button on review screen** — new Cancel button on the Review Extracted Data page discards the pending receipt and its uploaded file and returns to the Receipts list

### v1.1 — 2 March 2026
- **Settings page** — add, rename and delete Company Types and Categories from the UI; renames cascade to all existing receipts, line items and templates
- **Price Tracker moved to Dashboard** — removed from Reports page; now a self-contained card on the Dashboard with a Track Item button
- **Grouped receipts improvements** — groups start collapsed (name/count/total visible); expanded state persists in localStorage; view preference (grouped/flat) survives receipt edits
- **Modified column** — receipts tables show date and time of last edit; `updated_at` column added via automatic DB migration on startup
- **Save indicator** — spinner + "Saving… this may take a few seconds" shown while confirm is processing
- **Date filter persistence fix** — date inputs now save to localStorage on change, not only on Apply click
- **Quantity formatting** — whole-number quantities no longer show `.0` (28.0 → 28)

### v1.0 — February 2026
- Initial release
- Receipt scanning via Claude Vision (single and batch upload)
- Review, edit and confirm workflow; company templates with auto-categorisation
- Flat and grouped receipts views; pending queue with Process All
- Reports & Charts — spending over time, by category, by company
- Company-specific deep analysis — Energy Nordic electricity bills, Mercadona shopping
- Mobile-responsive UI; HTTPS via Tailscale
