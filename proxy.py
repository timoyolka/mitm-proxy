from cert import *
from gui import ProxyGUI
from collections import deque
from http import HTTPMessageParser
import re
import brotli
import threading
import logging
import asyncio
import ssl
import os
import time
from datetime import datetime

# Logging setup
logging.basicConfig(level=logging.DEBUG)

# Constants
NOT_ALLOWED = b"HTTP/1.1 405 Method Not Allowed\r\n\r\n"
CONNECTION_ESTABLISHED = b"HTTP/1.1 200 Connection Established\r\n\r\n"

CLIENT_TO_SERVER = True
SERVER_TO_CLIENT = False

class AsyncProxy:
    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        self.host = host
        self.port = port
        self.cert_handler = CertHandler()
        self.traffic_log = deque(maxlen=1000)
        self.gui = ProxyGUI(start_proxy_fn=self.start_background, stop_proxy_fn=self.stop_proxy)
        self.packet_counter = 0
        
        self.server = None
        self.loop = None
        
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
        target_writer = None
        
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
                asyncio.create_task(self._forward_data(reader, target_writer, direction=CLIENT_TO_SERVER)),
                asyncio.create_task(self._forward_data(target_reader, writer, direction=SERVER_TO_CLIENT))
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
                target_writer.close()
                try:
                    await target_writer.wait_closed()
                except Exception:
                    pass
              
            # Clean up temporary files
            if cert_path and os.path.exists(cert_path):
                os.unlink(cert_path)
            if key_path and os.path.exists(key_path):
                os.unlink(key_path)

    def _is_text_content_type(self, content_type: str) -> bool:
        """Determine if the content type indicates human-readable text."""
        if not content_type:
            return False

        content_type = content_type.lower()

        # Common text-like content types
        text_types = [
            "text/",
            "application/json",
            "application/javascript",
            "application/xml",
            "application/xhtml+xml",
            "application/x-www-form-urlencoded",
            "application/sql",
            "application/graphql"
        ]

        return any(content_type.startswith(tt) or tt in content_type for tt in text_types)
        
    def _unchunk_body(self, body: bytes) -> bytes:
        """Manually decode chunked HTTP body."""
        result = b""
        while body:
            match = re.match(rb"^([0-9A-Fa-f]+)\r\n", body)
            if not match:
                break
            length = int(match.group(1), 16)
            start = match.end()
            end = start + length
            result += body[start:end]
            body = body[end + 2:]  # skip \r\n after chunk
        return result


    async def _forward_data(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, direction: bool):
        """Continuously forward data between client and server, with optional HTTP logging."""
        parser = HTTPMessageParser(is_request=direction)
        buffer = bytearray()

        try:
            while not reader.at_eof():
                chunk = await reader.read(65536)
                if not chunk:
                    break

                writer.write(chunk)
                await writer.drain()
                buffer.extend(chunk)

                try:
                    parser.feed(chunk)
                except Exception as e:
                    logging.debug(f"Parser error (non-fatal): {e}")
                    continue

                if parser.completed:
                    try:
                        message, content_type, remaining = parser.get_full_message_and_remaining(buffer)
                        await self._handle_complete_message(
                            message=message,
                            content_type=content_type,
                            parser=parser,
                            direction=direction,
                            writer=writer
                        )
                        parser.reset_parser()
                        buffer = bytearray(remaining)
                    except Exception as e:
                        logging.error(f"Could not process complete message: {e}")
                        parser.reset_parser()
                        buffer.clear()

        except Exception as e:
            logging.error(f"Error forwarding data ({'Request' if direction else 'Response'}): {e}")
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass


    def _decode_body(self, headers: bytes, body: bytes) -> bytes:
        """Decode body with content-encoding and transfer-encoding headers."""
        if b"transfer-encoding: chunked" in headers.lower():
            try:
                body = self._unchunk_body(body)
            except Exception as e:
                logging.warning(f"Failed to unchunk body: {e}")
                body = b"[chunked decode failed]"

        if b"content-encoding: br" in headers.lower():
            try:
                body = brotli.decompress(body)
            except brotli.error as e:
                logging.warning(f"Brotli decompression failed: {e}")
                body = b"[brotli decompression failed]"

        return body


    def _format_http_message(self, headers: bytes, body: bytes, content_type: str) -> tuple[str, str]:
        """Return formatted full HTTP message text and summary line."""
        is_text = self._is_text_content_type(content_type)
        if is_text:
            try:
                text_body = body.decode('utf-8')
            except UnicodeDecodeError:
                text_body = body.decode('latin1')
            text = headers.decode('latin1') + "\r\n\r\n" + text_body
        else:
            preview = body[:64].hex() + ("..." if len(body) > 64 else "")
            text = headers.decode('latin1', errors='replace') + f"\r\n\r\n[binary content ({content_type or 'unknown'}): {preview}]"

        summary = text.splitlines()[0] if is_text else "Binary Content"
        return text, summary


    async def _handle_complete_message(self, message: bytes, content_type: str, parser, direction: bool, writer: asyncio.StreamWriter):
        """Process a complete HTTP message and send it to the GUI."""
        headers, _, body = message.partition(b"\r\n\r\n")
        body = self._decode_body(headers, body)
        full_text, summary = self._format_http_message(headers, body, content_type)

        method = getattr(parser, "method", "")
        url = getattr(parser, "url", "")
        direction_str = "Request" if direction == CLIENT_TO_SERVER else "Response"

        self.packet_counter += 1
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        peername = writer.get_extra_info('peername')
        sockname = writer.get_extra_info('sockname')
        source = sockname[0] if direction == CLIENT_TO_SERVER else peername[0]
        destination = peername[0] if direction == CLIENT_TO_SERVER else sockname[0]

        self.traffic_log.append((direction_str, full_text))
        self.gui.add_message(
            packet_no=self.packet_counter,
            timestamp=timestamp,
            source=source,
            destination=destination,
            protocol="HTTPS",
            length=len(message),
            info=summary,
            full_text=full_text,
            method=method
        )

    async def start(self):
        """Start the proxy server."""
        await self.initialize()
        self.server = await asyncio.start_server(self._handle_client, self.host, self.port)
        self.loop = asyncio.get_running_loop()
        addr = self.server.sockets[0].getsockname()
        logging.info(f"Proxy server running on {addr[0]}:{addr[1]}")
        async with self.server:
            await self.server.serve_forever()
    
    
    async def stop_proxy(self):
        """Stop the proxy server gracefully"""
        if hasattr(self, "server") and self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
    
    def start_gui(self):
        """Start the GUI event loop."""
        self.gui.mainloop()
    
    def start_background(self):
        """Start the proxy server in a background thread (called by GUI button)."""
        threading.Thread(target=lambda: asyncio.run(self.start()), daemon=True).start()