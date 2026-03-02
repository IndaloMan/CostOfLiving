/* Mercadona shopping analysis charts */

const COLORS = [
    '#2980b9','#27ae60','#e67e22','#e74c3c','#9b59b6',
    '#1abc9c','#f39c12','#34495e','#16a085','#c0392b',
    '#2ecc71','#3498db','#d35400','#8e44ad','#95a5a6',
];

let visitChart    = null;
let categoryChart = null;
let topItemsChart = null;
let priceChart    = null;

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`API error ${res.status}`);
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
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
        .join('&');
}

function fmt(n) {
    return '€' + Number(n).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function destroy(chart) { if (chart) chart.destroy(); return null; }

// ---------------------------------------------------------------------------
// Summary stats
// ---------------------------------------------------------------------------

async function loadSummary(start, end) {
    const d = await fetchJSON(`/api/analysis/mercadona/summary?${qs({ start, end })}`);
    document.getElementById('statVisits').textContent  = d.receipt_count;
    document.getElementById('statTotal').textContent   = fmt(d.total_spent);
    document.getElementById('statAvg').textContent     = fmt(d.avg_per_receipt);
    document.getElementById('statItems').textContent   = d.total_items;
    document.getElementById('statTopCat').textContent  = d.top_category;
}

// ---------------------------------------------------------------------------
// Spend per visit — bar chart
// ---------------------------------------------------------------------------

async function loadVisitChart(start, end) {
    const data  = await fetchJSON(`/api/analysis/mercadona/per-visit?${qs({ start, end })}`);
    const empty = document.getElementById('visitEmpty');
    visitChart  = destroy(visitChart);

    if (!data.labels.length) { empty.style.display = 'block'; return; }
    empty.style.display = 'none';

    const ctx = document.getElementById('visitChart').getContext('2d');
    visitChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [{
                label: 'Basket Total (€)',
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
            scales: { y: { beginAtZero: true, ticks: { callback: v => '€' + v } } },
        },
    });
}

// ---------------------------------------------------------------------------
// By category — doughnut
// ---------------------------------------------------------------------------

async function loadCategoryChart(start, end) {
    const data  = await fetchJSON(`/api/analysis/mercadona/by-category?${qs({ start, end })}`);
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
                tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${fmt(ctx.parsed)}` } },
            },
        },
    });
}

// ---------------------------------------------------------------------------
// Top items — horizontal bar
// ---------------------------------------------------------------------------

async function loadTopItemsChart(start, end) {
    const data  = await fetchJSON(`/api/analysis/mercadona/top-items?${qs({ start, end })}`);
    const empty = document.getElementById('topItemsEmpty');
    topItemsChart = destroy(topItemsChart);

    if (!data.labels.length) { empty.style.display = 'block'; return; }
    empty.style.display = 'none';

    // Reverse so highest bar is at top
    const labels = [...data.labels].reverse();
    const values = [...data.total_spent].reverse();
    const counts = [...data.purchase_count].reverse();

    const ctx = document.getElementById('topItemsChart').getContext('2d');
    topItemsChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Total Spent (€)',
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
                        label: (ctx) => ` ${fmt(ctx.parsed.x)}`,
                        afterLabel: (ctx) => ` ${counts[ctx.dataIndex]} purchase(s)`,
                    },
                },
            },
            scales: { x: { beginAtZero: true, ticks: { callback: v => '€' + v } } },
        },
    });
}

// ---------------------------------------------------------------------------
// Price tracker — line chart
// ---------------------------------------------------------------------------

async function loadPriceTrend() {
    const description = document.getElementById('itemSearch').value.trim();
    if (!description) return;

    const { start, end } = getFilters();
    const data  = await fetchJSON(`/api/analysis/mercadona/price-trend?${qs({ description, start, end })}`);
    const wrap  = document.getElementById('priceChartWrap');
    const empty = document.getElementById('priceEmpty');
    priceChart  = destroy(priceChart);

    if (!data.labels.length) {
        wrap.style.display = 'none'; empty.style.display = 'block'; return;
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
                tooltip: { callbacks: { label: ctx => ` ${fmt(ctx.parsed.y)} per unit` } },
            },
            scales: { y: { beginAtZero: false, ticks: { callback: v => '€' + v } } },
        },
    });
}

// ---------------------------------------------------------------------------
// Item autocomplete (Mercadona items only)
// ---------------------------------------------------------------------------

let suggestTimer = null;

async function suggestItems(q) {
    clearTimeout(suggestTimer);
    const list = document.getElementById('suggestions');
    if (q.length < 2) { list.style.display = 'none'; return; }

    suggestTimer = setTimeout(async () => {
        const items = await fetchJSON(`/api/analysis/mercadona/item-suggestions?${qs({ q })}`);
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
    const { start, end } = getFilters();
    localStorage.setItem('filter_mercadona_start', start);
    localStorage.setItem('filter_mercadona_end',   end);
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

// Initialise — restore saved dates or default to last 12 months
window.addEventListener('DOMContentLoaded', () => {
    const today = new Date();
    const defStart = new Date(today);
    defStart.setFullYear(defStart.getFullYear() - 1);
    document.getElementById('endDate').value   = localStorage.getItem('filter_mercadona_end')   || today.toISOString().split('T')[0];
    document.getElementById('startDate').value = localStorage.getItem('filter_mercadona_start') || defStart.toISOString().split('T')[0];

    // Save immediately when either date input changes (even without clicking Apply)
    document.getElementById('startDate').addEventListener('change', function () {
        localStorage.setItem('filter_mercadona_start', this.value);
    });
    document.getElementById('endDate').addEventListener('change', function () {
        localStorage.setItem('filter_mercadona_end', this.value);
    });

    loadAll();
});
