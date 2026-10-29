#!/usr/bin/env python3
"""
Personal Second Brain - Secure Local Email Client (email_client.py)
===================================================================
Enables the Second Brain and AI agents to send emails securely via SMTP
using a dedicated App Password (e.g. Gmail / Outlook / custom domain).

Security & Privacy Guarantees:
- Never requires or stores your main account password (uses 16-char App Password).
- Loads credentials from local environment variables or private .env file (git-ignored).
- Masks credentials in logs and outputs.
- Requires explicit user confirmation (--confirm) to prevent accidental sending.
- Full UTF-8 support for Hungarian and Polish text formatting.
"""

from __future__ import annotations

import argparse
import json
import os
import smtplib
import sys
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, Optional

# Load local .env if available
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ENV_FILE)
except ImportError:
    pass


class EmailClient:
    """Manages secure outbound SMTP communications."""

    DEFAULT_PROVIDERS = {
        "gmail": {"host": "smtp.gmail.com", "port": 587, "tls": True},
        "outlook": {"host": "smtp-mail.outlook.com", "port": 587, "tls": True},
        "hotmail": {"host": "smtp-mail.outlook.com", "port": 587, "tls": True},
        "yahoo": {"host": "smtp.mail.yahoo.com", "port": 587, "tls": True},
    }

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = True,
    ):
        self.user = user or os.getenv("SMTP_USER") or os.getenv("EMAIL_USER") or ""
        self.password = password or os.getenv("SMTP_PASS") or os.getenv("EMAIL_PASS") or ""
        
        # Auto-detect host from user email if not explicitly provided
        detected_host = "smtp.gmail.com"
        detected_port = 587
        if self.user and "@" in self.user:
            domain = self.user.split("@")[1].lower()
            for key, prov in self.DEFAULT_PROVIDERS.items():
                if key in domain:
                    detected_host = prov["host"]
                    detected_port = prov["port"]
                    break

        self.host = host or os.getenv("SMTP_HOST") or detected_host
        self.port = int(port or os.getenv("SMTP_PORT") or detected_port)
        self.use_tls = use_tls if use_tls is not None else (os.getenv("SMTP_USE_TLS", "true").lower() == "true")

    def is_configured(self) -> bool:
        """Checks if minimum SMTP credentials are present."""
        return bool(self.user and self.password and self.host)

    def mask_email(self, email: str) -> str:
        """Masks an email for safe display."""
        if not email or "@" not in email:
            return "[NOT SET]"
        parts = email.split("@")
        name = parts[0]
        if len(name) <= 2:
            masked_name = name[0] + "*"
        else:
            masked_name = name[0] + "*" * (len(name) - 2) + name[-1]
        return f"{masked_name}@{parts[1]}"

    def get_status(self) -> Dict[str, Any]:
        """Returns non-sensitive status info for agent or human inspection."""
        return {
            "configured": self.is_configured(),
            "smtp_host": self.host,
            "smtp_port": self.port,
            "smtp_user_masked": self.mask_email(self.user),
            "smtp_pass_set": bool(self.password),
            "smtp_pass_length": len(self.password) if self.password else 0,
            "use_tls": self.use_tls,
            "env_file_found": ENV_FILE.exists(),
        }

    def send_email(
        self,
        to_address: str,
        subject: str,
        body: str,
        confirmed: bool = False,
    ) -> Dict[str, Any]:
        """
        Sends an email via SMTP.
        Requires confirmed=True to prevent accidental transmission.
        """
        if not self.is_configured():
            raise ValueError(
                "EmailClient is not configured.\n"
                f"Please create {ENV_FILE} or set environment variables: SMTP_USER and SMTP_PASS."
            )

        if not confirmed:
            raise PermissionError(
                f"SAFETY GUARD: Email to '{to_address}' with subject '{subject}' requires explicit confirmation.\n"
                f"Pass --confirm flag or confirm interactively before sending."
            )

        # Build MIME message with proper UTF-8 headers
        msg = MIMEMultipart("alternative")
        msg["From"] = self.user
        msg["To"] = to_address
        msg["Subject"] = Header(subject, "utf-8").encode()
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Connect and send
        try:
            if self.port == 465:
                # SSL direct connection
                server = smtplib.SMTP_SSL(self.host, self.port, timeout=20)
            else:
                # TLS connection (default: 587)
                server = smtplib.SMTP(self.host, self.port, timeout=20)
                if self.use_tls:
                    server.starttls()

            server.login(self.user, self.password)
            server.sendmail(self.user, [to_address], msg.as_string())
            server.quit()
        except smtplib.SMTPAuthenticationError as auth_err:
            raise RuntimeError(
                f"SMTP Authentication Failed for {self.mask_email(self.user)}: {auth_err}\n"
                "Tip: If using Gmail, you MUST use an App Password (16 characters) generated under 2-Step Verification, not your main password."
            ) from auth_err
        except Exception as e:
            raise RuntimeError(f"SMTP Transmission Failed: {e}") from e

        return {
            "success": True,
            "to": to_address,
            "subject": subject,
            "from": self.user,
        }


