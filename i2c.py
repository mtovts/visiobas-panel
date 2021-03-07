import busio
from adafruit_mcp230xx.mcp23008 import MCP23008
from digitalio import Direction, Pull

try:
    import board
except (ImportError, NotImplementedError) as e:
    from logging import getLogger

    _log = getLogger(__name__)
    _log.critical(f'Error: {e}',
                  # exc_info=True
                  )


class I2CRWMixin:

    @staticmethod
    def read_i2c(obj_id: int, obj_type: int, dev_id: int) -> bool:
        """
        :param obj_id: first two numbers contains bus address. Then going pin number.
                Example: obj_id=3701 -> bus_address=37, pin=01
        """
        bus_addr = int(str(obj_id)[:2])
        pin_id = int(str(obj_id)[2:])

        i2c = busio.I2C(board.SCL, board.SDA)  # Initialize the I2C bus
        obj_di = MCP23008(i2c, bus_addr)

        pin_di = obj_di.get_pin(pin_id)
        pin_di.direction = Direction.INPUT
        pin_di.pull = Pull.UP

        return pin_di.value

        # mcp_di = MCP23008(i2c, address=0x25)
        # mcp_do = MCP23008(i2c, address=0x26)

        # if obj_type == ObjType.BINARY_INPUT.id:

        # todo obj.gpio? check on yard!

        # pins_in = [mcp_di.get_pin(i) for i in range(8)]
        # pins_out = [mcp_do.get_pin(i) for i in range(8)]
        # [pin.switch_to_output(value=True) for pin in pins_out]
        #
        # for pin in pins_in:
        #     pin.direction = digitalio.Direction.INPUT
        #     pin.pull = digitalio.Pull.UP

        # # Now loop blinking the pin 0 output and reading the state of pin 1 input.
        # while True:
        #     for pin in pins_out:
        #         pin.value = False  # turn on
        #         time.sleep(0.2)
        #         pin.value = True  # turn off

    @staticmethod
    def write_i2c(value: bool, obj_id: int, obj_type: int, dev_id: int):
        """
        :param value: True - Turn off. False - Turn on
        :param dev_id: in hex. Example: 0x25
        """
        bus_addr = int(str(obj_id)[:2])
        pin_id = int(str(obj_id)[2:])

        # Initialize the I2C bus:
        i2c = busio.I2C(board.SCL, board.SDA)  # Initialize the I2C bus
        obj_do = MCP23008(i2c, bus_addr)

        pin_out = obj_do.get_pin(pin_id)
        pin_out.switch_to_output(value=True)
        pin_out.value = bool(value)
        # if obj_type == ObjType.BINARY_OUTPUT.id:

    def write_with_check_i2c(self, value: bool, obj_id: int, obj_type: int, dev_id: int
                             ) -> bool:
        """
        :return: the read value is equal to the written value
        """
        self.write_i2c(value=value,
                       obj_id=obj_id,
                       obj_type=obj_type,
                       dev_id=dev_id
                       )
        rvalue = self.read_i2c(obj_id=obj_id,
                               obj_type=obj_type,
                               dev_id=dev_id
                               )
        return value == rvalue
