import logging
from httptools import HttpRequestParser, HttpResponseParser

class HTTPMessageParser:
    """
    Accepts raw byte streams,
    Feeds them into a low-level HTTP parser,
    Buffers headers + body,
    Marks when a full message is complete,
    Allows you to extract that message for logging or inspection. 
    """
    def __init__(self, is_request=True):
        self.is_request = is_request
        self.headers = {}
        self.body = bytearray()
        self.completed = False
        self.parser = (HttpRequestParser if is_request else HttpResponseParser)(self)
        self.buffer = bytearray()
        
        self.content_type = "application/octet-stream"
        self.method = ""
        self.url = ""

    def on_message_begin(self):
        self.headers.clear()
        self.body.clear()
        self.completed = False

    def on_url(self, url: bytes):
        self.url = url.decode(errors="replace")

    def on_status(self, status: bytes):
        pass

    def on_header(self, name: bytes, value: bytes):
        try:
            key = name.decode('utf-8').lower()
            val = value.decode('utf-8')
        except UnicodeDecodeError:
            key = name.decode('latin1').lower()
            val = value.decode('latin1')

        if key == "connection" and val.lower() == "close":
            logging.warning("Encountered 'Connection: close'")
            return

        self.headers[key] = val
        if key == "content-type":
            self.content_type = val
            
        if self.is_request and key == ":method":
            self.method = val

    def on_headers_complete(self):
        if self.is_request and not self.method:
            try:
                # Grab the first line of the full buffered message
                request_line = self.buffer.split(b'\r\n', 1)[0]
                parts = request_line.decode(errors="replace").split()
                if len(parts) >= 2:
                    self.method = parts[0]
                    self.url = parts[1]
            except Exception as e:
                logging.warning(f"Failed to parse method and URL from request line: {e}")
                
    def on_body(self, body: bytes):
        self.body.extend(body)

    def on_message_complete(self):
        self.completed = True

    def feed(self, data: bytes) -> int:
        """
        Feed raw data into the parser.
        Returns number of bytes consumed if complete, else 0.
        """
        try:
            # Reset internal buffer for a fresh parse
            self.buffer = bytearray(data)

            self.parser.feed_data(self.buffer)

            if self.completed:
                return len(self.buffer)

            return 0
        except Exception as e:
            logging.error(f"Parsing error: {e}")
            self.reset_parser()
            return 0

    def reset_parser(self):
        """Reset the parser state."""
        self.headers.clear()
        self.body.clear()
        self.buffer.clear()
        self.completed = False
        self.content_type = "application/octet-stream"
        self.parser = (HttpRequestParser if self.is_request else HttpResponseParser)(self)

    def get_full_message(self):
        """
        Return the full HTTP message from the buffer.
        """
        if not self.completed:
            raise ValueError("Message is not yet complete.")
        return bytes(self.buffer), self.content_type

    def get_remaining_buffer(self):
        """
        Return any unparsed data remaining in the buffer.
        """
        return bytes(self.buffer)
        
    def get_full_message_and_remaining(self, buffer: bytes) -> tuple[bytes, str, bytes]:
        full_msg, content_type = self.get_full_message()
        parsed_len = len(full_msg)
        remaining = buffer[parsed_len:]
        return full_msg, content_type, remaining