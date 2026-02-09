"""Camera signaling client for Prusa Connect.

This module implements the Socket.io and Protobuf signaling protocol
used by Prusa Connect for real-time camera interaction, including
pan/tilt (PTZ) controls and WebRTC signaling (WebRTC is not fully implemented,
as it is not fully deployed for all users in Prusa Connect).

Note:
    This Socket.io implementation is used within Prusa Connect for
    interactive camera control. If you just wish to trigger a snapshot
    or retreive the most recent snapshot, consider using the REST API instead.
    See `prusa.connect.client.sdk.PrusaConnectClient.get_snapshot` for more information.

How to use the most important parts:
- `PrusaCameraClient`: Instantiate this with a base URL, a Socket.io path,
  your auth token, and the camera's UUID.
- `connect()`, `trigger_snapshot()`, and `move_relative()` are the primary
  methods for interacting with the camera once initialized.
"""

import typing

import socketio
import structlog

from prusa.connect.client import camera_v2_pb2 as pb
from prusa.connect.client import consts as sdk_consts

logger = structlog.get_logger(sdk_consts.APP_NAME)


class PrusaCameraClient:
    """Client for interacting with a Prusa Connect camera via Socket.io/Protobuf."""

    def __init__(
        self,
        camera_token: str,
        signaling_url: str = "https://connect-signaling.prusa3d.com",
        jwt_token: str | None = None,
        fingerprint: str = "python-sdk",
    ):
        """Initializes the camera client.

        Args:
            camera_token: The target camera's unique ID.
            signaling_url: URL for the Prusa Connect signaling server.
            jwt_token: (Optional) User's session JWT for authorized control.
            fingerprint: Unique client fingerprint.
        """
        self.camera_token = camera_token
        self.jwt_token = jwt_token
        self.fingerprint = fingerprint
        self.sio = socketio.Client()
        self.url = signaling_url
        self.features: pb.CameraFeatures | None = None
        self.last_status: pb.CameraToServer | None = None

        # Register Callbacks
        self.sio.on("connect", self._on_connect)
        self.sio.on("disconnect", self._on_disconnect)
        self.sio.on("status", self._on_status)
        self.sio.on("features", self._on_features)
        self.sio.on("client_trigger", self._on_client_trigger)
        self.sio.on("webrtc_offer", self._on_webrtc_offer)
        self.sio.on("webrtc_answer", self._on_webrtc_answer)
        self.sio.on("webrtc_ice_candidate", self._on_webrtc_ice_candidate)

    def connect(self, wait: bool = False):
        """Connects to the signaling server."""
        auth_payload = {"token": self.camera_token}
        logger.debug("Connecting to signaling server", url=self.url, token=self.camera_token)
        self.sio.connect(self.url, auth=auth_payload, transports=["websocket"])
        if wait:
            self.sio.wait()

    def disconnect(self):
        """Disconnects from the signaling server."""
        self.sio.disconnect()

    def _on_connect(self):
        """Callback for successful connection."""
        logger.info("Connected to signaling server.")
        self._authenticate()
        self._sync_state()

    def _on_disconnect(self):
        """Callback for disconnection."""
        logger.info("Disconnected from signaling server.")

    def _authenticate(self):
        """Performs the Protobuf authentication handshake."""
        # If we have a JWT, we act as a "user" (viewer/controller)
        # If we only have a camera_token, we act as a basic "client"
        client_type = "user" if self.jwt_token else "client"

        auth = pb.ClientAuthentication(
            camera_token=self.camera_token,
            client_type=client_type,
            client_jwt_token=self.jwt_token if self.jwt_token else "",
            fingerprint=self.fingerprint,
        )
        logger.debug("Sending client_authentication", client_type=client_type)
        self.sio.emit("client_authentication", auth.SerializeToString())

    def _sync_state(self):
        """Requests initial status and features."""
        trigger = pb.CameraTrigger(
            camera_token=self.camera_token,
            get_status=pb.FEATURE_ENABLED,
            get_features=pb.FEATURE_ENABLED,
        )
        logger.debug("Sending trigger for initial sync")
        self.sio.emit("trigger", trigger.SerializeToString())

    def _on_features(self, data: bytes):
        """Callback for receiving camera features."""
        feat = pb.CameraFeatures()
        feat.ParseFromString(data)
        self.features = feat
        logger.debug("Features updated", ptz=feat.has_ptz, webrtc=feat.has_webrtc)

    def _on_status(self, data: bytes):
        """Callback for receiving camera status updates."""
        status = pb.CameraToServer()
        status.ParseFromString(data)
        self.last_status = status
        logger.debug("Status update received")

    def _on_client_trigger(self, data: bytes):
        """Callback for receiving async task updates."""
        # This can be used for timelapse progress etc.
        logger.debug("Client trigger received")

    def _on_webrtc_offer(self, data: typing.Any):
        """Callback for receiving a WebRTC offer."""
        logger.info("WebRTC offer received")

    def _on_webrtc_answer(self, data: typing.Any):
        """Callback for receiving a WebRTC answer."""
        logger.info("WebRTC answer received")

    def _on_webrtc_ice_candidate(self, data: typing.Any):
        """Callback for receiving a WebRTC ICE candidate."""
        logger.info("WebRTC ICE candidate received")

    # --- Control Methods ---

    def move(self, direction: str | int | pb.RotationDirection.ValueType, angle: int = 30):
        """Sends a pan/tilt move command.

        Args:
            direction: Direction to move. Can be string (LEFT, RIGHT, UP, DOWN)
                       or integer from RotationDirection enum.
            angle: Angle to move in degrees.
        """
        if isinstance(direction, str):
            try:
                dir_enum = pb.RotationDirection.Value(direction.upper())
            except (AttributeError, ValueError):
                # Fallback to getattr if Value doesn't work for some reason,
                # but Value is the standard protobuf way for enums.
                try:
                    dir_enum = getattr(pb, direction.upper())
                except AttributeError as err:
                    raise ValueError(f"Invalid direction: {direction}") from err
        else:
            dir_enum = typing.cast("pb.RotationDirection.ValueType", direction)

        cmd = pb.ServerToCamera(
            camera_token=self.camera_token,
            control=pb.CameraControl(rotation=pb.RotationSettings(direction=dir_enum, angle=angle)),
        )
        logger.debug("Sending move command", direction=direction, angle=angle)
        self.sio.emit("configuration", cmd.SerializeToString())

    def adjust(self, **kwargs: typing.Any):
        """Adjusts camera settings.

        Supported kwargs:
            brightness: int (-100 to 100?)
            contrast: int (-100 to 100?)
            saturation: int (-100 to 100?)
            camera_mode: pb.CameraMode (AUTO, DAY, NIGHT)
            exposure_time: int
            snapshot_interval: int
            volume: int
        """
        control_args = {}
        valid_fields = pb.CameraControl.DESCRIPTOR.fields_by_name
        for key, value in kwargs.items():
            if key in valid_fields:
                control_args[key] = value
            else:
                logger.warning(f"Unsupported adjustment key: {key}")

        if not control_args:
            return

        cmd = pb.ServerToCamera(
            camera_token=self.camera_token,
            control=pb.CameraControl(**control_args),
        )
        logger.debug("Sending adjustment configuration", **control_args)
        self.sio.emit("configuration", cmd.SerializeToString())

    def trigger(self, **kwargs: typing.Any):
        """Sends a trigger for specific actions.

        Supported kwargs:
            get_snapshot: pb.FeatureState
            set_snapshot_enable: pb.FeatureState
            set_timelapse_enable: pb.FeatureState
            start_fw_update: pb.FeatureState
            start_device_reboot: pb.FeatureState
            start_rtsp_server: pb.FeatureState
            start_timelapse_video: pb.FeatureState
        """
        trigger_args = {"camera_token": self.camera_token}
        valid_fields = pb.CameraTrigger.DESCRIPTOR.fields_by_name
        for key, value in kwargs.items():
            if key in valid_fields:
                trigger_args[key] = value
            else:
                logger.warning(f"Unsupported trigger key: {key}")

        trigger = pb.CameraTrigger(**trigger_args)
        logger.debug("Sending trigger", **kwargs)
        self.sio.emit("trigger", trigger.SerializeToString())
