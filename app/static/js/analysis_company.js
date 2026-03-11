/* Generic company analysis charts + price tracker */

const COLORS = [
    '#2980b9','#27ae60','#e67e22','#e74c3c','#9b59b6',
    '#1abc9c','#f39c12','#34495e','#16a085','#c0392b',
    '#2ecc71','#3498db','#d35400','#8e44ad','#95a5a6',
];

let visitChart    = null;
let categoryChart = null;
let topItemsChart = null;
let priceChart    = null;
let suggestTimer  = null;

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error('API error ' + res.status);
    return res.json();
}

function getFilters() {
    return {
        start: document.getElementById('startDate').value,
        end:   document.getElementById('endDate').value,
    };
}

function qs(params) {
    return Object.entries(params)
        .map(([k, v]) => encodeURIComponent(k) + '=' + encodeURIComponent(v))
        .join('&');
}

function fmt(n) {
    return '\u20ac' + Number(n).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function destroy(chart) { if (chart) chart.destroy(); return null; }

// ---------------------------------------------------------------------------
// Summary stats
// ---------------------------------------------------------------------------

async function loadSummary(start, end) {
    const d = await fetchJSON('/api/summary?' + qs({ start, end, company_id: COMPANY_ID }));
    document.getElementById('statVisits').textContent  = d.receipt_count;
    document.getElementById('statTotal').textContent   = fmt(d.total_spent);
    document.getElementById('statAvg').textContent     = fmt(d.avg_per_receipt);
    document.getElementById('statTopCat').textContent  = d.top_category;
}

// ---------------------------------------------------------------------------
// Spend per visit
// ---------------------------------------------------------------------------

async function loadVisitChart(start, end) {
    const data = await fetchJSON('/api/company/' + COMPANY_ID + '/per-visit?' + qs({ start, end }));
    const empty = document.getElementById('visitEmpty');
    visitChart = destroy(visitChart);

    if (!data.labels.length) { empty.style.display = 'block'; return; }
    empty.style.display = 'none';

    const ctx = document.getElementById('visitChart').getContext('2d');
    visitChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [{
                label: 'Total (EUR)',
                data: data.values,
                borderColor: COLORS[0],
                backgroundColor: COLORS[0] + '22',
                pointRadius: 5,
                pointHoverRadius: 7,
                tension: 0.2,
                fill: true,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true, ticks: { callback: v => '\u20ac' + v } } },
        },
    });
}

// ---------------------------------------------------------------------------
// By category
// ---------------------------------------------------------------------------

async function loadCategoryChart(start, end) {
    const data = await fetchJSON('/api/by-category?' + qs({ start, end, company_id: COMPANY_ID }));
    const empty = document.getElementById('categoryEmpty');
    categoryChart = destroy(categoryChart);

    if (!data.labels.length) { empty.style.display = 'block'; return; }
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
                tooltip: { callbacks: { label: ctx => ' ' + ctx.label + ': ' + fmt(ctx.parsed) } },
            },
        },
    });
}

// ---------------------------------------------------------------------------
// Top items
// ---------------------------------------------------------------------------

async function loadTopItemsChart(start, end) {
    const data = await fetchJSON('/api/company/' + COMPANY_ID + '/top-items?' + qs({ start, end }));
    const empty = document.getElementById('topItemsEmpty');
    topItemsChart = destroy(topItemsChart);

    if (!data.labels.length) { empty.style.display = 'block'; return; }
    empty.style.display = 'none';

    const labels = [...data.labels].reverse();
    const values = [...data.total_spent].reverse();
    const counts = [...data.purchase_count].reverse();

    const canvas = document.getElementById('topItemsChart');
    canvas.parentElement.style.height = Math.max(280, labels.length * 32) + 'px';
    const ctx = canvas.getContext('2d');
    topItemsChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Total Spent (EUR)',
                data: values,
                backgroundColor: COLORS[1],
                borderRadius: 4,
            }],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label:      ctx => ' ' + fmt(ctx.parsed.x),
                        afterLabel: ctx => ' ' + counts[ctx.dataIndex] + ' purchase(s)',
                    },
                },
            },
            scales: { x: { beginAtZero: true, ticks: { callback: v => '\u20ac' + v } } },
        },
    });
}

