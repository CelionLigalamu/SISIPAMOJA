document.addEventListener('DOMContentLoaded', () => {
    const statsUrl = '/admin/dashboard-stats/';
    const statNodes = document.querySelectorAll('[data-stat]');
    const updatedAt = document.getElementById('dashboard-updated-at');

    const formatValue = (value, format) => {
        if (format === 'currency') {
            return `KES ${Number(value || 0).toLocaleString()}`;
        }
        return Number(value || 0).toLocaleString();
    };

    const refreshStats = async () => {
        try {
            const response = await fetch(statsUrl, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin',
            });

            if (!response.ok) {
                return;
            }

            const data = await response.json();

            statNodes.forEach((node) => {
                const key = node.dataset.stat;
                if (Object.prototype.hasOwnProperty.call(data, key)) {
                    node.textContent = formatValue(data[key], node.dataset.format);
                }
            });

            if (updatedAt) {
                updatedAt.textContent = `Updated ${new Date().toLocaleTimeString()}`;
            }
        } catch (error) {
            console.error('Failed to refresh dashboard statistics', error);
        }
    };

    refreshStats();
    window.setInterval(refreshStats, 30000);
});