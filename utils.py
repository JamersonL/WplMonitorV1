import os, subprocess
import csv
import base64
import mimetypes
import time
from email.utils import formatdate, make_msgid

def send_email_mail(html_body: str, subject: str, recipients: list, attachment_path: str, from_addr: str = None):
    """
    Sends one independent HTML email per recipient through the local MTA.

    Every recipient receives a separate message with an individual To header
    and Message-ID. A failure for one recipient does not prevent attempts to
    deliver to the remaining recipients.
    """
    if not recipients:
        raise ValueError("send_email_mail: recipients list is empty")

    if not from_addr:
        from_addr = "WPLatAm.TSO.Reports@worldpay.com"

    # Detect attachment content type and read the attachment only once.
    attach_name = os.path.basename(attachment_path) if attachment_path else None
    ctype, _ = mimetypes.guess_type(attach_name or "")
    if not ctype:
        ctype = "application/octet-stream"

    attachment_part = ""
    if attachment_path and os.path.isfile(attachment_path):
        with open(attachment_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")

        attachment_part = (
            "Content-Type: %s; name=\"%s\"\n"
            "Content-Transfer-Encoding: base64\n"
            "Content-Disposition: attachment; filename=\"%s\"\n\n"
            "%s\n"
        ) % (ctype, attach_name, attach_name, b64)

    cmd = ["/usr/sbin/sendmail", "-t", "-oi"]
    failures = []

    for recipient in recipients:
        recipient = recipient.strip()
        if not recipient:
            continue

        message_id = make_msgid()
        date_hdr = formatdate(localtime=True)
        boundary = "==BOUNDARY_%s_%s==" % (int(time.time() * 1000000), os.getpid())

        raw = (
            "From: %s\n"
            "To: %s\n"
            "Subject: %s\n"
            "Message-ID: %s\n"
            "Date: %s\n"
            "MIME-Version: 1.0\n"
            "Content-Type: multipart/mixed; boundary=\"%s\"\n"
            "\n"
            "--%s\n"
            "Content-Type: text/html; charset=\"utf-8\"\n"
            "Content-Transfer-Encoding: 8bit\n\n"
            "%s\n"
            "%s"
            "--%s--\n"
        ) % (
            from_addr, recipient, subject, message_id, date_hdr, boundary,
            boundary, html_body, attachment_part, boundary
        )

        try:
            subprocess.run(
                cmd,
                input=raw.encode("utf-8", errors="replace"),
                check=True
            )
        except subprocess.CalledProcessError as exc:
            failures.append("%s: %s" % (recipient, exc))
        except OSError as exc:
            failures.append("%s: %s" % (recipient, exc))

    if failures:
        raise RuntimeError(
            "send_email_mail: failed to send to: " + "; ".join(failures)
        )

def send_email_mutt(html_body, subject, recipients, attachment_path):
    """
    Sends email using mutt:
      - html_body: string for inline body
      - subject: email subject
      - recipients: list of email addresses
      - attachment_path: path to attach the full HTML report
    """
    # Write the HTML body to a temp file
    tmp_body_file = "/tmp/email_body.html"
    with open(tmp_body_file, "w", encoding="utf-8") as f:
        f.write(html_body)

    cmd = [
        "mutt",
        "-e", "set content_type=text/html",
        "-s", subject,
        "-a", attachment_path,
        "--"
    ] + recipients

    FNULL = open(os.devnull, 'w')
    subprocess.run(cmd, input=open(tmp_body_file, "rb").read(), check=True, stdout=FNULL, stderr=subprocess.STDOUT)


def fmt_int(n):
    return f"{int(n):,}"

def fmt_money(code, amount):
    """
    Simple currency symbol mapping; falls back to the code if unknown.
    Adjust or extend as needed for your portfolio.
    """
    sym = {
        "BRL": "R$",
        "USD": "$",
        "EUR": "€",
        "ARS": "ARS$",
        "MXN": "MXN $",
        "COP": "COP $",
        "CLP": "CLP $",
        "PEN": "S/",
        "UNK": ""
    }.get(code, "")
    # Example: "BRL R$ 12,345.67"
    return f"{sym} {float(amount):,.2f}"

def parse_clients_file(path: str):
    clients = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "," in line or "'" in line:
                row = next(csv.reader([line], delimiter=",", quotechar="'", skipinitialspace=True))
                aliases = [a.strip() for a in row if a and a.strip()]
            else:
                aliases = [line]
            uniq = []
            for a in aliases:
                token = a.strip()
                if len(token) >= 2 and token[0] == token[-1] == "'":
                    token = token[1:-1]
                if token and token not in uniq:
                    uniq.append(token)
            if uniq:
                clients.append(uniq)
    return clients

def slugify(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in ("-", "_")).strip("_") or "client"