def main():
    shared_parser = argparse.ArgumentParser(add_help=False)
    shared_parser.add_argument("--json", action="store_true", help="Output machine-readable JSON.")

    parser = argparse.ArgumentParser(
        description="Personal Second Brain - Secure Local Email Client",
        parents=[shared_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Email command")

    # Status
    subparsers.add_parser("status", parents=[shared_parser], help="Check SMTP configuration and readiness.")

    # Send
    send_p = subparsers.add_parser("send", parents=[shared_parser], help="Send an email to a recipient.")
    send_p.add_argument("--to", type=str, required=True, help="Recipient email address.")
    send_p.add_argument("--subject", type=str, required=True, help="Email subject line.")
    send_p.add_argument("--body", type=str, default=None, help="Email body text.")
    send_p.add_argument("--body-file", type=str, default=None, help="Path to text/markdown file containing body.")
    send_p.add_argument("--confirm", action="store_true", help="Explicit user confirmation token to execute transmission.")

    # Test
    test_p = subparsers.add_parser("test", parents=[shared_parser], help="Send a self-test email to your own address.")
    test_p.add_argument("--confirm", action="store_true", help="Confirm sending the test email.")

    args = parser.parse_args()
    client = EmailClient()

    if not args.command or args.command == "status":
        status = client.get_status()
        if args.json:
            print(json.dumps(status, indent=2))
        else:
            print("=" * 60)
            print("  SECOND BRAIN - EMAIL CLIENT STATUS")
            print("=" * 60)
            print(f"Status:          {'CONFIGURED (Ready)' if status['configured'] else 'NOT CONFIGURED (Missing SMTP credentials)'}")
            print(f"SMTP Host:       {status['smtp_host']}:{status['smtp_port']}")
            print(f"Account:         {status['smtp_user_masked']}")
            print(f"Password:        {'Set (' + str(status['smtp_pass_length']) + ' chars)' if status['smtp_pass_set'] else 'Missing'}")
            print(f"TLS Active:      {status['use_tls']}")
            print(f".env File:       {'Found at ' + str(ENV_FILE) if status['env_file_found'] else 'Not found (Create ' + str(ENV_FILE) + ')'}")
            print("=" * 60)

    elif args.command == "send":
        body = args.body or ""
        if args.body_file:
            bf = Path(args.body_file)
            if bf.exists():
                body = bf.read_text(encoding="utf-8")
            else:
                print(f"Error: Body file '{args.body_file}' not found.")
                sys.exit(1)

        if not body:
            print("Error: Empty email body. Provide --body or --body-file.")
            sys.exit(1)

        confirmed = args.confirm
        if not confirmed and sys.stdin.isatty():
            print("\n" + "=" * 60)
            print(f"To:      {args.to}")
            print(f"Subject: {args.subject}")
            print("-" * 60)
            print(body[:300] + ("..." if len(body) > 300 else ""))
            print("=" * 60)
            ans = input("Send this email now? [y/N]: ")
            confirmed = (ans.strip().lower() in ("y", "yes"))

        try:
            res = client.send_email(
                to_address=args.to,
                subject=args.subject,
                body=body,
                confirmed=confirmed,
            )
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                print(f"[+] Email successfully sent to '{args.to}'.")
        except Exception as e:
            if args.json:
                print(json.dumps({"error": str(e)}, indent=2))
            else:
                print(f"Error: {e}")
            sys.exit(1)

    elif args.command == "test":
        if not client.is_configured():
            print(f"Error: Client is not configured. Please create {ENV_FILE} with your SMTP credentials.")
            sys.exit(1)

        confirmed = args.confirm
        if not confirmed and sys.stdin.isatty():
            ans = input(f"Send a self-test email to your account ({client.mask_email(client.user)})? [y/N]: ")
            confirmed = (ans.strip().lower() in ("y", "yes"))

        try:
            res = client.send_email(
                to_address=client.user,
                subject="Second Brain - SMTP Self-Test",
                body="Hello from your Second Brain!\n\nYour secure SMTP email client is properly configured and operational.",
                confirmed=confirmed,
            )
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                print(f"[+] Test email successfully sent to your address ({client.user}). Check your inbox!")
        except Exception as e:
            if args.json:
                print(json.dumps({"error": str(e)}, indent=2))
            else:
                print(f"Error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
