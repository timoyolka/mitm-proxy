import asyncio
import sys
from pathlib import Path
from proxy import AsyncProxy

HOST = "0.0.0.0"
PORT = 8080
CERT_PATH = Path("certs/mitm_cert.crt").resolve()
KEY_PATH = Path("certs/mitm_cert.key").resolve()

def main():
    proxy = AsyncProxy(host=HOST, port=PORT)
    asyncio.run(proxy.start())

if __name__ == "__main__":
    main()