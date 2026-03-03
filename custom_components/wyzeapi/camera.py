"""Platform for camera integration."""

from collections.abc import Callable
import logging
from typing import Any

from wyzeapy import Wyzeapy
from wyzeapy.services.camera_service import Camera as WyzeServiceCamera

from homeassistant.components import ffmpeg
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_CLIENT, DOMAIN, RTSP_PASSWORD, RTSP_USERNAME
from .token_manager import token_exception_handler

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
SUPPORTS_RTSP_CAMERA = ["HL_PAN3", "WYZE_CAKP2JFUS"]
PORT = ":322/stream0"


@token_exception_handler
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[list[Any], bool], None],
) -> None:
    """Set up the camera platform."""
    _LOGGER.debug("""Creating new WyzeApi camera component""")
    client: Wyzeapy = hass.data[DOMAIN][config_entry.entry_id][CONF_CLIENT]
    camera_service = await client.camera_service
    camera_username: str | None = config_entry.options.get(RTSP_USERNAME)
    camera_password: str | None = config_entry.options.get(RTSP_PASSWORD)
    cameras = [
        WyzeCamera(device, camera_username, camera_password, camera_service)
        for device in await camera_service.get_cameras()
        if device.product_model in SUPPORTS_RTSP_CAMERA
        and camera_username is not None
        and camera_password is not None
    ]

    async_add_entities(cameras, True)


class WyzeCamera(Camera):
    """Base camera entity."""

    _attr_has_entity_name = True
    _attr_is_streaming = True
    _attr_motion_detection_enabled = False
    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        camera: WyzeServiceCamera,
        camera_username,
        camera_password,
        camera_service,
    ) -> None:
        """Init a camera feed."""
        super().__init__()
        self._device = camera
        self._username = camera_username
        self._password = camera_password
        self._camera_service = camera_service
        self._attr_unique_id = f"{self._device.mac}-camera-entity"
        self._ip_address = self._device.device_params["ip"]
        self._attr_brand = "Wyze"
        self._rtsp_stream: str | None = (
            (f"rtsps://{self._username}:{self._password}@{self._ip_address}{PORT}")
            if self._username is not None and self._password is not None
            else None
        )

    async def stream_source(self) -> str | None:
        """Return the stream source."""
        return self._rtsp_stream

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._device.mac)},
            "name": self._device.nickname,
            "manufacturer": "WyzeLabs",
            "model": self._device.product_model,
        }

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a frame from the camera stream."""
        if self._rtsp_stream:
            return await ffmpeg.async_get_image(
                self.hass, self._rtsp_stream, width=width, height=height
            )
        return None
