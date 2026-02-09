import unittest
from unittest.mock import patch

from prusa.connect.client import camera_v2_pb2 as pb
from prusa.connect.client.camera import PrusaCameraClient


class TestPrusaCameraClient(unittest.TestCase):
    def setUp(self):
        self.camera_token = "test-token"
        self.signaling_url = "http://signaling.example.com"
        self.client = PrusaCameraClient(self.camera_token, self.signaling_url)

    @patch("socketio.Client")
    def test_connect(self, mock_sio_class):
        mock_sio = mock_sio_class.return_value
        self.client.sio = mock_sio

        self.client.connect()

        mock_sio.connect.assert_called_with(
            self.signaling_url, auth={"token": self.camera_token}, transports=["websocket"]
        )

    @patch("socketio.Client")
    def test_authenticate(self, mock_sio_class):
        mock_sio = mock_sio_class.return_value
        self.client.sio = mock_sio
        self.client.jwt_token = "test-jwt"

        self.client._authenticate()

        # Verify event name and that data is bytes (serialized protobuf)
        args, _kwargs = mock_sio.emit.call_args
        self.assertEqual(args[0], "client_authentication")

        # Decode and verify payload
        auth_pb = pb.ClientAuthentication()
        auth_pb.ParseFromString(args[1])
        self.assertEqual(auth_pb.camera_token, self.camera_token)
        self.assertEqual(auth_pb.client_type, "user")
        self.assertEqual(auth_pb.client_jwt_token, "test-jwt")

    @patch("socketio.Client")
    def test_move_command(self, mock_sio_class):
        mock_sio = mock_sio_class.return_value
        self.client.sio = mock_sio

        self.client.move("LEFT", angle=45)

        args, _kwargs = mock_sio.emit.call_args
        self.assertEqual(args[0], "configuration")

        # Decode and verify payload
        cmd_pb = pb.ServerToCamera()
        cmd_pb.ParseFromString(args[1])
        self.assertEqual(cmd_pb.camera_token, self.camera_token)
        self.assertEqual(cmd_pb.control.rotation.direction, pb.LEFT)
        self.assertEqual(cmd_pb.control.rotation.angle, 45)

    @patch("socketio.Client")
    def test_move_command_int(self, mock_sio_class):
        mock_sio = mock_sio_class.return_value
        self.client.sio = mock_sio

        # Pass enum value directly (which is an int)
        self.client.move(pb.RIGHT, angle=10)

        args, _kwargs = mock_sio.emit.call_args
        self.assertEqual(args[0], "configuration")

        # Decode and verify payload
        cmd_pb = pb.ServerToCamera()
        cmd_pb.ParseFromString(args[1])
        self.assertEqual(cmd_pb.control.rotation.direction, pb.RIGHT)
        self.assertEqual(cmd_pb.control.rotation.angle, 10)

    @patch("socketio.Client")
    def test_adjust_command(self, mock_sio_class):
        mock_sio = mock_sio_class.return_value
        self.client.sio = mock_sio

        self.client.adjust(brightness=50, contrast=-20)

        args, _kwargs = mock_sio.emit.call_args
        self.assertEqual(args[0], "configuration")

        # Decode and verify payload
        cmd_pb = pb.ServerToCamera()
        cmd_pb.ParseFromString(args[1])
        self.assertEqual(cmd_pb.camera_token, self.camera_token)
        self.assertEqual(cmd_pb.control.brightness, 50)
        self.assertEqual(cmd_pb.control.contrast, -20)

    @patch("socketio.Client")
    def test_trigger_command(self, mock_sio_class):
        mock_sio = mock_sio_class.return_value
        self.client.sio = mock_sio

        self.client.trigger(get_snapshot=pb.FEATURE_ENABLED)

        args, _kwargs = mock_sio.emit.call_args
        self.assertEqual(args[0], "trigger")

        # Decode and verify payload
        trigger_pb = pb.CameraTrigger()
        trigger_pb.ParseFromString(args[1])
        self.assertEqual(trigger_pb.camera_token, self.camera_token)
        self.assertEqual(trigger_pb.get_snapshot, pb.FEATURE_ENABLED)


if __name__ == "__main__":
    unittest.main()
