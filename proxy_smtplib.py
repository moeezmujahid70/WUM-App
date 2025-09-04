from __future__ import print_function
import socket
import socks
import smtplib
import datetime
import sys
import re
import var
from urllib.request import getproxies

# CRLF binary representationFor compatibility with Python 3.x
try:
    bCRLF = smtplib.bCRLF
except AttributeError:
    bCRLF = smtplib.CRLF


class NotSupportedProxyType(socks.ProxyError):
    """Not supported proxy type provided
    Exception is raised when provided proxy type is not supported.
    See socks.py for supported types.
    """


PROXY = {"useproxy": True, "server": None, "port": None, "type": "HTTP", "username": None, "password": None}


class Proxifier:
    """
    Helper class to configure proxy settings. Exposes the `get_socket()` method that returns
    a proxified connection (socket).
    """

    def __init__(self, proxy_server=None, proxy_port=None, proxy_type='SOCKS5', proxy_username=None, proxy_password=None):
        # proxy type: HTTP, SOCKS4 or SOCKS5 (default = HTTP)
        self.proxy_type = {'HTTP': socks.HTTP, 'SOCKS4': socks.SOCKS4, 'SOCKS5': socks.SOCKS5}.get(proxy_type, socks.HTTP)
        # proxy auth if required
        self.proxy_username = proxy_username
        self.proxy_password = proxy_password
        # if host or port not set, attempt to retrieve from system
        if not proxy_server or not proxy_port:
            self._get_sysproxy()
        else:
            self.proxy_server = proxy_server
            self.proxy_port = proxy_port

    def _get_sysproxy(self, setvars=True):
        """
        Retrieves system proxy settings from OS environment variables (HTTP_PROXY, HTTPS_PROXY etc.)
        If `setvars` == `True`, sets the member variables as well.
        """
        proxy_server, proxy_port, proxy_username, proxy_password = (None, None, None, None)
        template = re.compile(r'^(((?P<user>[^:]+)(:(?P<pass>[^@]*)?))@)?(?P<host>[^:]+?)(:(?P<port>\d{1,5})?)$', re.I)
        try:
            sys_proxy = getproxies()
            for p in sys_proxy:
                if p.lower().startswith('http') or p.lower().startswith('socks'):
                    sp = sys_proxy[p].split('//')
                    sp = sp[1] if len(sp) > 1 else sp[0]
                    m = template.fullmatch(sp)
                    proxy_server = m.group('host') or None
                    try:
                        proxy_port = int(m.group('port')) or None
                    except:
                        pass
                    proxy_username = m.group('user') or None
                    proxy_password = m.group('pass') or None
                    break
        except Exception as err:
            var.logging.exception(err)

        if setvars:
            self.proxy_server = proxy_server or self.proxy_server
            self.proxy_port = proxy_port or self.proxy_port
            self.proxy_username = proxy_username or self.proxy_username
            self.proxy_password = proxy_password or self.proxy_password
        return (proxy_server, proxy_port)

    def get_socket(self, source_address, host, port, timeout=None):
        """
        Applies proxy settings to PySocks `create_connection()` method to
        created a proxified connection (socket) which can be used by other
        interfaces to establish connection.
        """
        return socks.create_connection((host, port), timeout, source_address,
                                       proxy_type=self.proxy_type, proxy_addr=self.proxy_server, proxy_port=self.proxy_port,
                                       proxy_username=self.proxy_username, proxy_password=self.proxy_password)

    @staticmethod
    def get_proxifier(proxy=PROXY):
        """
        Factory returns a `Proxifier` object given proxy settings in a dictionary.
        """
        if not proxy or not proxy.get('useproxy', False):
            return None
        return Proxifier(proxy.get('server', None), proxy.get('port', None), proxy.get('type', None),
                        proxy.get('username', None), proxy.get('password', None))


