"use strict";
let DATA = null;
let dynChart, discChart, summerChart;

const $ = (id) => document.getElementById(id);

$("btn").addEventListener("click", analyze);

async function analyze() {
  const input = $("files");
  if (!input.files.length) { showError("Сначала выберите файлы."); return; }
  const fd = new FormData();
  for (const f of input.files) fd.append("files", f);
  hideError();
  $("btn").textContent = "Обработка…";
  try {
    const r = await fetch("/analyze", { method: "POST", body: fd });
    const j = await r.json();
    if (!r.ok) { showError(j.error || "Ошибка."); return; }
    DATA = j;
    render();
    $("report").classList.remove("hidden");
  } catch (e) {
    showError("Сбой запроса: " + e);
  } finally {
    $("btn").textContent = "Анализировать";
  }
}

function showError(m){ const e=$("error"); e.textContent=m; e.classList.remove("hidden"); }
function hideError(){ $("error").classList.add("hidden"); }

function render() {
  renderTotals();
  $("monthsList").textContent = DATA.months.join(", ");
  fillTeacherSelect();
  renderTops();
  renderAllTable(DATA.teachers);
  renderSummer();
}

function metric(value, label) {
  return `<div class="metric"><div class="v">${value}</div><div class="l">${label}</div></div>`;
}

function renderTotals() {
  const t = DATA.totals;
  $("totals").innerHTML =
    metric(t.teachers_count, "Тренеров") +
    metric(t.lessons_total, "Всего уроков") +
    metric(t.cancel_teacher, "Отмены (тренер)") +
    metric(t.cancel_student, "Отмены (ученик)") +
    metric(t.reschedule_teacher, "Переносы (тренер)") +
    metric(t.reschedule_student, "Переносы (ученик)") +
    metric(t.replace_teacher, "Замены (тренер)");
}

function fillTeacherSelect() {
  const sel = $("teacherSelect");
  sel.innerHTML = "";
  DATA.teachers.forEach((t) => {
    const o = document.createElement("option");
    o.value = t.teacher_id; o.textContent = "ID " + t.teacher_id;
    sel.appendChild(o);
  });
  sel.onchange = renderTeacher;
  renderTeacher();
}

function findTeacher(id) {
  return DATA.teachers.find((t) => String(t.teacher_id) === String(id));
}

function renderTeacher() {
  const t = findTeacher($("teacherSelect").value);
  if (!t) return;
  $("teacherMetrics").innerHTML =
    metric(t.lessons_total, "Уроков всего") +
    metric(t.cancel_teacher, "Отмены (тренер)") +
    metric(t.replace_teacher, "Замены (тренер)") +
    metric(t.reschedule_teacher, "Переносы (тренер)") +
    metric(t.cancel_student, "Отмены (ученик)") +
    metric(t.reschedule_student, "Переносы (ученик)");

  // Линейный график динамики учеников
  if (dynChart) dynChart.destroy();
  dynChart = new Chart($("dynamicsChart"), {
    type: "line",
    data: {
      labels: DATA.months,
      datasets: [{
        label: "Кол-во учеников (ID " + t.teacher_id + ")",
        data: t.dynamics, borderColor: "#4f9cf9",
        backgroundColor: "rgba(79,156,249,.15)", fill: true, tension: .25,
        pointRadius: 5,
      }],
    },
    options: chartOpts("Динамика количества учеников по месяцам"),
  });

  // Столбчатый график дисциплины
  if (discChart) discChart.destroy();
  discChart = new Chart($("discChart"), {
    type: "bar",
    data: {
      labels: ["Отмены тренер","Замены тренер","Переносы тренер","Отмены ученик","Переносы ученик"],
      datasets: [{
        label: "За все месяцы",
        data: [t.cancel_teacher,t.replace_teacher,t.reschedule_teacher,t.cancel_student,t.reschedule_student],
        backgroundColor: ["#f85149","#d29922","#bb8009","#3fb950","#2da44e"],
      }],
    },
    options: chartOpts("Показатели дисциплины (сумма за период)"),
  });
}

