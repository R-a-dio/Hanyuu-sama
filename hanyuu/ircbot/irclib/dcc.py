from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
import socket
from . import utils
from . import connection

from . import logger

logger = logger.getChild(__name__)

# TODO set this somewhere else?
DEBUG = False

class DCCConnectionError(connection.IRCError):
    pass


class DCCConnection(connection.Connection):
    """This class represents a DCC connection.

    DCCConnection objects are instantiated by calling
    :meth:`session.Session.dcc`.
    
    For usage, see :meth:`connect` and :meth:`listen`.
    """
    def __init__(self, irclibobj, dcctype, dccinfo=(None, 0)):
        connection.Connection.__init__(self, irclibobj)
        self.connected = 0
        self.passive = 0
        self.dcctype = dcctype
        self.dccfile = dccinfo[0]
        self.total = long(dccinfo[1])
        self.peeraddress = None
        self.peerport = None

    def connect(self, address, port):
        """Connect/reconnect to a DCC peer.
    
        :param address: Host/IP address of the peer.
        :param port: The port number to connect to.

        Returns the DCCConnection object.
        """
        if (self.dcctype == "send"):
            self.fileobj = open(self.dccfile, "wb")
            self.current = 0
        self.peeraddress = socket.gethostbyname(address)
        self.peerport = port
        self.socket = None
        self.previous_buffer = ""
        self.handlers = {}
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.passive = 0
        try:
            self.socket.connect((self.peeraddress, self.peerport))
        except socket.error, x:
            raise DCCConnectionError("Couldn't connect to socket: {}".format(x))
        self.connected = 1
        if self.irclibobj.fn_to_add_socket:
            self.irclibobj.fn_to_add_socket(self.socket)
        return self

    def listen(self):
        """Wait for a connection/reconnection from a DCC peer.

        Returns the DCCConnection object.

        The local IP address and port are available as :attr:`localaddress`
        and :attr:`localport`. After connection from a peer, the peer
        address and port are available as :attr:`peeraddress` and
        :attr:`peerport`.
        """
        self.previous_buffer = b""
        self.handlers = {}
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.passive = 1
        try:
            self.socket.bind((socket.gethostbyname(socket.gethostname()), 0))
            self.localaddress, self.localport = self.socket.getsockname()
            self.socket.listen(10)
        except socket.error, x:
            raise DCCConnectionError("Couldn't bind socket: {}".format(x))
        return self

    def disconnect(self, message=""):
        """Hang up the connection and close the object.

        :param message: Quit message.
        
        """
        if not self.connected:
            return

        self.connected = 0
        try:
            self.socket.close()
        except socket.error, x:
            pass
        self.socket = None
        self.irclibobj._handle_event(
            self,
            connection.Event("dcc_disconnect", self.peeraddress, "", [message]))
        self.irclibobj._remove_connection(self)

    def process_data(self):
        """[Internal]"""

        if self.passive and not self.connected:
            conn, (self.peeraddress, self.peerport) = self.socket.accept()
            self.socket.close()
            self.socket = conn
            self.connected = 1
            if DEBUG:
                # TODO: replace the prints with logging calls
                logger.debug("DCC connection from {}:{}"
                             .format(self.peeraddress, self.peerport))
            self.irclibobj._handle_event(
                self,
                connection.Event("dcc_connect", self.peeraddress, None, None))
            return

        try:
            new_data = self.socket.recv(2**14)
        except socket.error, x:
            # The server hung up.
            self.disconnect("Connection reset by peer")
            return
        if not new_data:
            # Read nothing: connection must be down.
            self.disconnect("Connection reset by peer")
            return

        if self.dcctype == "chat":
            # The specification says lines are terminated with LF, but
            # it seems safer to handle CR LF terminations too.
            chunks = utils._linesep_regexp.split(self.previous_buffer + new_data)

            # Save the last, unfinished line.
            self.previous_buffer = chunks[-1]
            if len(self.previous_buffer) > 2**14:
                # Bad peer! Naughty peer!
                self.disconnect()
                return
            chunks = chunks[:-1]
        elif self.dcctype == "send":
            # We are going to sidestep the events a bit
            size = len(new_data)
            self.current += size
            try:
                self.fileobj.write(new_data)
            except (AttributeError):
                self.disconnect("Invalid file object")
            except (IOError):
                self.disconnect("Invalid file object")
            chunks = ["send"]
        else:
            chunks = [new_data]

        command = "dccmsg"
        prefix = self.peeraddress
        target = None
        for chunk in chunks:
            if DEBUG:
                logger.debug("FROM PEER:" + chunk)
            arguments = [chunk]
            if DEBUG:
                logger.debug("command: {}, source: {}, target: {}, arguments: {}".format(
                    command, prefix, target, arguments))
            self.irclibobj._handle_event(
                self,
                connection.Event(command, prefix, target, arguments))

    def _get_socket(self):
        """[Internal]"""
        return self.socket

    def privmsg(self, string):
        """Send data to DCC peer.

        The string will be padded with appropriate LF if it's a DCC
        CHAT session.
        """
        try:
            self.socket.send(string)
            if self.dcctype == "chat":
                self.socket.send("\n")
            if DEBUG:
                print("TO PEER: {}\n".format(string))
        except socket.error, x:
            # Ouch!
            self.disconnect("Connection reset by peer.")