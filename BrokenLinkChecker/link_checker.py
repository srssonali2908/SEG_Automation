# -*- coding: utf-8 -*-
"""
Broken link checker for PDF documents.

Extracts every external hyperlink (URI annotation) from a PDF, checks each one
over HTTP and produces a CSV report.

Command-line usage:
    python link_checker.py <file.pdf> [-o report.csv] [--workers 8]

Runs on Python 3 and on Python 2.7 (for older web2py servers), with either
pypdf or PyPDF2.
"""
from __future__ import print_function

import argparse
import csv
import io
import os
import re
import sys
from multiprocessing.pool import ThreadPool

import requests

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

try:
    from pypdf import PdfReader
except ImportError:
    from PyPDF2 import PdfFileReader as PdfReader

PY2 = sys.version_info[0] == 2
text_type = unicode if PY2 else str  # noqa: F821

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
NO_LINKS_MESSAGE = "No hyperlinked web URLs found in this PDF document."


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
        for annot in _resolve(annots):
            action = _resolve(annot).get("/A")
            if action is None:
                continue
            uri = _resolve(action).get("/URI")
            if uri is None:
                continue
            uri = _resolve(uri)
            if isinstance(uri, bytes) and not isinstance(uri, text_type):
                uri = uri.decode("utf-8", "replace")
            uri = text_type(uri).strip()
            if uri.lower().startswith("http"):
                links.append((index + 1, uri))
    return links


def _resolve(obj):
    """Dereference an indirect PDF object (pypdf and PyPDF2 spell this differently)."""
    getter = getattr(obj, "get_object", None) or getattr(obj, "getObject", None)
    return getter() if getter else obj


def check_links(links, workers=8, progress=None):
    """
    Check (page_number, url) pairs and return report rows matching CSV_HEADER.

    progress, if given, is called as progress(done, total) after each distinct
    URL finishes. Each distinct URL is checked once, even if it appears on
    many pages.
    """
    unique_urls = list(dict.fromkeys(url for _, url in links))
    results = {}
    pool = ThreadPool(max(1, min(workers, len(unique_urls) or 1)))
    try:
        checked = pool.imap_unordered(_check_one, unique_urls)
        for done, (url, result) in enumerate(checked, 1):
            results[url] = result
            if progress:
                progress(done, len(unique_urls))
    finally:
        pool.close()
        pool.join()

    rows = []
    for page_num, url in links:
        status, redirect, is_intel = results[url]
        rows.append([page_num, url, status, redirect or "None", is_intel, is_broken(status)])
    return rows


def _check_one(url):
    return url, check_link(url)


def rows_to_csv(rows):
    """CSV text for the report (UTF-8 encoded bytes on Python 2)."""
    rows = [CSV_HEADER] + list(rows)
    if PY2:
        output = io.BytesIO()
        rows = [[text_type(cell).encode("utf-8") for cell in row] for row in rows]
    else:
        output = io.StringIO()
    csv.writer(output).writerows(rows)
    return output.getvalue()


def csv_bytes(csv_text):
    """UTF-8 bytes with a BOM, so Excel opens the report with the right encoding."""
    if not isinstance(csv_text, bytes):
        csv_text = csv_text.encode("utf-8")
    return b"\xef\xbb\xbf" + csv_text


def _message_row(message):
    return [message] + [""] * (len(CSV_HEADER) - 1)


def scrape_pdf_links(pdf_source, workers=8):
    """Extract and check every link in a PDF, returning the CSV report as text."""
    try:
        links = extract_links(pdf_source)
    except Exception as e:
        return rows_to_csv([_message_row("Error reading PDF: {}".format(e))])

    if not links:
        return rows_to_csv([_message_row(NO_LINKS_MESSAGE)])

    return rows_to_csv(check_links(links, workers=workers))


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

    try:
        links = extract_links(args.pdf)
    except Exception as e:
        links, rows = [], [_message_row("Error reading PDF: {}".format(e))]
    else:
        rows = check_links(links, workers=args.workers) if links else [_message_row(NO_LINKS_MESSAGE)]

    out_path = args.output or report_filename(args.pdf)
    with open(out_path, "wb") as f:
        f.write(csv_bytes(rows_to_csv(rows)))

    broken = sum(1 for row in rows if row[5] == "Yes") if links else 0
    print("Checked {} link(s), {} broken. Report saved to {}".format(len(links), broken, out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
