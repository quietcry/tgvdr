"""Provide functionality to interact with vdr devices on the network."""
import logging

import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_STOP,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PREVIOUS_TRACK
)
from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_PORT,
    CONF_TIMEOUT,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_OFF
)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_ARGUMENTS = "arguments"

SUPPORT_VDR = (
    SUPPORT_PAUSE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PLAY
    | SUPPORT_STOP
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PREVIOUS_TRACK
)

CONF_DEFAULT_NAME = "vdr"

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=CONF_DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=6419): cv.port,
    vol.Optional(CONF_TIMEOUT, default=10): cv.byte,
})

TVSTATIONS_LOGOS = {
    "Das Erste HD": 71,
    "ZDF HD": 37,
    "SAT.1": 39,
    "RTL Television": 38,
    "RTL2": 41,
    "ProSieben": 40,
    "VOX": 42,
    "kabel eins": 44,
    "ONE HD": 146,
    "3Sat HD": 56,
    "SIXX": 694,
    "WELT": 175,
    "ntv": 66,
    "Super RTL": 43,
    "ProSieben MAXX": 783,
    "ServusTV HD": 660,
    "ZDF_neo HD": 659,
    "WDR Köln HD": 46
}


def get_logo_url(chan_name):
    if chan_name in TVSTATIONS_LOGOS:
        return "https://senderlogos.images.dvbdata.com/302x190_w/{}.png".format(TVSTATIONS_LOGOS[chan_name])
    else:
        return ""


def setup_platform(hass, config, add_entities, discovery_info=None):
    _LOGGER.debug('Set up VDR with hostname , timeout=')

    """Set up the vdr platform."""
    from pyvdr import PYVDR

    conf_name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    _LOGGER.debug('Set up VDR with hostname {}, timeout={}'.format(host, config['timeout']))

    pyvdr_con = PYVDR(hostname=host)

    add_entities(
        [VdrDevice(conf_name, pyvdr_con)]
    )


class VdrDevice(MediaPlayerEntity):
    """Representation of a vdr player."""

    def __init__(self, name, pyvdr):
        """Initialize the vdr device."""
        self._pyvdr = pyvdr
        self._name = name
        self._volume = None
        self._muted = None
        self._state = None
        self._media_position_updated_at = None
        self._media_position = None
        self._media_title = None
        self._media_artist = None
        self._media_album_name = None
        self._media_duration = None
        self._media_image_url = None

    def update(self):
        """Get the latest details from the device."""
        try:
            channel = self._pyvdr.get_channel()
            if channel is None:
                return False

            epg_info = self._pyvdr.get_channel_epg_info(channel_no=channel['number'])

            self._media_artist = channel['name']
            self._media_title = epg_info.Title
            self._state = STATE_PLAYING
            self._media_image_url = get_logo_url(channel['name'])
        except Exception:
            self._state = STATE_OFF
            self._media_artist = None
            self._media_title = None
            _LOGGER.exception('Unable to update media player data.')
        return True

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def media_title(self):
        """Return the title of current playing media."""
        return self._media_title or None

    @property
    def media_artist(self):
        return self._media_artist or None

    @property
    def media_album_name(self):
        return self._media_album_name or None

    @property
    def media_image_url(self):
        return self._media_image_url or None

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_VDR

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self._media_duration

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        return self._media_position

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid."""
        return self._media_position_updated_at

    def media_seek(self, position):
        """Seek the media to a specific location."""
        track_length = 1000

    def mute_volume(self, mute):
        """Mute the volume."""
        self._muted = mute

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._volume = volume

    def media_play(self):
        """Send play command."""
        self._state = STATE_PLAYING

    def media_pause(self):
        """Send pause command."""
        self._state = STATE_PAUSED

    def media_stop(self):
        """Send stop command."""
        self._state = STATE_IDLE

    def media_next_track(self):
        """Send stop command."""
        self._pyvdr.channel_up()

    def media_previous_track(self):
        """Send stop command."""
        self._pyvdr.channel_down()

    def play_media(self, media_type, media_id, **kwargs):
        """Play media from a URL or file."""
        if not media_type == MEDIA_TYPE_MUSIC:
            _LOGGER.error(
                "Invalid media type %s. Only %s is supported",
                media_type,
                MEDIA_TYPE_MUSIC,
            )
            return
        self._state = STATE_PLAYING