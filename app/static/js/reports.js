/* Reports page — Chart.js charts powered by the /api/* endpoints */

const COLORS = [
    '#2980b9','#27ae60','#e67e22','#e74c3c','#9b59b6',
    '#1abc9c','#f39c12','#34495e','#16a085','#c0392b',
    '#2ecc71','#3498db','#d35400','#8e44ad','#95a5a6',
];

let timeChart     = null;
let categoryChart = null;
let companyChart  = null;

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

function getFilters() {
    return {
        start:     document.getElementById('startDate').value,
        end:       document.getElementById('endDate').value,
        groupBy:   document.getElementById('groupBy').value,
        companyId: document.getElementById('companyFilter').value,
    };
}

function qs(params) {
    return Object.entries(params)
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
        .join('&');
}

function fmt(n) {
    return '€' + Number(n).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function destroyChart(chart) {
    if (chart) chart.destroy();
    return null;
}

// ---------------------------------------------------------------------------
// Summary cards
// ---------------------------------------------------------------------------

async function loadSummary(start, end, companyId) {
    const data = await fetchJSON(`/api/summary?${qs({ start, end, company_id: companyId })}`);
    document.getElementById('statTotal').querySelector('.stat-num').textContent = fmt(data.total_spent);
    document.getElementById('statCount').querySelector('.stat-num').textContent = data.receipt_count;
    document.getElementById('statAvg').querySelector('.stat-num').textContent   = fmt(data.avg_per_receipt);
    document.getElementById('statTop').querySelector('.stat-num').textContent   = data.top_category;
}

// ---------------------------------------------------------------------------
// Spending over time — bar chart
// ---------------------------------------------------------------------------

async function loadTimeChart(start, end, groupBy, companyId) {
    const data = await fetchJSON(`/api/spending-over-time?${qs({ start, end, group_by: groupBy, company_id: companyId })}`);
    const empty = document.getElementById('timeEmpty');
    timeChart = destroyChart(timeChart);

    if (!data.labels.length) {
        empty.style.display = 'block';
        return;
    }
    empty.style.display = 'none';

    const ctx = document.getElementById('timeChart').getContext('2d');
    timeChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.labels,
            datasets: [{
                label: 'Total Spent (€)',
                data: data.values,
                backgroundColor: COLORS[0],
                borderRadius: 4,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, ticks: { callback: v => '€' + v } },
            },
        },
    });
}

// ---------------------------------------------------------------------------
// By category — doughnut chart
// ---------------------------------------------------------------------------

async function loadCategoryChart(start, end, companyId) {
    const data = await fetchJSON(`/api/by-category?${qs({ start, end, company_id: companyId })}`);
    const empty = document.getElementById('categoryEmpty');
    categoryChart = destroyChart(categoryChart);

    if (!data.labels.length) {
        empty.style.display = 'block';
        return;
    }
    empty.style.display = 'none';

    const ctx = document.getElementById('categoryChart').getContext('2d');
    categoryChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: data.labels,
            datasets: [{
                data: data.values,
                backgroundColor: COLORS.slice(0, data.labels.length),
                borderWidth: 2,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'right', labels: { boxWidth: 12, font: { size: 11 } } },
                tooltip: {
                    callbacks: {
                        label: ctx => ` ${ctx.label}: ${fmt(ctx.parsed)}`,
                    },
                },
            },
        },
    });
}

// ---------------------------------------------------------------------------
// By company — horizontal bar chart
// ---------------------------------------------------------------------------

async function loadCompanyChart(start, end, companyId) {
    const data = await fetchJSON(`/api/by-company?${qs({ start, end, company_id: companyId })}`);
    const empty = document.getElementById('companyEmpty');
    companyChart = destroyChart(companyChart);

    if (!data.labels.length) {
        empty.style.display = 'block';
        return;
    }
    empty.style.display = 'none';

    // Show highest at top
    const labels = [...data.labels].reverse();
    const values = [...data.values].reverse();

    const ctx = document.getElementById('companyChart').getContext('2d');
    companyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: COLORS[1],
                borderRadius: 4,
            }],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { beginAtZero: true, ticks: { callback: v => '€' + v } },
            },
        },
    });
}

// ---------------------------------------------------------------------------
// Load all charts
// ---------------------------------------------------------------------------

async function loadAll() {
    if (!window.validateDateRange()) return;
    const { start, end, groupBy, companyId } = getFilters();
    localStorage.setItem('filter_reports_start', start);
    localStorage.setItem('filter_reports_end',   end);
    try {
        await Promise.all([
            loadSummary(start, end, companyId),
            loadTimeChart(start, end, groupBy, companyId),
            loadCategoryChart(start, end, companyId),
            loadCompanyChart(start, end, companyId),
        ]);
    } catch (err) {
        console.error('Chart load error:', err);
    }
}

// ---------------------------------------------------------------------------
// Initialise — restore saved dates or default to last 12 months
// ---------------------------------------------------------------------------

