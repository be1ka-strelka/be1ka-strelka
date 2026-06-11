# -*- coding: utf-8 -*-
"""
Flask-сервер: загрузка Excel-файлов -> визуальный отчёт по тренерам.
Запуск:  python app/server.py
Открыть: http://127.0.0.1:5000
"""
import os
import io
import csv

from flask import Flask, request, render_template, jsonify, Response

from analytics import aggregate, ValidationError

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 МБ суммарно


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/demo")
def demo():
    return render_template("demo.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    uploaded = request.files.getlist("files")
    if not uploaded:
        return jsonify({"error": "Файлы не выбраны."}), 400

    files = []
    for f in uploaded:
        if not f.filename.lower().endswith((".xlsx", ".xls")):
            return jsonify({"error": f"«{f.filename}» — не Excel-файл."}), 400
        files.append((f.filename, f.read()))

    try:
        result = aggregate(files)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Ошибка обработки: {e}"}), 500

    return jsonify(result)


@app.route("/export.csv", methods=["POST"])
def export_csv():
    """Выгрузка сводной таблицы по тренерам в CSV (для руководства)."""
    uploaded = request.files.getlist("files")
    if not uploaded:
        return jsonify({"error": "Файлы не выбраны."}), 400
    files = [(f.filename, f.read()) for f in uploaded]
    try:
        result = aggregate(files)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow([
        "ID тренера", "Уроков всего", "Учеников (сумма)",
        "Отмены тренер", "Замены тренер", "Переносы тренер",
        "Отмены ученик", "Переносы ученик",
    ])
    for t in result["teachers"]:
        w.writerow([
            t["teacher_id"], t["lessons_total"], t["students_sum"],
            t["cancel_teacher"], t["replace_teacher"], t["reschedule_teacher"],
            t["cancel_student"], t["reschedule_student"],
        ])
    # BOM, чтобы Excel корректно открыл кириллицу
    data = "\ufeff" + buf.getvalue()
    return Response(
        data, mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=teachers_report.csv"},
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
