#!/usr/bin/env python3

import argparse
import re
from collections import namedtuple
from ..tgsvdrp.tgsvdrp import SVDRP


EPG_DATA_RECORD = "215"
epg_info = namedtuple("EPGDATA", "Channel Title Description")
timer_info = namedtuple("TIMER", "Status Name Date Description")
channel_info = namedtuple("CHANNEL", "Number Name")

FLAG_TIMER_ACTIVE = 1
FLAG_TIMER_INSTANT_RECORDING = 2
FLAG_TIMER_VPS = 4
FLAG_TIMER_RECORDING = 8


class PYVDR(object):
    def __init__(self, hostname="localhost"):
        self.hostname = hostname
        self.svdrp = SVDRP(hostname=self.hostname)
        self.timers = None

    def stat(self):
        self.svdrp.connect()
        self.svdrp.send_cmd("STAT DISK")
        disk_stat_response = self.svdrp.get_response()[1:][0]

        if disk_stat_response.Code != SVDRP.SVDRP_STATUS_OK:
            return -1

        disk_stat_parts = re.match(
            r"(\d*)\w. (\d*)\w. (\d*)", disk_stat_response.Value, re.M | re.I
        )
        return (
            disk_stat_parts.group(1),
            disk_stat_parts.group(2),
            disk_stat_parts.group(3),
        )

    def list_recordings(self):
        self.svdrp.connect()
        self.svdrp.send_cmd("LSTC")
        return self.svdrp.get_response()[1:]

    def get_channel(self):
        self.svdrp.connect()
        self.svdrp.send_cmd("CHAN")
        current_channel = self.svdrp.get_response()[-1]
        return current_channel[2]

    @staticmethod
    def _parse_channel_response(channel_data):
        print(channel_data[2])
        channel_parts = re.match(r"^(\d*)\s(.*)$", channel_data[2], re.M | re.I)
        return channel_info(Number=channel_parts.group(1), Name=channel_parts.group(2))

    @staticmethod
    def _parse_timer_response(response):
        timer_attr = response.Value.split(":")
        # print(timer_attr)
        # print(timer_attr[0])
        # print(timer_attr[0][-1])
        # print(timer_attr[1])
        # print(timer_attr[2])
        # print(timer_attr[3])
        # print(timer_attr[7].split('~')[0])
        # print(timer_attr[7].split('~')[1])
        return timer_info(
            Status=timer_attr[0].split(" ")[1],
            Date=timer_attr[2],
            Name=timer_attr[7].split("~")[0],
            Description="",
        )
        # timer_attr[7].split('~')[1]))

    def get_timers(self):
        timers = []
        self.svdrp.connect()
        self.svdrp.send_cmd("LSTT")
        responses = self.svdrp.get_response()
        for response in responses:
            if response.Code != "250":
                continue
            timers.append(self._parse_timer_response(response))

    def is_recording(self):
        self.svdrp.connect()
        self.svdrp.send_cmd("LSTT")
        responses = self.svdrp.get_response()
        for response in responses:
            if response.Code != "250":
                continue
            timer = self._parse_timer_response(response)
            if self._check_timer_recording_flag(timer, FLAG_TIMER_RECORDING):
                return timer
            if self._check_timer_recording_flag(timer, FLAG_TIMER_INSTANT_RECORDING):
                return timer

        return None

    @staticmethod
    def _check_timer_recording_flag(timer_info, flag):
        if isinstance(timer_info.Status, str):
            return int(timer_info.Status) & flag
        return timer_info.Status & flag

    def get_channel_info(self):
        self.svdrp.connect()
        self.svdrp.send_cmd("CHAN")
        chan = self.svdrp.get_response()[-1]
        channel = self._parse_channel_response(chan)

        self.svdrp.send_cmd("LSTE {} now".format(channel.Number))
        epg_data = self.svdrp.get_response()[1:]
        for d in epg_data:
            if d[0] == EPG_DATA_RECORD:
                print(d[2])
                epg = re.match(r"^(\S)\s(.*)$", d[2], re.M | re.I)
                if epg is not None:
                    epg_field_type = epg.group(1)
                    epg_field_value = epg.group(2)

                    print(epg_field_type)
                    if epg_field_type == "T":
                        epg_title = epg_field_value
                    if epg_field_type == "C":
                        epg_channel = epg_field_value
                    if epg_field_type == "D":
                        epg_description = epg_field_value

        return channel, epg_info(
            Channel=epg_channel, Title=epg_title, Description=epg_description
        )

    def channel_up(self):
        self.svdrp.connect()
        self.svdrp.send_cmd("CHAN +")
        return self.svdrp.get_response_text()

    def channel_down(self):
        self.svdrp.connect()
        self.svdrp.send_cmd("CHAN -")
        return self.svdrp.get_response_text()

    def test(self):
        self.svdrp.connect()
        self.svdrp.send_cmd("LSTE 6 now")
        return self.svdrp.get_response_text()

    def finish(self):
        self.svdrp.shutdown()


if __name__ == "__main__":
    print("pyvdr")
    parser = argparse.ArgumentParser()
    parser.add_argument("hostname", help="VDR Hostname")
    parser.add_argument(
        "command", help="Command to be executed [CHAN+|CHAN-|TIMER|CHANNEL]"
    )
    args = parser.parse_args()
    pyvdr = PYVDR(hostname=args.hostname)
    if args.command == "CHAN+":
        print(pyvdr.channel_up())
    if args.command == "STAT":
        print(pyvdr.stat())
    elif args.command == "CHAN-":
        print(pyvdr.channel_down())
    elif args.command == "TIMER":
        print(pyvdr.get_timers())
    elif args.command == "CHANNEL":
        print(pyvdr.get_channel_info())
    elif args.command == "REC":
        print("Recording: " + str(pyvdr.is_recording()))

    pyvdr.finish()
