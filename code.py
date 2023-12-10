import board
import digitalio
import time
import usb_hid

import adafruit_ble as able
#from adafruit_ble.advertising import Advertisement
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.standard.hid import HIDService
from adafruit_hid.Keyboard import Keyboard
import layers as lyr
from layers import Layers
from scancodes import Scancodes as _

import gc

class Kbd_Matrix:
    def __init__(s, inputs, outputs, pullup=True):
        s.pullup = pullup
        s.inputs = tuple(s.set_input(name) for name in inputs)  #TO CHECK
        s.outputs = tuple(s.set_output(name) for name in outputs)
        s.rows = s.inputs if len(s.inputs) < len(s.outputs) else s.outputs #assumes that there are less rows than columns
        s.cols = s.inputs if len(s.inputs) > len(s.outputs) else s.outputs
        s.length = len(s.inputs) * len(s.outputs)
        s.old_state = 0
        s._not = 0 if pullup else (1 << s.length) - 1
    def set_output(s,pin_name):
        pin = digitalio.DigitalInOut(getattr(board,pin_name))
        pin.direction = digitalio.Direction.OUTPUT
        pin.value = s.pullup
        return pin
    def set_input(s,pin_name):
        pin = digitalio.DigitalInOut(getattr(board, pin_name))
        pin.direction = digitalio.Direction.INPUT
        pin.pull = getattr( digitalio.Pull, "UP" if s.pullup else "DOWN" )
        return pin

    def bnot(s,num):
        #note : it's been a while since I made it. Have a hard time figuring out
        # the exact purpose of it. However, if it ever does make problems, I suggest
        # replacing the sub operator with a xor operator, as there is no chance
        # it does return a negative result.
        return s._not - num

    def scan(s):
        """returns the state of physical keys
        NOTE : returned state is automatically converted (if necessary)
        in a pulldown logic"""
        res = 0
        len_row = len(s.cols)
        pullup = s.pullup
        logic = s._index_logic_columns_are_inputs if s.cols is s.inputs else s._index_logic_rows_are_inputs 
        for a, pin_out in enumerate(s.outputs):
            pin_out.value = not pullup
            for b, pin_in in enumerate(s.inputs):
                v = pin_in.value
                if v :
                    res |= v << logic(a,b, len_row)
            pin_out.value = pullup
        return s.bnot(res) if pullup else res

    def get_report(s):
        """ returns 3 lists of indices, repectively:
        newly released keys,
        newly pressed keys,
        previously pressed keys"""
        new_state = s.scan()
        diff = s.old_state ^ new_state
        nre = diff & s.old_state  # nre : N(ewly) RE(leased)
        npr = diff & new_state  # npr : N(ewly) PR(essed)
        ppr = s.bnot(diff) & new_state  # ppr : P(revioulsy) PR(essed)
        nre_idx = []
        npr_idx = []
        ppr_idx = []
        max = ( 1 << s.length ) - 1
        for x in range( s.length ) :
            filt = 1 << x
            if filt & nre :
                nre_idx.append(x)
            elif filt & npr :
                npr_idx.append(x)
            elif filt & ppr:
                ppr_idx.append(x)
            mask = max - ( ( 1 << ( x + 1 ) ) - 1 )
            nre, npr, ppr = mask & nre, mask & npr, mask & ppr
            if not any((nre,npr, ppr)):
                break
        s.old_state = new_state
        return nre_idx, npr_idx, ppr_idx

    @staticmethod
    def _index_logic_columns_are_inputs (a, b, len_row) :
        return a * len_row + b

    @staticmethod
    def _index_logic_rows_are_inputs (a, b, len_row) :
        return b * len_row + a

matrix = Kbd_Matrix(
    ("D13", "D12", "D11", "D10", "D9"),
    ("A0", "A1", "A2", "A3", "A4", "A5", "SCK", "MOSI", "MISO", "D2", "RX", "TX", "SDA", "SCL", "D7" ),
    pullup = False
) #TODO : set row and col pins
layout = Layers((15,5))

# let's create the key functions that allows the switching to other layers
KPAD = layout.MOTO("keypad", restore=False)
NAV = layout.MOKEY("navigation", _.SPACE,  restore=False, timing=0.08)
KRAK = layout.TOGGLE("kraken", restore=False)

layout.set_default_layer((
    _.ESC,       _.NUM_1,    _.NUM_2, _.NUM_3, _.NUM_4, _.NUM_5, _.NUM_6, _.NUM_7, _.NUM_8, _.NUM_9,         _.NUM_0,  _.MINUS,         _.EQUALS,    _.BACKSLASH, _.DELETE,
    _.TAB,       None,       _.Q,     _.W,     _.E,     _.R,     _.T,     _.Y,     _.U,     _.I,             _.O,      _.P,             _.L_BRACKET, _.R_BRACKET, _.BACKSPACE,
    _.CAPS_LOCK, None,       _.A,     _.S,     _.D,     _.F,     _.G,     _.H,     _.J,     _.K,             _.L,      _.SEMICOLON,     _.QUOTE,     None,        _.ENTER,
    _.L_SHIFT,   None,       _.Z,     _.X,     _.C,     _.V,     _.B,     _.N,     _.M,     _.COMMA,         _.PERIOD, _.FORWARD_SLASH, None,        _.R_SHIFT,   None,
    _.L_CTRL,    _.L_CTRL,   _.WIN,   _.L_ALT, KPAD,    NAV,     None,    _.SPACE, _.R_ALT, _.FORWARD_SLASH, KRAK,     None,            None,        None,        None
))

