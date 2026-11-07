# -*- coding: utf-8 -*-
"""
Web front end for the PDF broken link checker.

Run:  python app.py [--open]   then open http://127.0.0.1:5000
"""
import argparse
import io
import os
import socket
import threading
import time
import webbrowser

from flask import Flask, Response, render_template, request
from werkzeug.utils import secure_filename

from link_checker import report_filename, scrape_pdf_links

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024

CHECK_WORKERS = int(os.environ.get("LINK_CHECKER_WORKERS", 8))


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        upload = request.files.get("file")
        if not upload or not upload.filename:
            return render_template("index.html", error="Please choose a PDF file to upload."), 400
        if not upload.filename.lower().endswith(".pdf"):
            return render_template("index.html", error="Please upload a valid PDF file!"), 400

        # Processed in memory so nothing is left behind on disk.
        csv_data = scrape_pdf_links(io.BytesIO(upload.read()), workers=CHECK_WORKERS)
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


def _open_browser_when_ready(url, host, port, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                webbrowser.open(url)
                return
        except OSError:
            time.sleep(0.3)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDF broken link checker web app")
    parser.add_argument("--open", action="store_true", help="Open the browser once the server is ready")
    args = parser.parse_args()

    host = "127.0.0.1"
    port = int(os.environ.get("PORT", 5000))
    url = "http://{}:{}/".format(host, port)
    print("Broken link checker running at {}  (close this window to stop it)".format(url))
    if args.open:
        threading.Thread(target=_open_browser_when_ready, args=(url, host, port), daemon=True).start()
    app.run(host=host, port=port)
