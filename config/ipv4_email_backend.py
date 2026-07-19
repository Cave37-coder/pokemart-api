"""
Forces outbound SMTP connections over IPv4.

Railway's containers frequently lack outbound IPv6 routing. If a mail
host's DNS advertises an IPv6 address -- common for cPanel-hosted mail
like mail.pokebulk.co.za -- Python's default socket connection can try
that address first and fail with exactly:

    [Errno 101] Network is unreachable

...before ever falling back to the working IPv4 address. This backend is
a drop-in replacement for Django's default SMTP backend that forces
IPv4 resolution, sidestepping the issue entirely. Every EMAIL_* setting
in settings.py stays exactly the same -- only EMAIL_BACKEND changes to
point here instead of Django's built-in smtp backend.
"""
import smtplib
import socket

from django.core.mail.backends.smtp import EmailBackend as DjangoSMTPEmailBackend
from django.core.mail.utils import DNS_NAME


def _ipv4_get_socket(self, host, port, timeout):
    """Replaces smtplib's default socket creation -- which tries every
    address family DNS returns, IPv6 first if present -- with an
    IPv4-only lookup and connection."""
    if timeout is not None and not timeout:
        raise ValueError('Non-blocking socket (timeout=0) is not supported')
    infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
    family, socktype, proto, canonname, sockaddr = infos[0]
    sock = socket.socket(family, socktype, proto)
    if timeout is not None:
        sock.settimeout(timeout)
    sock.connect(sockaddr)
    return sock


class IPv4SMTP(smtplib.SMTP):
    _get_socket = _ipv4_get_socket


class IPv4SMTP_SSL(smtplib.SMTP_SSL):
    def _get_socket(self, host, port, timeout):
        sock = _ipv4_get_socket(self, host, port, timeout)
        return self.context.wrap_socket(sock, server_hostname=host)


class IPv4EmailBackend(DjangoSMTPEmailBackend):
    """Identical to Django's built-in SMTP backend -- copied from
    Django's own open() implementation -- except the connection classes
    used are the IPv4-forcing ones above instead of plain smtplib."""

    def open(self):
        if self.connection:
            return False

        connection_class = IPv4SMTP_SSL if self.use_ssl else IPv4SMTP
        connection_params = {"local_hostname": DNS_NAME.get_fqdn()}
        if self.timeout is not None:
            connection_params["timeout"] = self.timeout
        if self.use_ssl:
            connection_params["context"] = getattr(self, "ssl_context", None)

        try:
            self.connection = connection_class(self.host, self.port, **connection_params)
            if not self.use_ssl and self.use_tls:
                self.connection.starttls(context=getattr(self, "ssl_context", None))
            if self.username and self.password:
                self.connection.login(self.username, self.password)
            return True
        except OSError:
            if not self.fail_silently:
                raise