// ---------------------------------------------------------------------------
// Price tracker
// ---------------------------------------------------------------------------

async function loadPriceTrend() {
    const description = document.getElementById('itemSearch').value.trim();
    if (!description) return;
    const { start, end } = getFilters();
    const wrap  = document.getElementById('priceChartWrap');
    const empty = document.getElementById('priceEmpty');
    priceChart  = destroy(priceChart);
    const data = await fetchJSON('/api/price-trend?' + qs({ description, start, end, company_id: COMPANY_ID }));
    if (!data.labels.length) { wrap.style.display = 'none'; empty.style.display = 'block'; return; }
    empty.style.display = 'none';
    wrap.style.display  = 'block';
    priceChart = new Chart(document.getElementById('priceChart').getContext('2d'), {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [{
                label: data.description, data: data.values,
                borderColor: COLORS[3], backgroundColor: COLORS[3] + '22',
                pointRadius: 5, pointHoverRadius: 7, tension: 0.2, fill: true,
            }],
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { display: true },
                tooltip: {
                    callbacks: {
                        label: ctx => {
                            const price = ctx.parsed.y, idx = ctx.dataIndex, vals = ctx.dataset.data;
                            let line = ' ' + fmt(price) + ' per unit';
                            if (idx > 0 && vals[idx - 1] != null) {
                                const prev = vals[idx - 1];
                                const pct  = ((price - prev) / prev * 100).toFixed(1);
                                line += '  (' + (pct >= 0 ? '+' : '') + pct + '% vs prev)';
                            }
                            return line;
                        },
                    },
                },
            },
            scales: { y: { beginAtZero: false, ticks: { callback: v => '\u20ac' + v } } },
        },
    });
}

async function suggestItems(q) {
    clearTimeout(suggestTimer);
    const list = document.getElementById('suggestions');
    if (q.length < 2) { list.style.display = 'none'; return; }
    suggestTimer = setTimeout(async () => {
        const items = await fetchJSON('/api/item-suggestions?' + qs({ q, company_id: COMPANY_ID }));
        list.innerHTML = '';
        if (!items.length) { list.style.display = 'none'; return; }
        items.forEach(item => {
            const li = document.createElement('li');
            li.textContent = item;
            li.addEventListener('mousedown', () => {
                document.getElementById('itemSearch').value = item;
                list.style.display = 'none';
                loadPriceTrend();
            });
            list.appendChild(li);
        });
        list.style.display = 'block';
    }, 250);
}

document.addEventListener('click', e => {
    if (!e.target.closest('#itemSearch'))
        document.getElementById('suggestions').style.display = 'none';
});

document.getElementById('itemSearch').addEventListener('keydown', e => {
    if (e.key === 'Enter') loadPriceTrend();
});

// ---------------------------------------------------------------------------
// Load all
// ---------------------------------------------------------------------------

async function loadAll() {
    if (!window.validateDateRange()) return;
    const { start, end } = getFilters();
    const lsKey = 'filter_company_' + COMPANY_ID;
    localStorage.setItem(lsKey + '_start', start);
    localStorage.setItem(lsKey + '_end',   end);
    try {
        await Promise.all([
            loadSummary(start, end),
            loadVisitChart(start, end),
            loadCategoryChart(start, end),
            loadTopItemsChart(start, end),
        ]);
    } catch (err) {
        console.error('Chart load error:', err);
    }
}

// Initialise
window.addEventListener('DOMContentLoaded', () => {
    const today    = new Date();
    const todayStr = today.toISOString().split('T')[0];
    const defStart = new Date(today);
    defStart.setFullYear(defStart.getFullYear() - 1);
    const lsKey = 'filter_company_' + COMPANY_ID;

    const startEl = document.getElementById('startDate');
    const endEl   = document.getElementById('endDate');
    endEl.value   = localStorage.getItem(lsKey + '_end')   || todayStr;
    startEl.value = localStorage.getItem(lsKey + '_start') || defStart.toISOString().split('T')[0];

    startEl.addEventListener('change', function () { localStorage.setItem(lsKey + '_start', this.value); });
    endEl.addEventListener('change',   function () { localStorage.setItem(lsKey + '_end',   this.value); });

    loadAll();
});
