import time
from json import loads, JSONDecodeError
from logging import getLogger
from pathlib import Path
from threading import Thread

import paho.mqtt.client as mqtt

from api import I2CConnector
from result_code import ResultCode

_log = getLogger(__name__)
_base_dir = Path(__file__).resolve().parent


class VisioMQTTClient:  # (Thread):
    """Control interactions via MQTT."""

    def __init__(self,
                 # gateway,
                 config: dict,
                 # getting_queue: SimpleQueue = None
                 ):
        # """
        # :param gateway: Gateway or Panel
        # """
        # super().__init__()
        # self.setName(name=f'{self}-Thread')
        # self.setDaemon(True)

        # self._gateway = gateway
        # self._getting_queue = getting_queue
        self._config = config

        self._host = self._config['host']
        self._port = self._config['port']

        self._username = self._config['username']
        self._password = self._config['password']

        self._qos = self._config.get('qos', 0)
        self._retain = self._config.get('retain', True)

        self._stopped = False
        self._connected = False

        self._client = mqtt.Client(
            transport='tcp',
            # transport='websockets'
        )
        # self._client.tls_set()
        # self._client.enable_logger()  # logger=logger
        self._client.username_pw_set(username=self._username, password=self._password)

        # Set up external MQTT broker callbacks
        self._client.on_connect = self._on_connect_cb
        self._client.on_disconnect = self._on_disconnect_cb
        self._client.on_subscribe = self._on_subscribe_cb
        self._client.on_message = self._on_message_cb
        self._client.on_publish = self._on_publish_cb

        self.api = I2CConnector.from_yaml(visio_mqtt_client=self,
                                          yaml_path=_base_dir / 'i2c.yaml'
                                          )
        poll_tread = Thread(target=self.api.run, daemon=True)
        poll_tread.start()

        # self.api.start()
        self.topics = [(topic, self._qos) for topic in self._config['subscribe']]

    def __repr__(self) -> str:
        return self.__class__.__name__

    @classmethod
    def from_yaml(cls, yaml_path: Path):
        import yaml

        with yaml_path.open() as cfg_file:
            mqtt_cfg = yaml.load(cfg_file, Loader=yaml.FullLoader)
            _log.info(f'Creating {cls.__name__} from {yaml_path} ...')
        return cls(  # gateway=gateway,
            # getting_queue=getting_queue,
            config=mqtt_cfg
        )

    @property
    def device_id(self):  # -> int:
        return self._config['device_id']

    @property
    def bus_intervals(self):  # -> dict[int, int]
        d = {}
        for bus_id in self._config['publish']:
            d[bus_id] = self._config['publish'][bus_id]['interval']
        return d

    @property
    def publish_topics(self):  # -> dict[int, dict]
        return self._config['publish']

    def run(self):
        """Main loop."""

        while not self._stopped:  # not self._connected and
            if self._connected:
                self._run_loop()
            else:
                try:
                    self.connect(host=self._host,
                                 port=self._port
                                 )
                except ConnectionRefusedError as e:
                    _log.warning(f'Cannot connect to broker: {e}')
                    time.sleep(10)
                except Exception as e:
                    _log.error(f'Connection to broker error: {e}',
                               exc_info=True
                               )

    def _run_loop(self):
        """Designed as an endless loop. CAn be stopped from gateway thread."""
        # self.subscribe(topics=self.topics)
        while not self._stopped:
            try:
                time.sleep(60 * 5)

            except Exception as e:
                _log.warning(f'Receive-publish error: {e}',
                             exc_info=True
                             )
        else:  # received stop signal
            _log.info(f'{self} stopped.')

    def stop(self) -> None:
        self._stopped = True
        _log.info(f'Stopping {self} ...')
        self.disconnect()

    def connect(self, host, port=1883):
        # host: str, port: int = 1883):
        """Connect to broker."""
        self._client.connect(host=host,
                             port=port,
                             )
        self._client.reconnect_delay_set()
        # self.subscribe(topics=self.topics)
        self._client.loop_forever(retry_first_connection=True)

    def disconnect(self):
        self._client.disconnect()
        _log.debug(f'{self._client} Disconnecting from broker')
        self._connected = False
        self._client.loop_stop()

    def subscribe(self, topics):  # : Sequence[tuple[str, int]]):
        """
        Topics example:
         [("my/topic", 0), ("another/topic", 2)]
         """
        result, mid = self._client.subscribe(topic=topics)
        if result == mqtt.MQTT_ERR_SUCCESS:
            _log.debug(f'Subscribed to topics: {topics}')
        elif result == mqtt.MQTT_ERR_NO_CONN:
            _log.warning(f'Not subscribed to topic: {topics} {result} {mid}')

    def publish(self, topic, payload=None, qos=0, retain=False):
        # topic: str, payload: str = None, qos: int = 0,
        # retain: bool = False) -> mqtt.MQTTMessageInfo:
        return self._client.publish(topic=topic,
                                    payload=payload,
                                    qos=qos,
                                    retain=retain
                                    )

    def _on_publish_cb(self, client, userdata, mid):
        # _log.debug(f'Published: {client} {userdata} {mid}')
        pass

    def _on_connect_cb(self, client, userdata, flags, rc, properties=None):
        if rc == ResultCode.CONNECTION_SUCCESSFUL.rc:
            self._connected = True
            _log.info('Successfully connected to broker')
            self.subscribe(topics=self.topics)
            # Subscribing in on_connect() means that if we lose the connection and
            # reconnect then subscriptions will be renewed.
        else:
            _log.warning(f'Failed connection to broker: {ResultCode(rc)}')

    def _on_disconnect_cb(self, client, userdata, rc):
        # self._connected = False
        _log.warning(f'Disconnected: {ResultCode(rc)}')
        # self._client.loop_stop()

    def _on_subscribe_cb(self, userdata, mid, granted_qos, properties=None):
        try:
            if granted_qos == 128:
                _log.warning('Subscription failed')
            else:
                _log.debug('Subscription success')
        except Exception as e:
            _log.error(f'Error: {e}',
                       exc_info=True
                       )

    def _on_message_cb(self, client, userdata, message):  #: mqtt.MQTTMessage):
        msg_dct = self.decode(msg=message)
        _log.debug(f'Received {message.topic}:{msg_dct}')
        try:
            if msg_dct['params'].get('device_id') == self._config['device_id']:
                if msg_dct.get('method') == 'value':
                    # TODO: ADD THREAD POOL
                    rpc_value_tread = Thread(target=self.api.rpc_value,
                                             kwargs={'params': msg_dct['params']},
                                             daemon=True
                                             )
                    rpc_value_tread.start()

        except Exception as e:
            _log.warning(f'Error: {e} :{msg_dct}',
                         exc_info=True
                         )

    @staticmethod
    def decode(msg):  # mqtt.MQTTMessage):
        try:
            if isinstance(msg.payload, bytes):
                content = loads(msg.payload.decode("utf-8", "ignore"))
            else:
                content = loads(msg.payload)
        except JSONDecodeError:
            if isinstance(msg.payload, bytes):
                content = msg.payload.decode("utf-8", "ignore")
            else:
                content = msg.payload
        return content
