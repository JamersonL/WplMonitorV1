import os, subprocess
import csv
import base64
import mimetypes
import time
from email.utils import formatdate, make_msgid

def send_email_mail(html_body: str, subject: str, recipients: list, attachment_path: str, from_addr: str = None):
    """
    Sends an email with HTML body and one attachment by piping a MIME message
    to the local MTA (sendmail). No SMTP login required.

    Parameters
    ----------
    html_body : str
        The HTML content to appear inline in the email body.
    subject : str
        Email subject.
    recipients : list[str]
        List of recipient email addresses.
    attachment_path : str
        Path to the file to attach (e.g., your full HTML report).
    from_addr : str, optional
        Envelope/sender address. If not provided, uses $EMAIL_FROM or 'noreply@localhost'.
    """

    if not recipients:
        raise ValueError("send_email_mail: recipients list is empty")

    if not from_addr:
        from_addr = "WPLatAm.TSO.Reports@worldpay.com"

    to_header = ", ".join(recipients)
    message_id = make_msgid()  # RFC 5322 compliant
    date_hdr   = formatdate(localtime=True)
    boundary   = f"==BOUNDARY_{int(time.time())}_{os.getpid()}=="

    # Detect attachment content type and name
    attach_name = os.path.basename(attachment_path) if attachment_path else None
    ctype, _ = mimetypes.guess_type(attach_name or "")
    if not ctype:
        ctype = "application/octet-stream"

    # Read and base64-encode the attachment (if any)
    attachment_part = ""
    if attachment_path and os.path.isfile(attachment_path):
        with open(attachment_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")

        attachment_part = (
            f"\n--{boundary}\n"
            f"Content-Type: {ctype}; name=\"{attach_name}\"\n"
            f"Content-Transfer-Encoding: base64\n"
            f"Content-Disposition: attachment; filename=\"{attach_name}\"\n\n"
            f"{b64}\n"
        )

    # Build full MIME message
    # NOTE: first part is text/html; adjust charset if needed
    raw = (
        f"From: {from_addr}\n"
        f"To: {to_header}\n"
        f"Subject: {subject}\n"
        f"Message-ID: {message_id}\n"
        f"Date: {date_hdr}\n"
        f"MIME-Version: 1.0\n"
        f"Content-Type: multipart/mixed; boundary=\"{boundary}\"\n"
        f"\n"
        f"--{boundary}\n"
        f"Content-Type: text/html; charset=\"utf-8\"\n"
        f"Content-Transfer-Encoding: 8bit\n\n"
        f"{html_body}\n"
        f"{attachment_part}"
        f"--{boundary}--\n"
    ).encode("utf-8", errors="replace")

    # Pipe to local MTA
    # -t : read recipients from headers (To/Cc/Bcc)
    # -oi: dot-stuffing off (don’t treat lone '.' as message end)
    cmd = ["/usr/sbin/sendmail", "-t", "-oi"]
    subprocess.run(cmd, input=raw, check=True)

def send_email_mutt(html_body, subject, recipients, attachment_path):
    """
    Sends email using mutt:
      - html_body: string with HTML content for inline body
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
