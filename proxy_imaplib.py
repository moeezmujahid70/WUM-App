import socks
import imaplib
import socket
import ssl

from functools import wraps

def sslwrap(func):
    @wraps(func)
    def bar(*args, **kw):
        kw['ssl_version'] = ssl.PROTOCOL_TLSv1
        return func(*args, **kw)
    return bar


class IMAP(imaplib.IMAP4_SSL):
    def __init__(self, proxy_host='', proxy_port=0, proxy_type=socks.HTTP,
                 proxy_user='', proxy_pass='', host='', port=imaplib.IMAP4_PORT,
                 keyfile=None, certfile=None, ssl_context=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT):

        if ssl_context is not None and keyfile is not None:
            raise ValueError("ssl_context and keyfile arguments are mutually "
                             "exclusive")
        if ssl_context is not None and certfile is not None:
            raise ValueError("ssl_context and certfile arguments are mutually "
                             "exclusive")
        if keyfile is not None or certfile is not None:
            import warnings
            warnings.warn("keyfile and certfile are deprecated, use a "
                          "custom ssl_context instead", DeprecationWarning, 2)
        self.keyfile = keyfile
        self.certfile = certfile
        if ssl_context is None:
            ssl_context = imaplib.ssl._create_stdlib_context(certfile=certfile,
                                                             keyfile=keyfile)
        self.ssl_context = ssl_context
        self.timeout = timeout
        self.debug = imaplib.Debug
        self.state = 'LOGOUT'
        self.literal = None  # A literal argument to a command
        self.tagged_commands = {}  # Tagged commands awaiting response
        self.untagged_responses = {}  # {typ: [data, ...], ...}
        self.continuation_response = ''  # Last continuation response
        self.is_readonly = False  # READ-ONLY desired state
        self.tagnum = 0
        self._tls_established = False
        self._mode_ascii()

        # Open socket to server.

        self.connect_proxy(proxy_host, proxy_port, proxy_type, proxy_user,
                           proxy_pass, host, port)

        try:
            self._connect()
        except Exception:
            try:
                self.shutdown()
            except OSError:
                pass
            raise

    def connect_proxy(self, proxy_host='', proxy_port=0, proxy_type=socks.HTTP,
                      proxy_user='', proxy_pass='', host='', port=0):

        """Setup connection to remote server on "host:port"
            (default: localhost:standard IMAP4 port).
        This connection will be used by the routines:
            read, readline, send, shutdown.
        """
        self.host = host
        self.port = port

        s = socks.socksocket()
        s.set_proxy(proxy_type=proxy_type, addr=proxy_host, port=proxy_port, username=proxy_user, password=proxy_pass)
        s.settimeout(self.timeout)

        s.connect((host, port))

        self.sock = self.ssl_context.wrap_socket(s, server_hostname=self.host, suppress_ragged_eofs=True)

        # self.sock = ssl.wrap_socket(s)
        self.file = self.sock.makefile('rb')