layout.add_layer(
    "keypad",(
    _.TRANS, _.F1,    _.F2,    _.F3,    _.F4,    _.F5,    _.F6,    _.F7,     _.F8,        _.F9,    _.F10,   _.F11,       _.F12,    _.TRANS,    _.TRANS,
    _.TRANS, None,    None,    None,    None,    None,    None,    _.KP_MIN, _.KP_7 ,     _.KP_8 , _.KP_9 , None,        None,     _.TRANS,    _.TRANS,
    _.TRANS, None,    None,    None,    None,    None,    None,    _.KP_ADD, _.KP_4 ,     _.KP_5 , _.KP_6 , _.KP_MUL,    None,     None,       _.TRANS,
    _.TRANS, None,    None,    None,    None,    None,    None,    _.KP_DIV, _.KP_1 ,     _.KP_2 , _.KP_3 , None,        None,     _.KP_ENTER, _.TRANS,
    _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.SPACE, None,    _.KP_0,   _.KP_PERIOD, _.TRANS, _.TRANS, _.TRANS,     None,     _.TRANS,    _.TRANS
))

layout.add_layer(
    "navigation",(
    _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS,     _.TRANS,     _.TRANS,     _.TRANS,  _.TRANS, _.TRANS, _.TRANS, _.TRANS,
    _.TRANS, None,    _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.HOME,      _.PAGE_DOWN, _.PAGE_UP,   _.END  ,  _.TRANS, _.TRANS, _.TRANS, _.TRANS,
    _.TRANS, None,    _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.LEFT,      _.DOWN ,     _.UP   ,     _.RIGHT,  _.TRANS, _.TRANS, None,    _.TRANS,
    _.TRANS, None,    _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.BACKSPACE, _.TRANS,     _.TRANS,     _.DELETE, _.TRANS, None,    _.TRANS, _.TRANS,
    _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, None,    _.TRANS,     _.TRANS,     _.TRANS,     _.TRANS,  _.TRANS, None,    _.TRANS, _.TRANS
))

layout.add_layer(
    "kraken",(
    _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS,   _.TRANS, _.TRANS,  _.TRANS,
    _.TRANS, None,    _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS,   _.TRANS, _.TRANS,  _.TRANS,
    _.TRANS, None,    _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS,   _.TRANS,    None,  _.TRANS,
    _.TRANS, None,    _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.PAGE_UP, _.TRANS,    _.UP,  _.PAGE_DOWN,
    _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.TRANS, None,    _.TRANS, _.TRANS, _.TRANS, _.TRANS, _.LEFT,    _.TRANS,  _.DOWN,  _.RIGHT
))

del FKEYS, KPAD, NAV

def main_loop(layout, matrix):
    # NOTE : there may be a problem when release_all() is triggered :
    # indeed, while keys are realease to the host,
    # these changes are not reflected in the matrix state.
    hid = HIDService()
    advertisement = ProvideServicesAdvertisement(hid)
    advertisement.appearance = 961
    ble = able.BLERadio()
    if ble.connected :
        for c in ble.connections :
            c.disconnect()
    ble.start_advertising(advertisement)
    advertising = True
    ble_keyboard = Keyboard(hid.devices)

    #(deprecated ?) old_state = (1<<matrix.length)-1
    print("success")
    while 1:
        # ...
        if ble.connected :
            advertising = False
            new_released, new_pressed, old_pressed = matrix.get_report()
            keys = []
            layers = []
            repress = False
            for key in (layout[idx] for idx in new_released):
                if key not in (None, _.TRANS) :
                    if callable(key): # if key function
                        if (type(key) is lyr.MOMENTARY ) or \
                            (type(key) is lyr.MOTO and key.beyond_timing()) or \
                            (type(key) is lyr.MOKEY and key.beyond_timing()):
                            keys.extend(layout[idx] for idx in old_pressed)
                            repress = True
                        elif (type(key) is lyr.MOKEY and not key.beyond_timing()):
                            ble_keyboard.press(key.key)
                            keys.append(key.key)
                        layers.append(key.depress)
                    elif type(key) is int:
                        keys.append(key)
            ble_keyboard.release(*keys)
            keys = []
            for key in (layout[idx] for idx in new_pressed):
                if key not in (None, _.TRANS) :
                    if callable(key):
                        if not repress:
                            repress = True
                            ble_keyboard.release(*(layout[idx] for idx in old_pressed))
                        layers.append(key.press)
                    elif type(key) is int:
                        if layout.tapped() :
                            ble_keyboard.press(key)
                            layout.untap()
                        else :
                            keys.append(key)
            for func in layers : func()
            if repress :
                keys.extend(layout[idx] for idx in old_pressed)
            ble_keyboard.press(*keys)
            gc.collect()

        elif not ble.connected and not advertising :
            ble.start_advertising(advertisement)
            advertising = True
        time.sleep(0.002)

if __name__ == '__main__':
    main_loop(layout, matrix)
