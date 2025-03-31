from cert import *
from adblock import EasyListParser
import re

# Logging setup
logging.basicConfig(level=logging.DEBUG)

# Constants
NOT_ALLOWED = b"HTTP/1.1 405 Method Not Allowed\r\n\r\n"
CONNECTION_ESTABLISHED = b"HTTP/1.1 200 Connection Established\r\n\r\n"


class AsyncProxy:
    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        self.host = host
        self.port = port
        self.cert_handler = CertHandler()

    async def initialize(self):
        """Initialize the proxy server."""
        await self.cert_handler.initialize()

    async def parse_connect_request(self, request: str):
        """Parse a CONNECT request."""
        match = re.match(r"^CONNECT\s+([\w.-]+):(\d+)\s+HTTP/\d\.\d", request)
        if not match:
            raise ValueError(f"Malformed CONNECT request: {request}")
            
        target_host, target_port = match.groups()
        return target_host, int(target_port)

    async def _setup_client_ssl(self, writer: asyncio.StreamWriter, cert_path: str, key_path: str):
        """Set up SSL/TLS for client-to-proxy communication."""
        ssl_context_server = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context_server.load_cert_chain(certfile=cert_path, keyfile=key_path)
        await writer.start_tls(sslcontext=ssl_context_server)

    async def _setup_target_ssl(self, target_host: str, target_port: int) -> tuple:
        """Set up SSL/TLS for proxy-to-target communication."""
        ssl_context_client = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ssl_context_client.verify_mode = ssl.CERT_REQUIRED
        ssl_context_client.check_hostname = True
        target_reader, target_writer = await asyncio.open_connection(
            host=target_host,
            port=target_port,
            ssl=ssl_context_client,
            server_hostname=target_host
        )
        return target_reader, target_writer

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle incoming client connections."""
        cert_path = None
        key_path = None
        try:
            # Read the initial CONNECT request
            request = await reader.readuntil(b"\r\n\r\n")
            target_host, target_port = await self.parse_connect_request(request.decode())
            
            # Generate a temporary certificate for the target host
            sans = [target_host]
            key_path, cert_path = await self.cert_handler.generate_and_save_temp_cert(target_host, sans)
            
            # Notify the client that the connection is established
            writer.write(CONNECTION_ESTABLISHED)
            logging.info(f"Connection established with {target_host}:{target_port}")
            await writer.drain()
            
            # Set up SSL/TLS for client-to-proxy communication
            await self._setup_client_ssl(writer, cert_path, key_path)
            
            # Connect to the target server
            target_reader, target_writer = await self._setup_target_ssl(target_host, target_port)
            
            # Forward data between the client and the target server
            forward_tasks = [
                asyncio.create_task(self._forward_data(reader, target_writer)),
                asyncio.create_task(self._forward_data(target_reader, writer))
            ]
            await asyncio.gather(*forward_tasks)
        except Exception as e:
            logging.error(f"Error handling client: {e}")
        finally:
            # Clean up resources
            if writer:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
            if target_writer:
                try:
                    await target_writer.wait_closed()
                except Exception:
                    pass
              
            # Clean up temporary files
            if cert_path and os.path.exists(cert_path):
                os.unlink(cert_path)
            if key_path and os.path.exists(key_path):
                os.unlink(key_path)

    async def _forward_data(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Forward data between two streams."""
        try:
            while not reader.at_eof():
                data = await reader.read(65536)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except Exception as e:
            logging.error(f"Error forwarding data: {e}")
        finally:
            if writer:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass

    async def start(self):
        """Start the proxy server."""
        await self.initialize()
        server = await asyncio.start_server(self._handle_client, self.host, self.port)
        addr = server.sockets[0].getsockname()
        logging.info(f"Proxy server running on {addr[0]}:{addr[1]}")
        async with server:
            await server.serve_forever()
