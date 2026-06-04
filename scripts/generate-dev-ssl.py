#!/usr/bin/env python3
"""Gera certificado autoassinado para HTTPS local / Radmin (microfone no navegador)."""

from __future__ import annotations

import argparse
import ipaddress
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SSL_DIR = PROJECT_ROOT / "data" / "dev-ssl"
CERT_FILE = SSL_DIR / "radiopoggers.crt"
KEY_FILE = SSL_DIR / "radiopoggers.key"
HOSTS_FILE = PROJECT_ROOT / "data" / "dev-access-hosts.txt"
CONFIG_JS = PROJECT_ROOT / "frontend" / "config.js"

OPENSSL_CANDIDATES = (
    "openssl",
    r"C:\Program Files\Git\usr\bin\openssl.exe",
    r"C:\Program Files (x86)\Git\usr\bin\openssl.exe",
)


def find_openssl() -> str | None:
    for candidate in OPENSSL_CANDIDATES:
        resolved = shutil.which(candidate) if "\\" not in candidate else candidate
        if resolved and Path(resolved).exists():
            return resolved
    return None


def detect_lan_ip() -> str | None:
    try:
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
        finally:
            sock.close()
        if ip.startswith(("192.168.", "10.")) or ip.startswith("172."):
            octets = ip.split(".")
            if len(octets) == 4 and ip.startswith("172."):
                second = int(octets[1])
                if second < 16 or second > 31:
                    return None
            return ip
    except OSError:
        return None
    return None


def load_config_host() -> str | None:
    if not CONFIG_JS.exists():
        return None
    match = re.search(r'azuracastBaseUrl:\s*"https?://([^"/]+)"', CONFIG_JS.read_text(encoding="utf-8"))
    if not match:
        return None
    host = match.group(1).strip()
    return host or None


def load_extra_hosts() -> list[str]:
    hosts: list[str] = []
    if not HOSTS_FILE.exists():
        return hosts
    for line in HOSTS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        hosts.append(line)
    return hosts


def normalize_hosts(raw_hosts: list[str]) -> list[str]:
    merged: list[str] = ["localhost", "127.0.0.1"]
    for value in raw_hosts:
        host = str(value or "").strip()
        if not host or host in merged:
            continue
        merged.append(host)
    return merged


def collect_default_hosts(extra: list[str] | None = None) -> list[str]:
    hosts = ["localhost", "127.0.0.1"]
    lan_ip = detect_lan_ip()
    if lan_ip:
        hosts.append(lan_ip)
    config_host = load_config_host()
    if config_host:
        hosts.append(config_host)
    hosts.extend(load_extra_hosts())
    if extra:
        hosts.extend(extra)
    return normalize_hosts(hosts)


def build_san(dns_names: list[str]) -> str:
    parts: list[str] = []
    for name in dns_names:
        name = name.strip()
        if not name:
            continue
        try:
            ipaddress.ip_address(name)
        except ValueError:
            parts.append(f"DNS:{name}")
        else:
            parts.append(f"IP:{name}")
    return ",".join(parts)


def read_cert_sans(cert_path: Path) -> set[str]:
    if not cert_path.exists():
        return set()

    try:
        from cryptography import x509

        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        try:
            ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        except x509.ExtensionNotFound:
            return set()
        values: set[str] = set()
        for name in ext.value:
            if isinstance(name, x509.DNSName):
                values.add(str(name.value))
            elif isinstance(name, x509.IPAddress):
                values.add(str(name.value))
        return values
    except ImportError:
        pass

    openssl = find_openssl()
    if not openssl:
        return set()

    result = subprocess.run(
        [openssl, "x509", "-in", str(cert_path), "-noout", "-ext", "subjectAltName"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return set()

    values: set[str] = set()
    for match in re.finditer(r"DNS:([^,\s]+)", result.stdout):
        values.add(match.group(1))
    for match in re.finditer(r"IP Address:([^,\s]+)", result.stdout):
        values.add(match.group(1))
    return values


def cert_covers_hosts(required_hosts: list[str]) -> bool:
    if not CERT_FILE.exists() or not KEY_FILE.exists():
        return False
    sans = read_cert_sans(CERT_FILE)
    if not sans:
        return False
    return all(host in sans for host in required_hosts)


def remove_existing_cert() -> None:
    for path in (CERT_FILE, KEY_FILE):
        if path.exists():
            path.unlink()


def generate_with_openssl(openssl: str, dns_names: list[str]) -> bool:
    SSL_DIR.mkdir(parents=True, exist_ok=True)
    san = build_san(dns_names)
    cmd = [
        openssl,
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-keyout",
        str(KEY_FILE),
        "-out",
        str(CERT_FILE),
        "-days",
        "825",
        "-subj",
        "/CN=RadioPoggersDev",
        "-addext",
        f"subjectAltName={san}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr or result.stdout, file=sys.stderr)
        return False
    return CERT_FILE.exists() and KEY_FILE.exists()


def generate_with_cryptography(dns_names: list[str]) -> bool:
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError:
        return False

    SSL_DIR.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "RadioPoggersDev")])

    alt_names: list[x509.GeneralName] = []
    for name in dns_names:
        name = name.strip()
        if not name:
            continue
        try:
            alt_names.append(x509.IPAddress(ipaddress.ip_address(name)))
        except ValueError:
            alt_names.append(x509.DNSName(name))

    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        .add_extension(
            x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    KEY_FILE.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    CERT_FILE.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return True


def generate_cert(hosts: list[str]) -> bool:
    hosts = normalize_hosts(hosts)
    remove_existing_cert()

    openssl = find_openssl()
    if openssl and generate_with_openssl(openssl, hosts):
        print(f"Certificado dev gerado com OpenSSL (SAN: {', '.join(hosts)})")
        return True

    if generate_with_cryptography(hosts):
        print(f"Certificado dev gerado com cryptography (SAN: {', '.join(hosts)})")
        return True

    print(
        "Nao foi possivel gerar PEM. Instale Git for Windows (openssl) ou: pip install cryptography",
        file=sys.stderr,
    )
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Certificado HTTPS dev RadioPoggers")
    parser.add_argument("--ensure", action="store_true", help="Regenera se faltar algum host no SAN")
    parser.add_argument("--force", action="store_true", help="Regenera sempre")
    parser.add_argument(
        "--hosts",
        default="",
        help="Hosts extras separados por virgula (alem de config.js e dev-access-hosts.txt)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    extra = [part.strip() for part in args.hosts.split(",") if part.strip()]
    required_hosts = collect_default_hosts(extra)

    if not args.force:
        if not args.ensure and cert_covers_hosts(required_hosts):
            print(f"Certificado dev OK em {SSL_DIR} (SAN: {', '.join(sorted(read_cert_sans(CERT_FILE)))})")
            return 0
        if args.ensure and cert_covers_hosts(required_hosts):
            print(f"Certificado dev OK em {SSL_DIR}")
            return 0

    if CERT_FILE.exists() and not cert_covers_hosts(required_hosts):
        missing = [host for host in required_hosts if host not in read_cert_sans(CERT_FILE)]
        print(f"Regenerando certificado — faltam no SAN: {', '.join(missing)}")

    if not generate_cert(required_hosts):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
