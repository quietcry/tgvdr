import logging
import json
import time

from datetime import timedelta
from datetime import datetime

from .tgpyvdr.tgpyvdr import PYVDR

import voluptuous as vol

from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_PORT,
    CONF_TIMEOUT,
    PERCENTAGE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv


_LOGGER = logging.getLogger(__name__)

CONF_DEFAULT_NAME = "vdr"

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=CONF_DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=6419): cv.port,
        vol.Optional(CONF_TIMEOUT, default=10): cv.byte,
    }
)

ATTR_CHANNEL_NAME = "channel_name"
ATTR_CHANNEL_NUMBER = "channel_number"
ATTR_RECORDING_NAME = "recording_name"
ATTR_RECORDING_INSTANT = "recording_instant"
ATTR_IS_RECORDING = "is_recording"
ATTR_DISKSTAT_TOTAL = "disksize_total"
ATTR_DISKSTAT_FREE = "disksize_free"
ATTR_SENSOR_NAME = 0
ATTR_ICON = 1
ATTR_UNIT = 2

ICON_VDR_ONLINE = "mdi:television-box"
ICON_VDR_OFFLINE = "mdi:television-classic-off"
ICON_VDR_RECORDING_INSTANT = "mdi:record-rec"
ICON_VDR_RECORDING_TIMER = "mdi:history"
ICON_VDR_RECORDING_NONE = "mdi:close-circle-outline"

SENSOR_TYPE_DISKUSAGE = "diskusage"
SENSOR_TYPE_RECINFO = "recinfo"
SENSOR_TYPE_VDRINFO = "vdrinfo"
SENSOR_TYPE_VDREPG = "vdrepg"
SENSOR_TYPE_TIMERS = "timer"

SENSOR_TYPES = {
    SENSOR_TYPE_VDREPG: ["EPG Info", "mdi:television-box", ""],
    SENSOR_TYPE_VDRINFO: ["Channel Info", "mdi:television-box", ""],
    SENSOR_TYPE_DISKUSAGE: ["Disk usage", "mdi:harddisk", PERCENTAGE],
    SENSOR_TYPE_RECINFO: ["Recording", "mdi:close-circle-outline", ""],
    SENSOR_TYPE_TIMERS: ["Timer", "mdi:close-circle-outline", ""],
}

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)
MIN_TIME_BETWEEN_EPG_UPDATES = timedelta(seconds=3600)
MIN_COUNTS_UPDATE = 1
MIN_COUNTS_UPDATE_EPG = 180


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    # from pyvdr import PYVDR

    conf_name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    _LOGGER.info(
        "Set up VDR with hostname {}, timeout={}".format(host, config["timeout"])
    )

    pyvdr_con = PYVDR(hostname=host)

    entities = []
    for sensor_type in SENSOR_TYPES:
        _LOGGER.debug("Setting up sensortype {}".format(sensor_type))
        entities.append(VdrSensor(sensor_type, conf_name, pyvdr_con))

    add_entities(entities)


class VdrSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, sensor_type, conf_name, pyvdr):
        """Initialize the sensor."""
        self._state = STATE_OFF
        self._sensor_type = sensor_type
        self._name = " ".join(
            [conf_name.capitalize(), SENSOR_TYPES[sensor_type][ATTR_SENSOR_NAME]]
        )
        self.runUpdateFactor = MIN_COUNTS_UPDATE

        self._Runs = 0
        self._pyvdr = pyvdr
        self._init_attributes()

    def _init_attributes(self):
        self._attributes = {}

        if self._sensor_type == SENSOR_TYPE_VDRINFO:
            self._attributes = {ATTR_CHANNEL_NAME: "", ATTR_CHANNEL_NUMBER: 0}

        if self._sensor_type == SENSOR_TYPE_DISKUSAGE:
            self._attributes = {ATTR_DISKSTAT_TOTAL: 0, ATTR_DISKSTAT_FREE: 0}

    def _updateRuns(self):
        result = False
        if (
            self.runUpdateFactor == 0
            or self._Runs == 0
            or self._Runs % self.runUpdateFactor == 0
        ):
            _LOGGER.info(f"UPDATE Runs {self._sensor_type} = true {self._Runs}")
            self._Runs = 1
            result = True
        else:
            self._Runs += 1
            result = False
        return result

    def _set_attributes(self, name, value):
        if not self._attributes:
            self._attributes = {}
        self._attributes.update({name: value})

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def state_attributes(self):
        """Return device specific state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Return device specific state attributes."""
        if self._state == "instant":
            return ICON_VDR_RECORDING_INSTANT

        if self._state == "timer":
            return ICON_VDR_RECORDING_TIMER

        return SENSOR_TYPES[self._sensor_type][ATTR_ICON]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if self._state == STATE_OFF:
            return ""
        return SENSOR_TYPES[self._sensor_type][ATTR_UNIT]

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """

        if not self._updateRuns():
            return

        self._state = STATE_OFF

        if self._sensor_type == SENSOR_TYPE_VDRINFO:
            response = self._pyvdr.get_channel()
            self._attributes = {}

            if response is None:
                return

            self._state = response["name"]
            self._attributes.update(
                {
                    ATTR_CHANNEL_NAME: response["name"],
                    ATTR_CHANNEL_NUMBER: response["number"],
                }
            )

            return

        if self._sensor_type == SENSOR_TYPE_DISKUSAGE:
            try:
                response = self._pyvdr.stat()
                if response is not None and len(response) == 3:
                    self._state = response[2]
                    self._attributes.update(
                        {
                            ATTR_DISKSTAT_TOTAL: int(response[0]),
                            ATTR_DISKSTAT_FREE: int(response[1]),
                        }
                    )
            except:
                _LOGGER.debug("Vdr seems to be offline")

            return

        if self._sensor_type == SENSOR_TYPE_RECINFO:
            response = self._pyvdr.is_recording()
            if response is not None:
                if response["instant"]:
                    self._state = "instant"
                else:
                    self._state = "timer"
                self._attributes.update(
                    {
                        ATTR_RECORDING_NAME: response["name"],
                    }
                )
            else:
                self._attributes = {}
                self._state = STATE_OFF
            return
        def get_timerlist(self):
            timers=list()
            nextTimer=-1
            listPos=-1
            
            response = self._pyvdr.get_timers()
            if response is not None:
                for resp in response:
                    timers.append(resp)
                    s=resp.get("start")
                    s=s[:2] + ':' + s[2:]
                    s=resp.get("date")+" "+s
                    timer=time.mktime(datetime.strptime(s, "%Y-%m-%d %H:%M").timetuple())
                    if nextTimer < 0 or nextTimer > timer:
                        nextTimer=timer
                        listPos=len(timers)-1
                if listPos > -1:
                    timers[listPos]["nextTimer"]=True
                    timers[listPos]["nextTimerTime"]=s
            return timers
        
        if self._sensor_type == SENSOR_TYPE_TIMERS:
            response = get_timerlist(self)
            state=STATE_OFF
            if len(response) > 0:
                state="no Timers defined"
                self._set_attributes(
                    "timer",
                    json.dumps(response)
                )               
                for resp in response:
                    key="nextTimer"
                    if key in resp and resp.get(key):
                        state = "next of ["+str(len(response))+"] : " + resp.get("nextTimerTime")+" - "+resp.get("name")
                        break 
            self._state=state 
            return

        if self._sensor_type == SENSOR_TYPE_VDREPG:
            _LOGGER.info(f"UPDATE VDR SENSOR {self._sensor_type}")
            _LOGGER.debug(f"UPDATE VDR SENSOR {self._sensor_type}")
            self._set_attributes(
                "timers",
                json.dumps(get_timerlist(self)),
                )
            
            response = self._pyvdr.get_channels()
            if response is None:              
                self.runUpdateFactor = MIN_COUNTS_UPDATE
                return
            _LOGGER.debug(f"UPDATE VDR SENSOR Result: {response}")
            self.runUpdateFactor = MIN_COUNTS_UPDATE_EPG

            current_datetime = datetime.now()
            updateTime = current_datetime.strftime("%m/%d/%Y, %H:%M:%S")
            self._state = updateTime
            # response = self._pyvdr.get_channels()
            filter = ""
            for resp in response:
                id = resp.get("id")
                epg = self._pyvdr.get_channel_epg_info(id, filter)
                if epg is None or not id in epg:
                    _LOGGER.info(f"VDR EPG NONE {epg}")
                    continue
                channeldata = dict()
                channeldata["channelid"] = id
                channeldata["name"] = resp.get("name")
                channeldata["lastUpdate"] = updateTime
                self._set_attributes(
                    f"{id}",
                    json.dumps({"channeldata": channeldata, "epg": epg.get(id)}),
                )
            _LOGGER.info(f"VDR SENSOR {self._sensor_type} UPDATED {self._attributes}")

            return
