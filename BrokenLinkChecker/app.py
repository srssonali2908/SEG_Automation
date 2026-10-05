# -*- coding: utf-8 -*-
"""
Web front end for the PDF broken link checker.

Run:  python app.py   then open http://127.0.0.1:5000
"""
import io
import os

from flask import Flask, Response, render_template, request
from werkzeug.utils import secure_filename

from link_checker import report_filename, scrape_pdf_links

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        upload = request.files.get("file")
        if not upload or not upload.filename:
            return render_template("index.html", error="Please choose a PDF file to upload."), 400
        if not upload.filename.lower().endswith(".pdf"):
            return render_template("index.html", error="Please upload a valid PDF file!"), 400

        # Processed in memory so nothing is left behind on disk.
        csv_data = scrape_pdf_links(io.BytesIO(upload.read()))
        download_name = report_filename(secure_filename(upload.filename))

        # The BOM lets Excel open the CSV as UTF-8.
        return Response(
            "\ufeff" + csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": 'attachment; filename="{}"'.format(download_name)},
        )

    return render_template("index.html")


@app.errorhandler(413)
def too_large(_):
    return render_template("index.html", error="That file is too large (limit 200 MB)."), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)))
