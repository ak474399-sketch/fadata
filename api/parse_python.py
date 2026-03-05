from pathlib import Path
import sys

from flask import Flask, jsonify, request

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from common.parser import parse_dataframe, read_table

app = Flask(__name__)


def _parse_files_impl():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"results": [], "errors": [{"fileName": "-", "message": "未上传文件。"}]}), 400

    results = []
    errors = []

    for file in files:
        try:
            payload = file.read()
            dataframe = read_table(file.filename, payload)
            rows = parse_dataframe(dataframe)
            results.append({"fileName": file.filename, "rows": rows})
        except Exception as exc:
            errors.append({"fileName": file.filename, "message": str(exc)})

    return jsonify({"results": results, "errors": errors})


@app.post("/")
def parse_files_root():
    return _parse_files_impl()


@app.post("/api/parse_python")
def parse_files_scoped():
    return _parse_files_impl()
