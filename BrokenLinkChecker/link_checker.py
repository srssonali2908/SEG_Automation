# -*- coding: utf-8 -*-
"""
Broken link checker for PDF documents.

Extracts every external hyperlink (URI annotation) from a PDF, checks each one
over HTTP and produces a CSV report.

Command-line usage:
    python link_checker.py <file.pdf> [-o report.csv] [--workers 8]
"""
import argparse
import csv
import io
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests
from pypdf import PdfReader

USER_AGENT = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
TIMEOUT = 10

# Known naked directory/support pages that loop or fail outside the VPN.
PUBLIC_DIRECTORY_FALLBACKS = {
    "https://www.altera.com/design": "https://www.altera.com/design/resources-overview",
    "https://www.intel.com/content/www/us/en/support/programmable/kdb-filter.html":
        "https://community.altera.com/category/top/kb/knowledge-base",
}

# Hosts on these domains may only resolve inside the corporate network, so a
# connection failure is reported as unverified rather than broken.
CORPORATE_DOMAINS = ("intel.com", "altera.com")

CORP_404_REDIRECTOR = "corpredirect.intel.com/redirector/404redirector.aspx?"
PUBLIC_DOC_URL = "https://docs.altera.com/r/docs/{}/current"

CSV_HEADER = [
    "Page Number",
    "Original Link",
    "Status / Error Code",
    "Redirect History (From -> To)",
    "Contains Intel?",
    "Broken?",
]

STATUS_VPN = "Corporate Network Required"


def _is_corporate(url):
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in CORPORATE_DOMAINS)


def _normalize(url):
    return url.lower().rstrip("/")


def _same_url(a, b):
    return a.rstrip("/") == b.rstrip("/")


def _fetch(url):
    """GET a URL following redirects, without downloading the whole body."""
    r = requests.get(url, headers=USER_AGENT, allow_redirects=True,
                     timeout=TIMEOUT, stream=True)
    r.close()
    return r


def _resolve_target(link):
    """Apply the corporate 404-redirector unwrap and known directory fallbacks."""
    if _normalize(link) in PUBLIC_DIRECTORY_FALLBACKS:
        link = PUBLIC_DIRECTORY_FALLBACKS[_normalize(link)]

    if CORP_404_REDIRECTOR in link.lower():
        parts = link.split("?", 1)
        if len(parts) > 1 and parts[1].startswith("http"):
            link = parts[1]
            if _normalize(link) in PUBLIC_DIRECTORY_FALLBACKS:
                link = PUBLIC_DIRECTORY_FALLBACKS[_normalize(link)]
    return link


def _result_from_response(r, target):
    if r.status_code == 200:
        redirect = "None" if _same_url(r.url, target) else r.url
        return "200 OK", redirect
    return "HTTP {}".format(r.status_code), r.url


def check_link(link):
    """
    Check a single link.

    Returns (status_label, redirect_history, contains_intel).
    redirect_history is "None" when the link resolved without redirecting.
    """
    target = _resolve_target(link)
    target_lower = _normalize(target)
    is_intel = "Yes" if "intel.com" in target_lower else "No"

    id_match = re.search(r"/programmable/(\d+)", target_lower)
    doc_id = id_match.group(1) if id_match else None

    try:
        status, redirect = _result_from_response(_fetch(target), target)
        return status, redirect, is_intel

    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        # Internal hosts are unreachable outside the corporate network; try the
        # public equivalent before giving up.
        if doc_id:
            try:
                r = _fetch(PUBLIC_DOC_URL.format(doc_id))
            except requests.exceptions.RequestException:
                return STATUS_VPN, "Network Connection Blocked -> {}".format(target), is_intel
            if r.status_code == 200:
                status, redirect = _result_from_response(r, target)
                return status, redirect, is_intel
            return ("HTTP {}".format(r.status_code),
                    "Public Fallback Missing -> {}".format(target), is_intel)

        for key, replacement in PUBLIC_DIRECTORY_FALLBACKS.items():
            if key in target_lower:
                try:
                    r = _fetch(replacement)
                except requests.exceptions.RequestException:
                    continue
                if r.status_code == 200:
                    status, redirect = _result_from_response(r, target)
                    return status, redirect, is_intel

        if _is_corporate(target):
            return STATUS_VPN, "Blocked outside VPN -> {}".format(target), is_intel
        return "Connection Failed", "Host unreachable -> {}".format(target), is_intel

    except requests.exceptions.RequestException as e:
        return "Request Error", str(e), is_intel


def is_broken(status_label):
    if status_label == "200 OK":
        return "No"
    if status_label == STATUS_VPN:
        return "Unverified (VPN)"
    return "Yes"


def extract_links(pdf_source):
    """
    Return a list of (page_number, url) for every external http(s) link.

    pdf_source may be a file path or a binary file-like object. Internal
    document anchors (GoTo actions) are skipped.
    """
    reader = PdfReader(pdf_source)
    links = []
    for index, page in enumerate(reader.pages):
        annots = page.get("/Annots")
        if not annots:
            continue
        for annot in annots.get_object():
            annot_obj = annot.get_object()
            action = annot_obj.get("/A")
            if action is None:
                continue
            action = action.get_object()
            uri = action.get("/URI")
            if uri is None:
                continue
            uri = uri.get_object()
            if isinstance(uri, bytes):
                uri = uri.decode("utf-8", errors="replace")
            uri = str(uri).strip()
            if uri.lower().startswith("http"):
                links.append((index + 1, uri))
    return links


def scrape_pdf_links(pdf_source, workers=8):
    """Extract and check every link in a PDF, returning the CSV report as text."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_HEADER)

    try:
        links = extract_links(pdf_source)
    except Exception as e:
        writer.writerow(["Error reading PDF: {}".format(e), "", "", "", "", ""])
        return output.getvalue()

    if not links:
        writer.writerow(["No hyperlinked web URLs found in this PDF document.", "", "", "", "", ""])
        return output.getvalue()

    # Each distinct URL is checked once, even if it appears on many pages.
    unique_urls = list(dict.fromkeys(url for _, url in links))
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        results = dict(zip(unique_urls, pool.map(check_link, unique_urls)))

    for page_num, url in links:
        status, redirect, is_intel = results[url]
        writer.writerow([page_num, url, status, redirect or "None", is_intel, is_broken(status)])

    return output.getvalue()


def report_filename(pdf_name):
    base = os.path.splitext(os.path.basename(pdf_name))[0] or "document"
    return "broken-links-{}.csv".format(base)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check every hyperlink in a PDF for broken links.")
    parser.add_argument("pdf", help="Path to the PDF file")
    parser.add_argument("-o", "--output", help="CSV output path (default: broken-links-<name>.csv)")
    parser.add_argument("--workers", type=int, default=8, help="Parallel link checks (default: 8)")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.pdf):
        parser.error("File not found: {}".format(args.pdf))

    csv_data = scrape_pdf_links(args.pdf, workers=args.workers)
    out_path = args.output or report_filename(args.pdf)
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        f.write(csv_data)

    rows = [row for row in csv.reader(io.StringIO(csv_data)) if row and row[0].isdigit()]
    broken = sum(1 for row in rows if row[5] == "Yes")
    print("Checked {} link(s), {} broken. Report saved to {}".format(len(rows), broken, out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