window.addEventListener('DOMContentLoaded', () => {
    const today    = new Date();
    const todayStr = today.toISOString().split('T')[0];
    const defStart = new Date(today);
    defStart.setFullYear(defStart.getFullYear() - 1);

    const startEl = document.getElementById('startDate');
    const endEl   = document.getElementById('endDate');
    endEl.value   = localStorage.getItem('filter_reports_end')   || todayStr;
    startEl.value = localStorage.getItem('filter_reports_start') || defStart.toISOString().split('T')[0];

    // Save immediately when either date input changes (even without clicking Apply)
    startEl.addEventListener('change', function () { localStorage.setItem('filter_reports_start', this.value); });
    endEl.addEventListener('change',   function () { localStorage.setItem('filter_reports_end',   this.value); });

    loadAll();

});

// ---------------------------------------------------------------------------
// Item Analysis table
// ---------------------------------------------------------------------------

async function loadItemAnalysis() {
    const start     = document.getElementById('startDate').value;
    const end       = document.getElementById('endDate').value;
    const companyId = document.getElementById('companyFilter').value;
    const wrap      = document.getElementById('iaTableWrap');

    // Update date label
    const labelEl = document.getElementById('iaDateLabel');
    if (labelEl && start && end) {
        const s    = new Date(start), e = new Date(end);
        const days = Math.round((e - s) / (1000 * 60 * 60 * 24));
        const fmt  = d => d.toLocaleDateString('en-GB', { day:'2-digit', month:'short', year:'numeric' });
        labelEl.textContent = `${fmt(s)} — ${fmt(e)}  (${days} days)`;
    }
    const empty     = document.getElementById('iaEmpty');
    const loading   = document.getElementById('iaLoading');
    const tbody     = document.getElementById('iaBody');

    wrap.style.display    = 'none';
    empty.style.display   = 'none';
    loading.style.display = 'block';

    const params = { start, end };
    if (companyId) params.company_id = companyId;

    try {
        const data = await fetchJSON(`/api/item-analysis?${qs(params)}`);
        loading.style.display = 'none';

        if (!data.length) {
            empty.style.display = 'block';
            return;
        }

        const hideZero = document.getElementById('iaHideZero') && document.getElementById('iaHideZero').checked;
        const filtered = hideZero ? data.filter(row => row.pct_diff == null || row.pct_diff !== 0) : data;

        if (!filtered.length) {
            empty.style.display = 'block';
            return;
        }

        tbody.innerHTML = '';
        filtered.forEach(row => {
            const tr = document.createElement('tr');
            let pctHtml = '—';
            if (row.pct_diff != null) {
                const sign  = row.pct_diff >= 0 ? '+' : '';
                const color = row.pct_diff > 0 ? '#c0392b' : '#27ae60';
                pctHtml = `<span style="color:${color};font-weight:600">${sign}${row.pct_diff.toFixed(1)}%</span>`;
            }
            tr.innerHTML = `
                <td style="padding-right:0.5rem"><a href="/items/search?q=${encodeURIComponent(row.description)}${(()=>{const c=document.getElementById("companyFilter").value;return c?"&company_id="+c:"";})()}" target="_blank" style="color:inherit;text-decoration:none;border-bottom:1px dashed #aaa;">${row.description}</a></td>
                <td style="text-align:center;padding-right:0.5rem">${row.qty}</td>
                <td style="text-align:right;padding-right:0.5rem">${row.price_low  != null ? '€' + row.price_low.toFixed(2)  : '—'}</td>
                <td style="text-align:right;padding-right:0.5rem">${row.price_high != null ? '€' + row.price_high.toFixed(2) : '—'}</td>
                <td style="text-align:right;padding-right:0.5rem">${pctHtml}</td>
                <td>${row.category}</td>
            `;
            tbody.appendChild(tr);
        });

        wrap.style.display = 'block';
        initTableSort(document.getElementById('iaTable'));
    } catch (err) {
        loading.style.display = 'none';
        console.error('Item analysis error:', err);
    }
}

function initTableSort(table) {
    let sortCol = null, sortAsc = true;
    table.querySelectorAll('th.sortable').forEach(th => {
        th.style.cursor = 'pointer';
        th.onclick = () => {
            const col = parseInt(th.dataset.col);
            sortAsc = (sortCol === col) ? !sortAsc : true;
            sortCol = col;
            const tbody = table.querySelector('tbody');
            const rows  = Array.from(tbody.querySelectorAll('tr'));
            rows.sort((a, b) => {
                const av = a.cells[col] ? a.cells[col].textContent.replace(/[€,]/g, '').trim() : '';
                const bv = b.cells[col] ? b.cells[col].textContent.replace(/[€,]/g, '').trim() : '';
                const an = parseFloat(av), bn = parseFloat(bv);
                const cmp = (!isNaN(an) && !isNaN(bn)) ? an - bn : av.localeCompare(bv);
                return sortAsc ? cmp : -cmp;
            });
            rows.forEach(r => tbody.appendChild(r));
            table.querySelectorAll('th.sortable .sort-icon').forEach(ic => ic.textContent = '');
            th.querySelector('.sort-icon').textContent = sortAsc ? ' ▲' : ' ▼';
        };
    });
}

