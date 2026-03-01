/* Reports page — Chart.js charts powered by the /api/* endpoints */

const COLORS = [
    '#2980b9','#27ae60','#e67e22','#e74c3c','#9b59b6',
    '#1abc9c','#f39c12','#34495e','#16a085','#c0392b',
    '#2ecc71','#3498db','#d35400','#8e44ad','#95a5a6',
];

let timeChart     = null;
let categoryChart = null;
let companyChart  = null;
let priceChart    = null;

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
// Price tracker — line chart
// ---------------------------------------------------------------------------

async function loadPriceTrend() {
    const description = document.getElementById('itemSearch').value.trim();
    if (!description) return;

    const { start, end, companyId } = getFilters();
    const data = await fetchJSON(`/api/price-trend?${qs({ description, start, end, company_id: companyId })}`);

    const wrap  = document.getElementById('priceChartWrap');
    const empty = document.getElementById('priceEmpty');
    priceChart = destroyChart(priceChart);

    if (!data.labels.length) {
        wrap.style.display  = 'none';
        empty.style.display = 'block';
        return;
    }
    empty.style.display = 'none';
    wrap.style.display  = 'block';

    const ctx = document.getElementById('priceChart').getContext('2d');
    priceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [{
                label: data.description,
                data: data.values,
                borderColor: COLORS[3],
                backgroundColor: COLORS[3] + '22',
                pointRadius: 5,
                pointHoverRadius: 7,
                tension: 0.2,
                fill: true,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true },
                tooltip: {
                    callbacks: {
                        label: ctx => ` ${fmt(ctx.parsed.y)} per unit`,
                    },
                },
            },
            scales: {
                y: { beginAtZero: false, ticks: { callback: v => '€' + v } },
            },
        },
    });
}

// ---------------------------------------------------------------------------
// Item autocomplete
// ---------------------------------------------------------------------------

let suggestTimer = null;

async function suggestItems(q) {
    clearTimeout(suggestTimer);
    const list = document.getElementById('suggestions');
    if (q.length < 2) { list.style.display = 'none'; return; }

    suggestTimer = setTimeout(async () => {
        const items = await fetchJSON(`/api/item-suggestions?${qs({ q })}`);
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
    if (!e.target.closest('#itemSearch')) {
        document.getElementById('suggestions').style.display = 'none';
    }
});

document.getElementById('itemSearch').addEventListener('keydown', e => {
    if (e.key === 'Enter') { loadPriceTrend(); }
});

// ---------------------------------------------------------------------------
// Load all charts
// ---------------------------------------------------------------------------

async function loadAll() {
    const { start, end, groupBy, companyId } = getFilters();
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
// Initialise with last 12 months
// ---------------------------------------------------------------------------

window.addEventListener('DOMContentLoaded', () => {
    const today = new Date();
    const start = new Date(today);
    start.setFullYear(start.getFullYear() - 1);

    document.getElementById('endDate').value   = today.toISOString().split('T')[0];
    document.getElementById('startDate').value = start.toISOString().split('T')[0];

    loadAll();
});
