# -*- coding: utf-8 -*-
"""
web2py controller for the PDF broken link checker.

Needs link_checker.py in the application's modules/ folder and the view
views/broken_link_checker/index.html. Served at
/<application>/broken_link_checker/index
"""
import io
import re

import link_checker

CHECK_WORKERS = 16


def index():
    if request.env.request_method != "POST":
        return dict(error=None)

    upload = request.vars.file
    if not hasattr(upload, "file") or not getattr(upload, "filename", ""):
        return dict(error="Please choose a PDF file to upload.")
    if not upload.filename.lower().endswith(".pdf"):
        return dict(error="Please upload a valid PDF file!")

    # Processed in memory so nothing is left behind in uploads/.
    csv_data = link_checker.scrape_pdf_links(io.BytesIO(upload.file.read()), workers=CHECK_WORKERS)

    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", upload.filename.replace("\\", "/").split("/")[-1])
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = 'attachment; filename="{}"'.format(
        link_checker.report_filename(safe_name))
    return link_checker.csv_bytes(csv_data)
