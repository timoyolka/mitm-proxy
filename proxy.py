from cert import *
<<<<<<< HEAD
from gui import ProxyGUI
from collections import deque
import re
import threading
=======
from adblock import EasyListParser
import re
>>>>>>> b2d7ad00ddfa5c124555eed2c4fb4f48826050f9

# Logging setup
logging.basicConfig(level=logging.DEBUG)

# Constants
NOT_ALLOWED = b"HTTP/1.1 405 Method Not Allowed\r\n\r\n"
CONNECTION_ESTABLISHED = b"HTTP/1.1 200 Connection Established\r\n\r\n"

<<<<<<< HEAD
CLIENT_TO_SERVER = True
SERVER_TO_CLIENT = False
=======
>>>>>>> b2d7ad00ddfa5c124555eed2c4fb4f48826050f9

class AsyncProxy:
    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        self.host = host
        self.port = port
        self.cert_handler = CertHandler()
<<<<<<< HEAD
        self.traffic_log = deque(maxlen=1000)
        self.gui = ProxyGUI(start_proxy_fn=self.start_background)
=======
>>>>>>> b2d7ad00ddfa5c124555eed2c4fb4f48826050f9

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
<<<<<<< HEAD
                asyncio.create_task(self._forward_data(reader, target_writer, direction=CLIENT_TO_SERVER)),
                asyncio.create_task(self._forward_data(target_reader, writer, direction=SERVER_TO_CLIENT))
=======
                asyncio.create_task(self._forward_data(reader, target_writer)),
                asyncio.create_task(self._forward_data(target_reader, writer))
>>>>>>> b2d7ad00ddfa5c124555eed2c4fb4f48826050f9
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
<<<<<<< HEAD
                    
                    
    def _read_chunked_body(self, body: bytes):
        """
        Parse chunked transfer-encoded body.
        Returns (body, total_length) or (None, 0) if incomplete.
        """
        pos = 0
        full_body = b""

        while True:
            newline = body.find(b"\r\n", pos)
            if newline == -1:
                return None, 0

            chunk_size_line = body[pos:newline].decode(errors="ignore")
            try:
                chunk_size = int(chunk_size_line.strip(), 16)
            except ValueError:
                return None, 0

            pos = newline + 2
            if len(body) < pos + chunk_size + 2:
                return None, 0

            full_body += body[pos:pos + chunk_size]
            pos += chunk_size + 2  # Skip \r\n

            if chunk_size == 0:
                break

        return full_body, pos


    async def _extract_http_message(self, data: bytes):
        """
        Attempts to extract a full HTTP request/response.
        Returns (message, remaining_data, content_type) if complete,
        otherwise (None, data, None).
        """
        try:
            header_end = data.find(b"\r\n\r\n")
            if header_end == -1:
                return None, data, None  # wait for more data

            headers = data[:header_end + 4]
            lines = headers.decode(errors="ignore").split("\r\n")
            content_length = 0
            chunked = False
            content_type = ""

            for line in lines:
                if line.lower().startswith("content-length:"):
                    content_length = int(line.split(":", 1)[1].strip())
                elif line.lower().startswith("transfer-encoding:") and "chunked" in line.lower():
                    chunked = True
                elif line.lower().startswith("content-type:"):
                    content_type = line.split(":", 1)[1].strip().lower()

            body_start = header_end + 4
            if chunked:
                try:
                    body, total_len = self._read_chunked_body(data[body_start:])
                    if body is None:
                        return None, data, None
                    return data[:body_start + total_len], data[body_start + total_len:], content_type
                except Exception:
                    return None, data, None

            total_length = body_start + content_length
            if len(data) >= total_length:
                return data[:total_length], data[total_length:], content_type

            return None, data, None
        except Exception:
            return None, data, None


    def _is_text_content_type(self, content_type: str) -> bool:
        """Determine if the content type is textual and safe to decode."""
        if not content_type:
            return False
        return (
            content_type.startswith("text/") or
            "json" in content_type or
            "xml" in content_type or
            "javascript" in content_type
        )


    async def _forward_data(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, direction=""):
        """Forward full HTTP requests/responses with traffic inspection and logging."""
        try:
            buffer = b""

            while not reader.at_eof():
                chunk = await reader.read(65536)
                if not chunk:
                    break
                buffer += chunk

                while True:
                    message, remaining, content_type = await self._extract_http_message(buffer)
                    if message is None:
                        break  # need more data

                    buffer = remaining
                    is_text = self._is_text_content_type(content_type)

                    if is_text:
                        try:
                            text = message.decode('utf-8')
                        except UnicodeDecodeError:
                            text = message.decode('latin1')
                    else:
                        text = f"[binary content: {content_type or 'unknown'}]"

                    if direction:
                        if text.startswith(("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS")) or is_text:
                            self.traffic_log.append(("Request", text))
                            summary = text.splitlines()[0] if is_text else "Binary Request"
                            self.gui.after(0, self.gui.add_request, summary, text)

                    else:
                        self.traffic_log.append(("Response", text))
                        self.gui.after(0, self.gui.add_request, "Response", text)

                    writer.write(message)
                    await writer.drain()

        except Exception as e:
            logging.error(f"Error forwarding data ({direction}): {e}")
=======

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
>>>>>>> b2d7ad00ddfa5c124555eed2c4fb4f48826050f9
        finally:
            if writer:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass

<<<<<<< HEAD



=======
>>>>>>> b2d7ad00ddfa5c124555eed2c4fb4f48826050f9
    async def start(self):
        """Start the proxy server."""
        await self.initialize()
        server = await asyncio.start_server(self._handle_client, self.host, self.port)
        addr = server.sockets[0].getsockname()
        logging.info(f"Proxy server running on {addr[0]}:{addr[1]}")
        async with server:
            await server.serve_forever()
<<<<<<< HEAD
    
    
    def start_gui(self):
        """Start the GUI event loop."""
        self.gui.mainloop()
    
    
    def start_background(self):
        """Start the proxy server in a background thread (called by GUI button)."""
        threading.Thread(target=lambda: asyncio.run(self.start()), daemon=True).start()
=======
>>>>>>> b2d7ad00ddfa5c124555eed2c4fb4f48826050f9
