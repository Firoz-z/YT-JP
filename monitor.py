"""Pipeline health check — sends email alert when uploads are stale or the
pipeline reports an explicit failure.

Reads uploads.md to find the most recent upload date. If it is 2+ days old,
or if FAILURE_REASON is set (called from daily.yml on failure), an alert email
is sent via Gmail SMTP and the script exits with code 1.

Required GitHub secrets (add under Settings → Secrets → Actions):
    GMAIL_FROM          your Gmail address (e.g. you@gmail.com)
    GMAIL_APP_PASSWORD  Gmail App Password (not your normal password)
    ALERT_EMAIL         address to receive alerts (can be same as GMAIL_FROM)
"""
import os
import smtplib
import sys
from datetime import date, timedelta
from email.mime.text import MIMEText

UPLOAD_LOG = os.path.join(os.path.dirname(__file__), "uploads.md")
ACTIONS_URL = "https://github.com/ojas94/yt-jp/actions"


def _most_recent_upload_date() -> date | None:
    if not os.path.exists(UPLOAD_LOG):
        return None
    latest = None
    with open(UPLOAD_LOG, encoding="utf-8") as f:
        for line in f:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 5:
                continue
            cell = parts[1]
            if not (len(cell) >= 4 and cell[:4].isdigit()):
                continue
            try:
                d = date.fromisoformat(cell)
                if latest is None or d > latest:
                    latest = d
            except ValueError:
                continue
    return latest


def _send_email(subject: str, body: str) -> None:
    gmail_from   = os.environ.get("GMAIL_FROM", "").strip()
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    alert_to     = os.environ.get("ALERT_EMAIL", gmail_from).strip()

    if not gmail_from or not app_password:
        print(f"[monitor] No Gmail credentials — alert not sent.\nSubject: {subject}\n{body}")
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"]    = gmail_from
    msg["To"]      = alert_to

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(gmail_from, app_password)
        smtp.sendmail(gmail_from, alert_to, msg.as_string())
    print(f"[monitor] Alert sent to {alert_to}")


def main() -> None:
    failure_reason = os.environ.get("FAILURE_REASON", "").strip()
    issues: list[str] = []

    if failure_reason:
        issues.append(f"Pipeline step failed: {failure_reason}")

    latest = _most_recent_upload_date()
    today  = date.today()

    if latest is None:
        issues.append(
            "uploads.md is empty or missing — no videos have been uploaded yet "
            "or the file was not committed."
        )
    elif (today - latest).days >= 2:
        gap = (today - latest).days
        issues.append(
            f"No upload recorded in the last {gap} days. "
            f"Most recent entry: {latest.isoformat()}."
        )

    if not issues:
        print(f"[monitor] Health check passed — most recent upload: {latest}")
        return

    subject = "[YT-JP ALERT] Upload pipeline issue detected"
    body = (
        "The YT-JP pipeline health check has detected a problem:\n\n"
        + "\n".join(f"  • {i}" for i in issues)
        + f"\n\nReview the GitHub Actions logs:\n{ACTIONS_URL}\n"
    )
    _send_email(subject, body)
    sys.exit(1)


if __name__ == "__main__":
    main()
