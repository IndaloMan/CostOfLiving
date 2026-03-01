/* Energy Nordic — electricity analysis charts */

const labels  = billData.map(r => r.date);
const P1COLOR = '#2980b9';
const P2COLOR = '#27ae60';
const P3COLOR = '#e67e22';

// ---------------------------------------------------------------------------
// Chart 1: Consumption per period — line chart
// ---------------------------------------------------------------------------
new Chart(document.getElementById('consumptionChart').getContext('2d'), {
    type: 'line',
    data: {
        labels,
        datasets: [
            {
                label: 'P1 (peak)',
                data: billData.map(r => r.data.energy.P1?.kwh ?? 0),
                borderColor: P1COLOR,
                backgroundColor: P1COLOR + '22',
                pointRadius: 5,
                pointHoverRadius: 7,
                tension: 0.2,
                fill: false,
            },
            {
                label: 'P2 (shoulder)',
                data: billData.map(r => r.data.energy.P2?.kwh ?? 0),
                borderColor: P2COLOR,
                backgroundColor: P2COLOR + '22',
                pointRadius: 5,
                pointHoverRadius: 7,
                tension: 0.2,
                fill: false,
            },
            {
                label: 'P3 (off-peak)',
                data: billData.map(r => r.data.energy.P3?.kwh ?? 0),
                borderColor: P3COLOR,
                backgroundColor: P3COLOR + '22',
                pointRadius: 5,
                pointHoverRadius: 7,
                tension: 0.2,
                fill: false,
            },
        ],
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { position: 'top' },
            tooltip: {
                callbacks: {
                    footer: items => {
                        const total = items.reduce((s, i) => s + i.parsed.y, 0);
                        return `Total: ${total.toFixed(2)} kWh`;
                    },
                },
            },
        },
        scales: {
            y: { beginAtZero: true, ticks: { callback: v => v + ' kWh' } },
        },
    },
});

// ---------------------------------------------------------------------------
// Chart 2: Energy price trend — line chart (price + toll per period)
// ---------------------------------------------------------------------------
new Chart(document.getElementById('priceChart').getContext('2d'), {
    type: 'line',
    data: {
        labels,
        datasets: [
            {
                label: 'P1 (peak)',
                data: billData.map(r => {
                    const p = r.data.energy.P1;
                    return p ? +((p.energy_price ?? 0) + (p.toll ?? 0)).toFixed(4) : null;
                }),
                borderColor: P1COLOR,
                backgroundColor: P1COLOR + '22',
                pointRadius: 5,
                tension: 0.2,
            },
            {
                label: 'P2 (shoulder)',
                data: billData.map(r => {
                    const p = r.data.energy.P2;
                    return p ? +((p.energy_price ?? 0) + (p.toll ?? 0)).toFixed(4) : null;
                }),
                borderColor: P2COLOR,
                backgroundColor: P2COLOR + '22',
                pointRadius: 5,
                tension: 0.2,
            },
            {
                label: 'P3 (off-peak)',
                data: billData.map(r => {
                    const p = r.data.energy.P3;
                    return p ? +((p.energy_price ?? 0) + (p.toll ?? 0)).toFixed(4) : null;
                }),
                borderColor: P3COLOR,
                backgroundColor: P3COLOR + '22',
                pointRadius: 5,
                tension: 0.2,
            },
        ],
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'top' } },
        scales: {
            y: {
                beginAtZero: false,
                ticks: { callback: v => '€' + v.toFixed(4) },
            },
        },
    },
});

// ---------------------------------------------------------------------------
// Chart 3: Bill component breakdown — stacked bar
// ---------------------------------------------------------------------------
new Chart(document.getElementById('breakdownChart').getContext('2d'), {
    type: 'bar',
    data: {
        labels,
        datasets: [
            {
                label: 'Energy (P1+P2+P3)',
                data: billData.map(r => {
                    const e = r.data.energy;
                    return +((e.P1?.total ?? 0) + (e.P2?.total ?? 0) + (e.P3?.total ?? 0)).toFixed(2);
                }),
                backgroundColor: '#2980b9',
                borderRadius: 3,
            },
            {
                label: 'Contracted Power',
                data: billData.map(r => {
                    const cp = r.data.contracted_power;
                    return +((cp?.P1?.total ?? 0) + (cp?.P2?.total ?? 0)).toFixed(2);
                }),
                backgroundColor: '#9b59b6',
                borderRadius: 3,
            },
            {
                label: 'Handle Fee',
                data: billData.map(r => r.data.handle_fee ?? 0),
                backgroundColor: '#1abc9c',
                borderRadius: 3,
            },
            {
                label: 'Meter Hire',
                data: billData.map(r => r.data.meter_hire?.total ?? 0),
                backgroundColor: '#95a5a6',
                borderRadius: 3,
            },
            {
                label: 'Electricity Tax',
                data: billData.map(r => r.data.electricity_tax?.amount ?? 0),
                backgroundColor: '#e74c3c',
                borderRadius: 3,
            },
            {
                label: 'VAT (21%)',
                data: billData.map(r => r.data.vat?.amount ?? 0),
                backgroundColor: '#e67e22',
                borderRadius: 3,
            },
        ],
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { position: 'top', labels: { boxWidth: 12, font: { size: 11 } } },
            tooltip: {
                callbacks: {
                    footer: items => {
                        const total = items.reduce((s, i) => s + i.parsed.y, 0);
                        return `Total: €${total.toFixed(2)}`;
                    },
                },
            },
        },
        scales: {
            x: { stacked: true },
            y: { stacked: true, beginAtZero: true, ticks: { callback: v => '€' + v } },
        },
    },
});
