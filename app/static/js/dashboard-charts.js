/* Dashboard grafiklerini çizer.
 *
 * Sayısal veriler şablondan #dashboard-chart-data içindeki JSON etiketiyle
 * gelir. JSON etiketi çalıştırılabilir betik olmadığı için CSP tarafından
 * engellenmez; böylece satır içi betik yazmaya gerek kalmaz.
 */
(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        var dataElement = document.getElementById('dashboard-chart-data');

        if (!dataElement || typeof window.Chart === 'undefined') {
            return;
        }

        var stats;

        try {
            stats = JSON.parse(dataElement.textContent);
        } catch (error) {
            return;
        }

        var commonLegend = {
            labels: { usePointStyle: true, boxWidth: 8, color: '#475569' }
        };

        var statusCanvas = document.getElementById('taskStatusChart');

        if (statusCanvas) {
            new window.Chart(statusCanvas, {
                type: 'doughnut',
                data: {
                    labels: [
                        'Yapılacak',
                        'Devam ediyor',
                        'İnceleme bekliyor',
                        'Düzeltme istendi',
                        'Tamamlandı'
                    ],
                    datasets: [{
                        data: [
                            stats.todo,
                            stats.in_progress,
                            stats.review_pending,
                            stats.revision_requested,
                            stats.done
                        ],
                        backgroundColor: [
                            '#f59e0b',
                            '#3b82f6',
                            '#6366f1',
                            '#f97316',
                            '#22c55e'
                        ],
                        borderWidth: 0,
                        hoverOffset: 6
                    }]
                },
                options: {
                    responsive: true,
                    cutout: '68%',
                    plugins: {
                        legend: Object.assign({}, commonLegend, {
                            position: 'bottom'
                        })
                    }
                }
            });
        }

        var priorityCanvas = document.getElementById('taskPriorityChart');

        if (priorityCanvas) {
            new window.Chart(priorityCanvas, {
                type: 'bar',
                data: {
                    labels: ['Düşük', 'Orta', 'Yüksek'],
                    datasets: [{
                        data: [stats.low, stats.medium, stats.high],
                        backgroundColor: ['#22c55e', '#f59e0b', '#ef4444'],
                        borderRadius: 8,
                        borderSkipped: false
                    }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: {
                            grid: { display: false },
                            border: { display: false }
                        },
                        y: {
                            beginAtZero: true,
                            ticks: { precision: 0 },
                            border: { display: false },
                            grid: { color: '#e2e8f0' }
                        }
                    }
                }
            });
        }
    });
})();
