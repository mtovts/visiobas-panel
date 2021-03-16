import asyncio
import logging
from json import loads, JSONDecodeError
from pathlib import Path
from time import time

import busio
import digitalio
from adafruit_mcp230xx.mcp23008 import MCP23008

from obj_type import ObjType

_log = logging.getLogger(__name__)

try:
    import board
except NotImplementedError as e:
    _log.critical(e)


class I2CConnector:  # (Thread):
    def __init__(self, visio_mqtt_client, config: dict):  # , gateway):
        # super().__init__()
        # self.setName(name=f'{self}-Thread')
        # self.setDaemon(True)

        self.mqtt_client = visio_mqtt_client

        self._config = config

        self.i2c = busio.I2C(board.SCL, board.SDA)

        # init i2c buses
        self.bi_busses = [MCP23008(self.i2c, address=addr)
                          for addr in self.bi_bus_ids]

        self.bo_busses = [MCP23008(self.i2c, address=addr)
                          for addr in self.bo_bus_ids]
        _log.debug(f'Buses: bo={self.bo_bus_ids} bi={self.bi_bus_ids}')

        # init pins
        self.bi_pins = {}
        for bus, bus_addr in zip(self.bi_busses, self.bi_bus_ids):
            pins = []
            for i in range(8):
                pin = bus.get_pin(i)
                pin.direction = digitalio.Direction.INPUT
                pin.pull = digitalio.Pull.UP
                pins.append(pin)

            self.bi_pins[bus_addr] = pins

        self.bo_pins = {}
        for bus, bus_addr in zip(self.bo_busses, self.bo_bus_ids):
            pins = []
            for i in range(8):
                pin = bus.get_pin(i)
                pin.switch_to_output(value=True)
                pins.append(pin)

            self.bo_pins[bus_addr] = pins

        self._polling_buses = self.bi_bus_ids

        self._last_values = {bi_bus_id: {0: None,
                                         1: None,
                                         2: None,
                                         3: None,
                                         4: None,
                                         5: None,
                                         6: None,
                                         7: None,
                                         } for bi_bus_id in self.bi_bus_ids}

    @property
    def bi_bus_ids(self):
        return list(self._config.get('bi_buses', {}).keys())

    @property
    def bo_bus_ids(self):
        return list(self._config.get('bo_buses', {}).keys())

    @classmethod
    def from_yaml(cls, visio_mqtt_client, yaml_path: Path):
        import yaml

        with yaml_path.open() as cfg_file:
            i2c_cfg = yaml.load(cfg_file, Loader=yaml.FullLoader)
            _log.info(f'Creating {cls.__name__} from {yaml_path} ... \n{i2c_cfg}')
        return cls(visio_mqtt_client=visio_mqtt_client,
                   config=i2c_cfg
                   )

    def __repr__(self):
        return self.__class__.__name__

    @property
    def pins(self):  # -> dict[int, list]:
        return {**self.bi_pins, **self.bo_pins}

    @property
    def device_id(self):  # -> int
        return self.mqtt_client.device_id

    def publish(self, topic, payload=None, qos=0, retain=False):
        # topic: str, payload: str = None, qos: int = 0,
        # retain: bool = True) -> mqtt.MQTTMessageInfo:
        return self.mqtt_client.publish(topic=topic,
                                        payload=payload,
                                        qos=qos,
                                        retain=retain
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

    # def run(self) -> None:
    #     asyncio.run(self.start_polling())

    async def start_polling(self):
        _log.info(f'Start polling: {self._polling_buses}')

        for bus_id in self._polling_buses:
            # await asyncio.ensure_future(
            await asyncio.create_task(
                self.start_bus_polling(
                    bus_id=bus_id,
                    realtime_interval=self.get_realtime_interval(bus_id=bus_id),
                    mqtt_interval=self.get_mqtt_interval(bus_id=bus_id),
                    start_time=time()
                ))

    async def start_bus_polling(self, bus_id,
                                realtime_interval, mqtt_interval,
                                start_time) -> None:

        start_time_expired = False
        while bus_id in self._polling_buses:
            _t0 = time()
            for pin_id in range(len(self.bi_pins[bus_id])):
                rvalue = self.read_i2c(bus_id=bus_id, pin_id=pin_id)

                # if rvalue != self.get_default(bus_id=bus_id, pin_id=pin_id):
                #     _log.debug('Non-default value - pub')
                #     topic = self.get_topic(bus_id=bus_id, pin_id=pin_id)
                #     payload = '{0} {1} {2} {3}'.format(self.device_id,
                #                                        ObjType.BINARY_INPUT.id,
                #                                        f'{bus_id}0{pin_id}',
                #                                        int(rvalue),
                #                                        )
                #     self.publish(topic=topic, payload=payload,
                #                  qos=1, retain=True)

                if rvalue != self._last_values[bus_id][pin_id]:
                    self._last_values[bus_id][pin_id] = rvalue
                    _log.debug('Not equal last value - pub')

                    topic = self.get_topic(bus_id=bus_id, pin_id=pin_id)
                    payload = '{0} {1} {2} {3}'.format(self.device_id,
                                                       ObjType.BINARY_INPUT.id,
                                                       f'{bus_id}0{pin_id}',
                                                       int(rvalue),
                                                       )
                    self.publish(topic=topic, payload=payload,
                                 qos=1, retain=True)

                elif (time() - start_time) >= mqtt_interval:
                    start_time_expired = True
                    _log.debug('Default value. Expired interval - pub')
                    topic = self.get_topic(bus_id=bus_id, pin_id=pin_id)
                    payload = '{0} {1} {2} {3}'.format(self.device_id,
                                                       ObjType.BINARY_INPUT.id,
                                                       f'{bus_id}0{pin_id}',
                                                       int(rvalue),
                                                       )
                    self.publish(topic=topic, payload=payload,
                                 qos=0, retain=False)
            if start_time_expired:
                start_time = time()
                start_time_expired = False  # TODO: for start sending poll?

            _t_delta = time() - _t0
            delay = (realtime_interval - _t_delta) * 0.9
            _log.info(f'Bus: {bus_id} polled for {round(_t_delta, ndigits=4)} sec '
                      f'sleeping {round(delay, ndigits=4)} sec ...')
            await asyncio.sleep(delay)

    def get_topic(self, bus_id, pin_id):  # -> str:
        topic = self.mqtt_client.publish_topics[bus_id]['pin_topic'].get(pin_id)
        if topic is None:
            topic = self.mqtt_client.publish_topics[bus_id]['bus_topic']
        return topic

    def get_default(self, bus_id, pin_id):  # -> bool
        buses = {**self._config['bo_buses'], **self._config['bi_buses']}

        default_value = buses[bus_id]['default'].get(pin_id)
        if default_value is None:
            default_value = buses[bus_id]['default']['bus']
        return default_value

    def get_mqtt_interval(self, bus_id):  # -> int:
        return self.mqtt_client.bus_intervals[bus_id]

    def get_realtime_interval(self, bus_id):  # -> float
        return self._config['bi_buses'][bus_id]['realtime_interval']

    def get_pulse_delay(self, bus_id, pin_id):
        return self._config['bo_buses'][bus_id]['pulse_delay'][pin_id]

    async def rpc_value_panel(self, params):
        # params: dict) -> None:

        # todo: validate params

        _log.debug(f'Processing \'value\' method with params: {params}')

        obj_id = params['object_identifier']
        # first two numbers in object_id contains bus address.
        # Then going pin number.
        # Example: obj_id=3701 -> bus_address=37, pin=01
        bus_id = int(str(obj_id)[:2])
        pin_id = int(str(obj_id)[2:])

        if params['object_type'] == ObjType.BINARY_OUTPUT.id:
            delay = self.get_pulse_delay(bus_id=bus_id, pin_id=pin_id)
            value = bool(params['value'])

            if value == self.get_default(bus_id=bus_id, pin_id=pin_id):
                _log.debug(f'Received default value: {value}')
                return

            if delay:
                await self._wr_p_s_wr_p(value=value, bus_id=bus_id, pin_id=pin_id,
                                        delay=delay)
            else:
                self._wr_p(value=value, bus_id=bus_id, pin_id=pin_id)

        elif params['object_type'] == ObjType.BINARY_INPUT.id:
            self._r_p(bus_id=bus_id, pin_id=pin_id)
        else:
            raise ValueError(
                f'Expected only {ObjType.BINARY_INPUT} or {ObjType.BINARY_OUTPUT}')

    def read_i2c(self, bus_id, pin_id):  #: int):  # , obj_type: int, dev_id: int) -> bool:
        try:
            # inverting because False=turn on, True=turn off
            v = not self.pins[bus_id][pin_id].value
            _log.debug(f'Read: bus={bus_id} pin={pin_id} value={v}')
            return v
        except LookupError as e:
            _log.warning(e,
                         exc_info=True
                         )
        except ValueError:
            _log.warning('Please, provide correct object_id (for splitting to bus and pin)')

    def _r_p(self, bus_id, pin_id):
        value = self.read_i2c(bus_id=bus_id, pin_id=pin_id)
        payload = '{0} {1} {2} {3}'.format(self.device_id,
                                           ObjType.BINARY_INPUT.id,
                                           f'{bus_id}0{pin_id}',
                                           value,
                                           )
        self.publish(topic=self.get_topic(bus_id=bus_id, pin_id=pin_id),
                     payload=payload,
                     qos=1, retain=True
                     )

    def write_i2c(self, value, bus_id, pin_id):
        # value: bool, obj_id: int) -> None:  # , obj_type: int, dev_id: int):
        try:
            value = not value
            _log.debug(f'Write bus={bus_id}, pin={pin_id} value={value}')
            self.bo_pins[bus_id][pin_id].value = value

        except LookupError as e:
            _log.warning(e,
                         exc_info=True
                         )
        except ValueError:
            _log.warning('Please, provide correct object_id (for splitting to bus and pin)')

    def _wr_i2c(self, value, bus_id, pin_id):
        # value: bool, obj_id: int  # , obj_type: int, dev_id: int) -> bool:
        self.write_i2c(value=value,
                       bus_id=bus_id,
                       pin_id=pin_id
                       )
        rvalue = self.read_i2c(bus_id=bus_id,
                               pin_id=pin_id
                               )
        res = value == rvalue  # because inverted
        _log.debug(f'Write with check result={res}')
        return res

    def _wr_p(self, value, bus_id, pin_id):
        _is_eq = self._wr_i2c(value=value, bus_id=bus_id, pin_id=pin_id)
        if _is_eq:
            payload = '{0} {1} {2} {3}'.format(self.device_id,
                                               ObjType.BINARY_OUTPUT.id,
                                               f'{bus_id}0{pin_id}',
                                               int(value),
                                               )
            self.publish(topic=self.get_topic(bus_id=bus_id, pin_id=pin_id),
                         payload=payload,
                         qos=1, retain=True
                         )

    async def _wr_p_s_wr_p(self, value, bus_id, pin_id, delay):
        self._wr_p(value=value, bus_id=bus_id, pin_id=pin_id)
        await asyncio.sleep(delay)
        value = not value
        self._wr_p(value=value, bus_id=bus_id, pin_id=pin_id)