class SmtpProxy(smtplib.SMTP):
    """
    Descendant of SMTP with optional proxy wrapping.
    """

    def __init__(self, host='', port=0, local_hostname=None, timeout=30, source_address=None,
                 proxifier: Proxifier=None):
        # `Proxifier` object if proxy is required
        self._proxifier = proxifier
        super().__init__(host, port, local_hostname, timeout, source_address)

    def _get_socket(self, host, port, timeout):
        """
        Overridden method of base class to allow for proxified connection.
        """
        if not self._proxifier:
            # no proxy: use base class implementation
            return super()._get_socket(host, port, timeout)
        if timeout is not None and not timeout:
            raise ValueError('Non-blocking socket (timeout=0) is not supported')
        if self.debuglevel > 0:
            self._print_debug('connect: to', (host, port), self.source_address)
        # proxy: use proxifier connection
        return self._proxifier.get_socket(self.source_address, host, port, timeout)


class SMTP(smtplib.SMTP):
    """This class manages a connection to an SMTP or ESMTP server.
    HTTP/SOCKS4/SOCKS5 proxy servers are supported
    For additional information see smtplib.py
    """

    def __init__(self, host='', port=0, proxy_host='', proxy_port=0, proxy_type=socks.SOCKS5,
                 local_hostname=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None):
        """Initialize a new instance.
        If a host is specified the connect method is called, and if it returns anything other than a
        success code an SMTPConnectError is raised
        :param host: Hostname of SMTP server
        :type host: string
        :param port: Port of SMTP server, by default smtplib.SMTP_PORT is used
        :type port: int
        :param proxy_host: Hostname of proxy server
        :type proxy_host: string
        :param proxy_port: Port of proxy server, by default port for specified  proxy type is used
        :type proxy_port: int
        :param proxy_type: Proxy type to use (see socks.PROXY_TYPES for details)
        :type proxy_type: int
        :param local_hostname: Local hostname is used as the FQDN of the local host for the
            HELO/EHLO command, if not specified the local hostname is found using socket.getfqdn()
        :type local_hostname: string
        :param timeout: Connection timeout
        :type timeout: int
        :param source_address: Host and port for the socket to bind to as its source address before
            connecting
        :type source_address: tuple
        """
        # super(SMTP, self).__init__("smtp.gmail.com", 465, context=context)
        self._host = host
        self.timeout = timeout
        self.esmtp_features = {}
        self.command_encoding = 'ascii'
        self.source_address = source_address
        if host:
            if proxy_host:
                (code, msg) = self.connect_proxy(
                    proxy_host, proxy_port, proxy_type, host, port)
            else:
                (code, msg) = self.connect(host, port)
            if code != 220:
                raise smtplib.SMTPConnectError(code, msg)
        if local_hostname is not None:
            self.local_hostname = local_hostname
        else:
            # RFC 2821 says we should use the fqdn in the EHLO/HELO verb, and
            # if that can't be calculated, that we should use a domain literal
            # instead (essentially an encoded IP address like [A.B.C.D]).
            fqdn = socket.getfqdn()
            if '.' in fqdn:
                self.local_hostname = fqdn
            else:
                # We can't find an fqdn hostname, so use a domain literal
                addr = '127.0.0.1'
                try:
                    addr = socket.gethostbyname(socket.gethostname())
                except socket.gaierror:
                    pass
                self.local_hostname = '[%s]' % addr

    def _print_debug(self, *args):
        """Method output debug message into stderr
        :param args: Message(s) to output
        :rtype args: string
        """
        if self.debuglevel > 1:
            print(datetime.datetime.now().time(), *args, file=sys.stderr)
        else:
            print(*args, file=sys.stderr)

    @classmethod
    def _parse_host(cls, host='localhost', port=0):
        """ Parse provided hostname and extract port number
        :param host: Server hostname
        :type host: string
        :param port: Server port
        :return: Tuple of (host, port)
        :rtype: tuple
        """
        if not port and (host.find(':') == host.rfind(':')):
            i = host.rfind(':')
            if i >= 0:
                host, port = host[:i], host[i + 1:]
                try:
                    port = int(port)
                except ValueError:
                    raise OSError('nonnumeric port')
        return host, port

    def _get_socket(self, host, port, timeout):
        # This makes it simpler for SMTP_SSL to use the SMTP connect code
        # and just alter the socket connection bit.
        if self.debuglevel > 0:
            self._print_debug('connect: to', (host, port), self.source_address)
        return socket.create_connection((host, port), timeout,
                                        self.source_address)

    def ehlo(self, name=''):
        """ SMTP 'ehlo' command.
        Hostname to send for this command defaults to the FQDN of the local
        host.
        """
        from smtplib import SMTPServerDisconnected, OLDSTYLE_AUTH
        import re
        self.esmtp_features = {}

        self.putcmd(self.ehlo_msg, name or self.local_hostname)
        (code, msg) = self.getreply()
        # According to RFC1869 some (badly written)
        # MTA's will disconnect on an ehlo. Toss an exception if
        # that happens -ddm
        if code == -1 and len(msg) == 0:
            self.close()
            raise SMTPServerDisconnected("Server not connected")
        self.ehlo_resp = msg
        if code != 250:
            return (code, msg)
        self.does_esmtp = 1
        #parse the ehlo response -ddm
        assert isinstance(self.ehlo_resp, bytes), repr(self.ehlo_resp)
        resp = self.ehlo_resp.decode("latin-1").split('\n')
        del resp[0]
        for each in resp:
            # To be able to communicate with as many SMTP servers as possible,
            # we have to take the old-style auth advertisement into account,
            # because:
            # 1) Else our SMTP feature parser gets confused.
            # 2) There are some servers that only advertise the auth methods we
            #    support using the old style.
            auth_match = OLDSTYLE_AUTH.match(each)
            if auth_match:
                # This doesn't remove duplicates, but that's no problem
                self.esmtp_features["auth"] = self.esmtp_features.get("auth", "") \
                        + " " + auth_match.groups(0)[0]
                continue

            # RFC 1869 requires a space between ehlo keyword and parameters.
            # It's actually stricter, in that only spaces are allowed between
            # parameters, but were not going to check for that here.  Note
            # that the space isn't present if there are no parameters.
            m = re.match(r'(?P<feature>[A-Za-z0-9][A-Za-z0-9\-]*) ?', each)
            if m:
                feature = m.group("feature").lower()
                params = m.string[m.end("feature"):].strip()
                if feature == "auth":
                    self.esmtp_features[feature] = self.esmtp_features.get(feature, "") \
                            + " " + params
                else:
                    self.esmtp_features[feature] = params
        return (code, msg)

    def ehlo_or_helo_if_needed(self):
        """Call self.ehlo() and/or self.helo() if needed.

        If there has been no previous EHLO or HELO command this session, this
        method tries ESMTP EHLO first.

        This method may raise the following exceptions:

         SMTPHeloError            The server didn't reply properly to
                                  the helo greeting.
        """
        from smtplib import SMTPHeloError
        if self.helo_resp is None and self.ehlo_resp is None:
            if not (200 <= self.ehlo()[0] <= 299):
                (code, resp) = self.helo()
                if not (200 <= code <= 299):
                    raise SMTPHeloError(code, resp)

    def starttls(self, keyfile=None, certfile=None, context=None):
        """Puts the connection to the SMTP server into TLS mode.

        If there has been no previous EHLO or HELO command this session, this
        method tries ESMTP EHLO first.

        If the server supports TLS, this will encrypt the rest of the SMTP
        session. If you provide the keyfile and certfile parameters,
        the identity of the SMTP server and client can be checked. This,
        however, depends on whether the socket module really checks the
        certificates.

        This method may raise the following exceptions:

         SMTPHeloError            The server didn't reply properly to
                                  the helo greeting.
        """
        # self.ehlo_or_helo_if_needed()

        try:
            import ssl
        except ImportError:
            _have_ssl = False
        else:
            _have_ssl = True
        from smtplib import SMTPNotSupportedError, SMTPResponseException
        self.ehlo_or_helo_if_needed()
        if not self.has_extn("starttls"):
            raise SMTPNotSupportedError(
                "STARTTLS extension not supported by server.")
        (resp, reply) = self.docmd("STARTTLS")
        if resp == 220:
            if not _have_ssl:
                raise RuntimeError("No SSL support included in this Python")
            if context is not None and keyfile is not None:
                raise ValueError("context and keyfile arguments are mutually "
                                 "exclusive")
            if context is not None and certfile is not None:
                raise ValueError("context and certfile arguments are mutually "
                                 "exclusive")
            if keyfile is not None or certfile is not None:
                import warnings
                warnings.warn("keyfile and certfile are deprecated, use a "
                              "custom context instead", DeprecationWarning, 2)
            if context is None:
                context = ssl._create_stdlib_context(certfile=certfile,
                                                     keyfile=keyfile)
            self.sock = context.wrap_socket(self.sock,
                                            server_hostname=self._host)
            self.file = None
            # RFC 3207:
            # The client MUST discard any knowledge obtained from
            # the server, such as the list of SMTP service extensions,
            # which was not obtained from the TLS negotiation itself.
            self.helo_resp = None
            self.ehlo_resp = None
            self.esmtp_features = {}
            self.does_esmtp = 0
        else:
            # RFC 3207:
            # 501 Syntax error (no parameters allowed)
            # 454 TLS not available due to temporary reason
            raise SMTPResponseException(resp, reply)
        return (resp, reply)

    def connect_proxy(self, proxy_host='localhost', proxy_port=0, proxy_type=socks.HTTP,
                      proxy_user='', proxy_pass='', host='', port=0):
        """Connect to a host on a given port via proxy server
        If the hostname ends with a colon (`:') followed by a number, and
        there is no port specified, that suffix will be stripped off and the
        number interpreted as the port number to use.
        Note: This method is automatically invoked by __init__, if a host and proxy server are
        specified during instantiation.
        :param proxy_host: Hostname of proxy server
        :type proxy_host: string
        :param proxy_port: Port of proxy server, by default port for specified  proxy type is used
        :type proxy_port: int
        :param proxy_type: Proxy type to use (see socks.PROXY_TYPES for details)
        :type proxy_type: int
        :param host: Hostname of SMTP server
        :type host: string
        :param port: Port of SMTP server, by default smtplib.SMTP_PORT is used
        :type port: int
        :return: Tuple of (code, msg)
        :rtype: tuple
        """
        if proxy_type not in socks.DEFAULT_PORTS.keys():
            raise NotSupportedProxyType
        (proxy_host, proxy_port) = self._parse_host(
            host=proxy_host, port=proxy_port)
        if not proxy_port:
            proxy_port = socks.DEFAULT_PORTS[proxy_type]
        (host, port) = self._parse_host(host=host, port=port)
        if self.debuglevel > 0:
            self._print_debug('connect: via proxy', proxy_host, proxy_port)

        self._host = host
        s = socks.socksocket()
        s.set_proxy(proxy_type=proxy_type, addr=proxy_host,
                    port=proxy_port, username=proxy_user, password=proxy_pass)
        s.settimeout(self.timeout)

        s.connect((host, port))

        # todo
        # Send CRLF in order to get first response from destination server.
        # Probably it's needed only for HTTP proxies. Further investigation required.
        s.sendall(bCRLF)
        self.sock = s
        (code, msg) = self.getreply()
        if self.debuglevel > 0:
            self._print_debug('connect:', repr(msg))
        return (code, msg)