function chartOpts(title) {
  return {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { labels: { color: "#e6edf3" } },
      title: { display: true, text: title, color: "#8b98a5" } },
    scales: {
      x: { ticks: { color: "#8b98a5" }, grid: { color: "#2d3744" } },
      y: { ticks: { color: "#8b98a5" }, grid: { color: "#2d3744" }, beginAtZero: true },
    },
  };
}

function rankTable(el, rows) {
  let h = "<tr><th>ID тренера</th><th>Переносы (тренер)</th><th>Замены (тренер)</th><th>Σ</th></tr>";
  rows.forEach((t) => {
    h += `<tr><td>${t.teacher_id}</td><td>${t.reschedule_teacher}</td><td>${t.replace_teacher}</td><td>${t.reschedule_teacher + t.replace_teacher}</td></tr>`;
  });
  $(el).innerHTML = h;
}

function renderTops() {
  rankTable("tableMost", DATA.tops.most);
  rankTable("tableLeast", DATA.tops.least);
}

function renderAllTable(rows) {
  let h = "<tr><th>ID</th><th>Уроки</th><th>Учеников Σ</th><th>Отм.тр</th><th>Зам.тр</th><th>Пер.тр</th><th>Отм.уч</th><th>Пер.уч</th></tr>";
  rows.forEach((t) => {
    h += `<tr><td>${t.teacher_id}</td><td>${t.lessons_total}</td><td>${t.students_sum}</td><td>${t.cancel_teacher}</td><td>${t.replace_teacher}</td><td>${t.reschedule_teacher}</td><td>${t.cancel_student}</td><td>${t.reschedule_student}</td></tr>`;
  });
  $("tableAll").innerHTML = h;
}

$("exportBtn").addEventListener("click", () => {
  const input = $("files");
  if (!input.files.length) { showError("Сначала загрузите файлы."); return; }
  const fd = new FormData();
  for (const f of input.files) fd.append("files", f);
  fetch("/export.csv", { method: "POST", body: fd })
    .then((r) => r.blob())
    .then((blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "teachers_report.csv";
      a.click(); URL.revokeObjectURL(url);
    });
});

$("search").addEventListener("input", (e) => {
  const q = e.target.value.trim();
  renderAllTable(DATA.teachers.filter((t) => String(t.teacher_id).includes(q)));
});

function renderSummer() {
  const s = DATA.summer_forecast;
  $("forecastNote").textContent =
    `Прогноз построен от среднего весеннего уровня (≈${s.spring_avg_students} учеников/мес). ` +
    `Множители спада: июнь ×${s.factors["июнь"]}, июль ×${s.factors["июль"]}, август ×${s.factors["август"]}. ` +
    `Отмены/переносы по инициативе ученика повышены ×${s.student_cancel_uplift} (отпуска, отъезды, конец учебного года). ` +
    `Основано на открытой статистике сезонности детских образовательных программ.`;

  if (summerChart) summerChart.destroy();
  summerChart = new Chart($("summerChart"), {
    type: "bar",
    data: {
      labels: s.forecast.map((f) => f.month),
      datasets: [
        { label: "Ученики (прогноз)", data: s.forecast.map((f)=>f.students), backgroundColor:"#4f9cf9" },
        { label: "Отмены ученик", data: s.forecast.map((f)=>f.cancel_student), backgroundColor:"#3fb950" },
        { label: "Переносы ученик", data: s.forecast.map((f)=>f.reschedule_student), backgroundColor:"#2da44e" },
        { label: "Отмены тренер", data: s.forecast.map((f)=>f.cancel_teacher), backgroundColor:"#f85149" },
      ],
    },
    options: chartOpts("Прогноз показателей на летние месяцы"),
  });

  let h = "<tr><th>Месяц</th><th>Ученики</th><th>Отмены ученик</th><th>Переносы ученик</th><th>Отмены тренер</th></tr>";
  s.forecast.forEach((f) => {
    h += `<tr><td>${f.month}</td><td>${f.students}</td><td>${f.cancel_student}</td><td>${f.reschedule_student}</td><td>${f.cancel_teacher}</td></tr>`;
  });
  $("tableSummer").innerHTML = h;
}
