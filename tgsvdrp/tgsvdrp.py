#!/usr/bin/env python3

from enum import Enum
import re
import socket
import logging
from collections import namedtuple


SVDRP_CMD_LF = "\r\n"
response_data = namedtuple("ResponseData", "Code Separator Value")
SVDRP_EMPTY_RESPONSE = ""

_LOGGER = logging.getLogger(__name__)


class SVDRP_COMMANDS(str, Enum):
    QUIT = "quit"
    LIST_TIMERS = "LSTT"
    GET_CHANNEL = "CHAN"
    GET_CHANNELS = "LSTC :ids :groups"
    DISK_INFO = "STAT DISK"
    LIST_RECORDINGS = "LSTR"
    LIST_EPG = "LSTE"
    CHANNEL_UP = "CHAN +"
    CHANNEL_DOWN = "CHAN -"


class SVDRP_RESULT_CODE(str, Enum):
    SUCCESS = "250"
    EPG_DATA_RECORD = "215"


class SVDRP(object):
    SVDRP_STATUS_OK = "250"

    def __init__(self, hostname="localhost", port=6419, timeout=10):
        self.hostname = hostname
        self.port = port
        self.timeout = timeout
        self.socket = None
        self.responses = []

    def _connect(self):
        if self.socket is None:
            try:
                _LOGGER.debug("Setting up connection to {}".format(self.hostname))
                self.socket = socket.create_connection(
                    (self.hostname, self.port), timeout=self.timeout
                )
            except socket.error as se:
                _LOGGER.info("Unable to connect. Not powered on? {}".format(se))
            finally:
                self.responses = []

    def _disconnect(self, send_quit=False):
        _LOGGER.debug("Closing communication with server.")
        if self.socket is not None:
            if send_quit:
                self.socket.sendall(SVDRP_COMMANDS.QUIT.join(SVDRP_CMD_LF).encode())
            self.socket.close()
            self.socket = None

    def is_connected(self):
        return self.socket is not None

    """
    Sends a SVDRP command to the VDR instance, by default the connection will be created and also be closed at the end.
    If the connection should be kept open in the end (e.g. for sending multi-commands)
    the param auto_disconnect needs to be set to False on invoking.
    The result will be stored in the internal responses array for later content handling.
    :return void / nothing
    """

    def send_cmd(self, cmd):
        self._connect()
        _LOGGER.debug("Send command: {}".format(cmd))

        if not self.is_connected():
            return

        command_list = [cmd]
        command_list.extend([SVDRP_COMMANDS.QUIT])
        _LOGGER.debug("Send commands: {}".format(command_list))

        try:
            data = list()
            [self.socket.sendall(s.join(SVDRP_CMD_LF).encode()) for s in command_list]
            while True:
                data.append(self.socket.recv(16))
                if not data[-1]:
                    break
        except IOError as e:
            _LOGGER.debug("IOError e {}, closing connection".format(e))
        finally:
            _LOGGER.debug("Decoding data into responses: %s" % data)
            response_raw = b"".join(data)
            [
                self.responses.append(self._parse_response_item(s.decode()))
                for s in response_raw.splitlines()
            ]

            self._disconnect()

    """
    Parses a single response item into data set
    :return response_data object
    """

    def _parse_response_item(self, resp):
        # <Reply code:3><-|Space><Text><Newline>
        # print ("---",resp)
        match_obj = re.match(r"^(\d{3})[\-|\s]([0-9]+|[A-Z])\s(.*)$", resp, re.M | re.I)
        if not match_obj:
            match_obj = re.match(r"^(\d{3})[\-|\s]([0-9]+|[A-Z])()$", resp, re.M | re.I)
        if not match_obj:
            match_obj = re.match(r"^(\d{3})(.)(.*)", resp, re.M | re.I)
        if match_obj:
            return response_data(
                Code=match_obj.group(1),
                Separator=match_obj.group(2),
                Value=match_obj.group(3),
            )
        else:
            return response_data(Code="221", Separator="", Value="")

    """
    Gets the response from the last CMD and puts it in the internal list.
    :return Namedtuple (Code, Separator, Value)
    """

    def _read_response_(self):
        for line in self.responses:
            response_entry = self._parse_response_item(line)
            self.responses.append(response_entry)

            # The first and last row are separated simply by ' ', other with '-'.
            # End once found a ' ' separator
            if response_entry.Separator != "-" and len(self.responses) > 1:
                break

    """
    Gets the response of the latest CMD as plaintext
    :return response as plain text
    """

    def get_response_as_text(self):
        return "".join(str(self.responses))

    """
    Gets the response of the latest CMD as data structure
    By default returns a list, if single line set to true it will just return the
    1st state line.
    :return List of Namedtuple (Code, Separator, Value)
    """

    def get_response(self, single_line=False):
        if len(self.responses) == 0:
            return SVDRP_EMPTY_RESPONSE

        if single_line:
            _LOGGER.debug("Returning single item")
            return self.responses[2]
        else:
            _LOGGER.debug("Returning {} items".format(len(self.responses)))
            return self.responses
