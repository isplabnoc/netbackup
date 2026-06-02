const metrics = window.dashboardMetrics || {};

Chart.defaults.color = "#d7e6f6";
Chart.defaults.borderColor = "rgba(127, 173, 221, .18)";
Chart.defaults.font.family = 'Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';

const statusDonut = document.getElementById("statusDonut");
if (statusDonut) {
  const success = Number(metrics.backup_success || 0);
  const failed = Number(metrics.backup_failed || 0);
  new Chart(statusDonut, {
    type: "doughnut",
    data: {
      labels: ["OK", "Falha"],
      datasets: [{
        data: [success, failed],
        backgroundColor: ["#35c64a", "#ef4044"],
        borderWidth: 0,
        hoverOffset: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "62%",
      plugins: {
        legend: { display: false },
        tooltip: { enabled: true }
      }
    }
  });
}

function chart(id, type, labels, values, label) {
  const element = document.getElementById(id);
  if (!element) return;
  new Chart(element, {
    type,
    data: {
      labels,
      datasets: [{
        label,
        data: values,
        borderWidth: 2,
        borderColor: "#39a8ff",
        backgroundColor: "rgba(53, 198, 74, .72)"
      }]
    },
    options: { responsive: true, maintainAspectRatio: false }
  });
}

const backupsByDay = metrics.backups_by_day || [];
chart("backupsChart", "line", backupsByDay.map(x => `${x.label} ${x.status}`), backupsByDay.map(x => x.value), "Últimos 30 dias");

const vendors = metrics.failures_by_vendor || [];
chart("vendorsChart", "bar", vendors.map(x => x.label), vendors.map(x => x.value), "Falhas por vendor");

const changes = metrics.changes_by_day || [];
chart("changesChart", "bar", changes.map(x => x.label), changes.map(x => x.value), "Alterações por período");
