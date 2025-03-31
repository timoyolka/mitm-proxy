import asyncio
import ssl
import logging
from pathlib import Path
from typing import Optional, Tuple
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509 import ExtendedKeyUsageOID, NameOID, DNSName
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
from cryptography import x509
from cryptography.hazmat.primitives import hashes
import datetime
import io
import tempfile
import os

# Default expiry durations for certificates
CA_EXPIRY = datetime.timedelta(days=10 * 365)
CERT_EXPIRY = datetime.timedelta(days=365)

CA_CERT_PATH = "certs/mitm_cert.crt"
CA_KEY_PATH = "certs/mitm_cert.key"
TEMP_CERT_DIR = "temp_certs"

os.makedirs(TEMP_CERT_DIR, exist_ok=True)


class CertStore:
    """
    In-memory certificate store for managing certificates.
    """
    def __init__(self, default_privatekey: rsa.RSAPrivateKey, default_ca: x509.Certificate):
        self.default_privatekey = default_privatekey
        self.default_ca = default_ca
        self.certs = {}
        self.lock = asyncio.Lock()

    async def get_cert(self, commonname: str, sans: list) -> x509.Certificate:
        """
        Retrieve or generate a certificate for the given CN and SANs asynchronously.
        """
        async with self.lock:
            key = (commonname, tuple(sans))
            if key in self.certs:
                return self.certs[key]

            # Generate a new certificate if not found
            cert = await dummy_cert_async(
                self.default_privatekey,
                self.default_ca,
                commonname,
                sans,
            )
            self.certs[key] = cert
            return cert


async def create_ca_async(organization: str, cn: str, key_size: int) -> Tuple[rsa.RSAPrivateKey, x509.Certificate]:
    """
    Asynchronously create a Certificate Authority (CA) certificate.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, cn),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
    ])
    builder = x509.CertificateBuilder()
    builder = builder.serial_number(x509.random_serial_number())
    builder = builder.subject_name(name)
    builder = builder.not_valid_before(now - datetime.timedelta(days=2))
    builder = builder.not_valid_after(now + CA_EXPIRY)
    builder = builder.issuer_name(name)
    builder = builder.public_key(private_key.public_key())
    builder = builder.add_extension(
        x509.BasicConstraints(ca=True, path_length=None), critical=True
    )
    builder = builder.add_extension(
        x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False
    )
    cert = builder.sign(private_key=private_key, algorithm=hashes.SHA256())
    return private_key, cert


async def dummy_cert_async(
    privkey: rsa.RSAPrivateKey,
    cacert,
    commonname: str,
    sans: list,
) -> x509.Certificate:
    """
    Asynchronously generate a dummy certificate signed by the CA.
    """
    builder = x509.CertificateBuilder()
    builder = builder.issuer_name(cacert.subject)
    builder = builder.add_extension(
        x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False
    )
    builder = builder.public_key(privkey.public_key())
    now = datetime.datetime.now(datetime.timezone.utc)
    builder = builder.not_valid_before(now - datetime.timedelta(days=2))
    builder = builder.not_valid_after(now + CERT_EXPIRY)
    subject = [x509.NameAttribute(NameOID.COMMON_NAME, commonname)]
    builder = builder.subject_name(x509.Name(subject))
    builder = builder.serial_number(x509.random_serial_number())
    builder = builder.add_extension(
        x509.SubjectAlternativeName([DNSName(san) for san in sans]),
        critical=False,
    )
    cert = builder.sign(private_key=privkey, algorithm=hashes.SHA256())
    return cert
    
    
    
class CertHandler:
    def __init__(self, cert_path: str = CA_CERT_PATH, key_path: str = CA_KEY_PATH):
        self.cert_path = Path(cert_path).resolve()
        self.key_path = Path(key_path).resolve()
        self.cert_store = None

    async def _load_existing_ca_cert(self) -> (rsa.RSAPrivateKey, x509.Certificate):
        """Load existing CA certificate and private key."""
        with open(self.cert_path, "rb") as cert_file:
            ca_cert_data = cert_file.read()
        with open(self.key_path, "rb") as key_file:
            ca_key_data = key_file.read()
        ca_cert = x509.load_pem_x509_certificate(ca_cert_data)
        private_key = serialization.load_pem_private_key(ca_key_data, None)
        return private_key, ca_cert

    async def _save_cert_to_file(self, private_key: rsa.RSAPrivateKey, ca_cert: x509.Certificate):
        """Save CA certificate and private key to files."""
        os.makedirs(self.cert_path.parent, exist_ok=True)
        with open(self.cert_path, "wb") as cert_file:
            cert_file.write(ca_cert.public_bytes(Encoding.PEM))
        with open(self.key_path, "wb") as key_file:
            key_file.write(private_key.private_bytes(
                Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()
            ))

    async def _generate_new_ca_cert(self):
        """Generate a new CA certificate and private key."""
        private_key, ca_cert = await create_ca_async("MyProxy CA", "MyProxy Root CA", 2048)
        await self._save_cert_to_file(private_key, ca_cert)
        return private_key, ca_cert

    async def initialize(self):
        """Initialize the Certificate Authority (CA) and CertStore."""
        if not self.cert_path.exists() or not self.key_path.exists():
            private_key, ca_cert = await self._generate_new_ca_cert()
            logging.info(f"New certificate and private key saved to {self.cert_path} and {self.key_path}")
        else:
            private_key, ca_cert = await self._load_existing_ca_cert()
            logging.info(f"Loaded existing certificate and private key from {self.cert_path} and {self.key_path}")
        # Initialize CertStore
        self.cert_store = CertStore(private_key, ca_cert)

    async def generate_and_save_temp_cert(self, target_host: str, sans: list) -> (str, str):
        """Generate and save a temporary certificate for the target host."""
        cert = await self.cert_store.get_cert(target_host, sans)
        cert_pem = cert.public_bytes(Encoding.PEM)
        key_pem = self.cert_store.default_privatekey.private_bytes(
            Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()
        )
        with tempfile.NamedTemporaryFile(delete=False, dir=TEMP_CERT_DIR) as cert_file:
            cert_file.write(cert_pem)
            cert_path = cert_file.name
        with tempfile.NamedTemporaryFile(delete=False, dir=TEMP_CERT_DIR) as key_file:
            key_file.write(key_pem)
            key_path = key_file.name
        return key_path, cert_path
