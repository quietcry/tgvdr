#!/usr/bin/env python3
from ..tgsvdrp.tgsvdrp import SVDRP
from ..tgsvdrp.tgsvdrp import SVDRP_COMMANDS
from ..tgsvdrp.tgsvdrp import SVDRP_RESULT_CODE


import logging
import re
from collections import namedtuple

epg_info = namedtuple("EPGDATA", "Channel Title Description")

FLAG_TIMER_ACTIVE = 1
FLAG_TIMER_INSTANT_RECORDING = 2
FLAG_TIMER_VPS = 4
FLAG_TIMER_RECORDING = 8

_LOGGER = logging.getLogger(__name__)


class PYVDR(object):
    def __init__(self, hostname="localhost", timeout=10):
        self.hostname = hostname
        self.svdrp = SVDRP(hostname=self.hostname, timeout=timeout)
        self.timers = None

    def stat(self):
        self.svdrp.send_cmd(SVDRP_COMMANDS.DISK_INFO)
        disk_stat_response = self.svdrp.get_response()[1:][0]

        if disk_stat_response.Code != SVDRP.SVDRP_STATUS_OK:
            return -1

        disk_stat_parts = re.match(
            r"(\d*)\w. (\d*)\w. (\d*)", disk_stat_response.Value, re.M | re.I
        )
        if disk_stat_parts:
            return [
                disk_stat_parts.group(1),
                disk_stat_parts.group(2),
                disk_stat_parts.group(3),
            ]
        else:
            return None

    """
    Gets a list of all channels names and ids
    """

    def get_channels(self):
        _LOGGER.debug("{SVDRP_COMMANDS.GET_CHANNELS}")
        # self.svdrp.send_cmd("{} :ids ".format(SVDRP_COMMANDS.GET_CHANNELS))
        # self.svdrp.send_cmd(f"{SVDRP_COMMANDS.GET_CHANNELS} :ids")
        self.svdrp.send_cmd(SVDRP_COMMANDS.GET_CHANNELS)
        responses = self.svdrp.get_response()
        if len(responses) < 1:
            _LOGGER.debug("Response of get channels cmd: NONE")
            return None
        # get 2nd element (1. welcome, 2. response, 3. quit msg)
        myresponse = []
        for response in responses:
            # print(response)
            if response.Code != SVDRP_RESULT_CODE.SUCCESS:
                continue
            myresponse.append(self._parse_channels_response(response))
        _LOGGER.debug("Response of get channels cmd: '%s' channels" % len(myresponse))
        # _LOGGER.debug("Response of get channels cmd: '%s'" % myresponse)
        return myresponse

    @staticmethod
    def _parse_channels_response(channel_data):
        _LOGGER.debug("Parsing Channel response to fields: %s" % channel_data.Value)
        channel_info = {}
        channel_parts = re.match(
            r"^([A-Z][0-9|\-]*?)\s(.*?);.*$", channel_data.Value, re.M | re.I
        )
        if channel_parts:
            channel_info["number"] = channel_data.Separator
            channel_info["id"] = channel_parts.group(1)
            channel_info["name"] = channel_parts.group(2)
        return channel_info

    """
    Gets the channel info and returns the channel number and the channel name.
    """

    def get_channel(self):
        self.svdrp.send_cmd(SVDRP_COMMANDS.GET_CHANNEL)
        responses = self.svdrp.get_response()
        _LOGGER.debug("Response of get channel cmd: '%s'" % responses)
        if len(responses) < 1:
            return None
        # get 2nd element (1. welcome, 2. response, 3. quit msg)
        generic_response = responses[-2]
        channel = self._parse_channel_response(generic_response)
        _LOGGER.debug("Returned Chan: '%s'" % channel)
        return channel

    @staticmethod
    def _parse_channel_response(channel_data):
        _LOGGER.debug("Parsing Channel response to fields: %s" % channel_data.Value)
        channel_info = {}
        channel_info["number"] = channel_data.Separator
        channel_info["name"] = channel_data.Value
        return channel_info

    @staticmethod
    def _parse_timer_response(response):
        timer = {}
        timer_match = re.match(
            r"^(\d+):(\d+):(\d{4}\-\d{2}\-\d{2}):(\d+):(\d+):(\d+):(\d+):(.+?):.+?<eventid>(.*)<\/eventid>.+?<timerid>(.*)<\/timerid>.*$",
            response.Value,
            re.M | re.I,
        )

        if timer_match:
            timer["status"] = timer_match.group(1)
            timer["channel"] = timer_match.group(2)
            timer["date"] = timer_match.group(3)
            timer["start"] = timer_match.group(4)
            timer["end"] = timer_match.group(5)
            timer["name"] = timer_match.group(8)
            timer["eventid"] = timer_match.group(9)
            timer["timerid"] = timer_match.group(10)
            timer["description"] = ""
            timer["series"] = timer["name"].find("~") != -1
            timer["instant"] = False
            _LOGGER.debug("Parsed timer: {}".format(timer))
        else:
            _LOGGER.debug(
                "You might want to check the regex for timer parsing?! {}".format(
                    response
                )
            )

        return timer

    def get_timers(self):
        timers = []
        self.svdrp.send_cmd(SVDRP_COMMANDS.LIST_TIMERS)
        responses = self.svdrp.get_response()
        print("timers", responses)
        for response in responses:
            if response.Code != SVDRP_RESULT_CODE.SUCCESS:
                continue
            timers.append(self._parse_timer_response(response))
        return timers

    def is_recording(self):
        self.svdrp.send_cmd(SVDRP_COMMANDS.LIST_TIMERS)
        responses = self.svdrp.get_response()
        for response in responses:
            if response.Code != SVDRP_RESULT_CODE.SUCCESS:
                continue
            timer = self._parse_timer_response(response)
            if len(timer) <= 0:
                _LOGGER.debug("No output from timer parsing.")
                return None
            if self._check_timer_recording_flag(timer, FLAG_TIMER_INSTANT_RECORDING):
                timer["instant"] = True
                return timer
            if self._check_timer_recording_flag(timer, FLAG_TIMER_RECORDING):
                return timer

        return None

    def get_channel_epg_info(self, channel_no=1, filter=""):
        # epg_title = epg_channel = epg_description = None
        # self.svdrp.send_cmd(f"{SVDRP_COMMANDS.LIST_EPG} {channel_no} {filter}")
        self.svdrp.send_cmd(f"LSTE {channel_no} {filter}")
        epg_data = self.svdrp.get_response()[1:]
        _LOGGER.debug("epg raw data: '%s' items" % epg_data)

        # print (epg_data)
        setChannel = setInfo = 0
        epg = channel = info = dict()
        channelkey = infokey = "none"
        for data in epg_data:
            # _LOGGER.debug("epg data: '%s' items" % data)

            if data.Code != SVDRP_RESULT_CODE.EPG_DATA_RECORD:
                continue
            # _LOGGER.debug("epg data: '%s' items" % data)

            if data.Separator == "C" and setChannel == 0:
                channel_match = re.match(
                    r"^([A-Z]\-[0-9|\-]+?)\s(.*)$", data.Value, re.M | re.I
                )
                if channel_match:
                    setChannel = 1
                    channel = dict()
                    channel["channelid"] = channelkey = channel_match.group(1)
                    channel["channelname"] = channel_match.group(2)
            elif data.Separator == "E" and setChannel == 1 and setInfo == 0:
                info_match = re.match(
                    r"^([0-9]+?)\s([0-9]+?)\s([0-9]+?)\s.*$", data.Value, re.M | re.I
                )
                if info_match:
                    setInfo = 1
                    info = dict()
                    info["START"] = infokey = info_match.group(2)
                    info["DURATION"] = info_match.group(3)
                    info["EVENTID"] = info_match.group(1)

            elif data.Separator == "e":
                if setInfo == 1:
                    channel[infokey] = info
                setInfo = 0
            elif data.Separator == "c":
                if setChannel == 1:
                    epg[channelkey] = dict(sorted(channel.items()))
                setInfo = 0
                setChannel = 0
            elif setInfo == 1:
                if data.Separator == "T":
                    info["TITLE"] = data.Value
                if data.Separator == "S":
                    info["SUBTITLE"] = data.Value
                if data.Separator == "D":
                    info["DESCRIPTION"] = data.Value
                if data.Separator == "G":
                    info["GENRE"] = data.Value
                if data.Separator == "R":
                    info["MINAGE"] = data.Value
                if data.Separator == "V":
                    info["VPSTIME"] = data.Value
                if data.Separator == "X":
                    if not "STREAMDETAILS" in info:
                        info["STREAMDETAILS"] = list()
                    info["STREAMDETAILS"].append(data.Value)
        _LOGGER.debug("Response of get_channel_epg_info cmd: '%s' items" % len(epg))
        return epg

    def channel_up(self):
        self.svdrp.send_cmd(SVDRP_COMMANDS.CHANNEL_UP)
        response_text = self.svdrp.get_response_as_text()
        return response_text

    def channel_down(self):
        self.svdrp.send_cmd(SVDRP_COMMANDS.CHANNEL_DOWN)
        response_text = self.svdrp.get_response_as_text()
        return response_text

    def list_recordings(self):
        self.svdrp.send_cmd(SVDRP_COMMANDS.LIST_RECORDINGS)
        return self.svdrp.get_response()[1:]

    @staticmethod
    def _check_timer_recording_flag(timer_info, flag):
        timer_status = timer_info["status"]
        if isinstance(timer_status, str):
            return int(timer_status) & flag
        return timer_status & flag
