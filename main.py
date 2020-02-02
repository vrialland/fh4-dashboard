from machine import idle, I2C, Pin
import network
from ucollections import namedtuple, OrderedDict
import usocket
import ustruct
import utime

import ssd1306
from config import (
    SSD1306_ADDR,
    SSD1306_SCL,
    SSD1306_SDA,
    SSD1306_HEIGHT,
    SSD1306_WIDTH,
    UDP_PORT,
    WIFI_PASSWORD,
    WIFI_SSID,
)

# Data structure of the sent packets
ATTRS = (
    ("is_race_on", "i"),
    ("timestamp_ms", "I"),
    ("engine_max_rpm", "f"),
    ("engine_idle_rpm", "f"),
    ("current_engine_rpm", "f"),
    ("acceleration_x", "f"),
    ("acceleration_y", "f"),
    ("acceleration_z", "f"),
    ("velocity_x", "f"),
    ("velocity_y", "f"),
    ("velocity_z", "f"),
    ("angular_velocity_x", "f"),
    ("angular_velocity_y", "f"),
    ("angular_velocity_z", "f"),
    ("yaw", "f"),
    ("pitch", "f"),
    ("roll", "f"),
    ("normalized_suspension_travel_front_left", "f"),
    ("normalized_suspension_travel_front_right", "f"),
    ("normalized_suspension_travel_rear_left", "f"),
    ("normalized_suspension_travel_rear_right", "f"),
    ("tire_slip_ratio_front_left", "f"),
    ("tire_slip_ratio_front_right", "f"),
    ("tire_slip_ratio_rear_left", "f"),
    ("tire_slip_ratio_rear_right", "f"),
    ("wheel_rotation_speed_front_left", "f"),
    ("wheel_rotation_speed_front_right", "f"),
    ("wheel_rotation_speed_rear_left", "f"),
    ("wheel_rotation_speed_rear_right", "f"),
    ("wheel_on_rumble_strip_front_left", "i"),
    ("wheel_on_rumble_strip_front_right", "i"),
    ("wheel_on_rumble_strip_rear_left", "i"),
    ("wheel_on_rumble_strip_rear_right", "i"),
    ("wheel_in_puddle_depth_front_left", "f"),
    ("wheel_in_puddle_depth_front_right", "f"),
    ("wheel_in_puddle_depth_rear_left", "f"),
    ("wheel_in_puddle_depth_rear_right", "f"),
    ("surface_rumble_front_left", "f"),
    ("surface_rumble_front_right", "f"),
    ("surface_rumble_rear_left", "f"),
    ("surface_rumble_rear_right", "f"),
    ("tire_slip_angle_front_left", "f"),
    ("tire_slip_angle_front_right", "f"),
    ("tire_slip_angle_rear_left", "f"),
    ("tire_slip_angle_rear_right", "f"),
    ("tire_combined_slip_front_left", "f"),
    ("tire_combined_slip_front_right", "f"),
    ("tire_combined_slip_rear_left", "f"),
    ("tire_combined_slip_rear_right", "f"),
    ("suspension_travel_meters_front_left", "f"),
    ("suspension_travel_meters_front_right", "f"),
    ("suspension_travel_meters_rear_left", "f"),
    ("suspension_travel_meters_rear_right", "f"),
    ("car_ordinal", "i"),
    ("car_class", "i"),
    ("car_performance_index", "i"),
    ("drivetrain_type", "i"),
    ("num_cylinders", "i"),
    # here is an unknown structure of 12 bits "x"*12 datatype on standard" Python
    ("position_x", "f"),
    ("position_y", "f"),
    ("position_z", "f"),
    ("speed", "f"),
    ("power", "f"),
    ("torque", "f"),
    ("tire_temp_front_left", "f"),
    ("tire_temp_front_right", "f"),
    ("tire_temp_rear_left", "f"),
    ("tire_temp_rear_right", "f"),
    ("boost", "f"),
    ("fuel", "f"),
    ("distance_traveled", "f"),
    ("best_lap", "f"),
    ("last_lap", "f"),
    ("current_lap", "f"),
    ("current_race_time", "f"),
    ("lap_number", "H"),
    ("race_position", "B"),
    ("accel", "B"),
    ("brake", "B"),
    ("clutch", "B"),
    ("hand_brake", "B"),
    ("gear", "B"),
    ("steer", "b"),
    ("normalized_driving_line", "b"),
    ("normalized_ai_brake_difference", "b"),
)

# Definitions
UNKNOWN_DATA_INDEX = 58
UNKNOWN_DATA_SIZE = 12

PACKET_FORMAT = "<{}".format("".join(k[1] for k in ATTRS))
PACKET_SIZE = ustruct.calcsize(PACKET_FORMAT)

PACKET_SIZE_BEFORE_UNKNOWN_DATA = ustruct.calcsize(PACKET_FORMAT[:UNKNOWN_DATA_INDEX])


Telemetry = namedtuple("Telemetry", " ".join(k[0] for k in ATTRS))


# SSD1306 setup
i2c = I2C(scl=Pin(SSD1306_SCL), sda=Pin(SSD1306_SDA))
screen = ssd1306.SSD1306_I2C(SSD1306_WIDTH, SSD1306_HEIGHT, i2c, addr=SSD1306_ADDR)


# Formatting
def format_speed(speed_mps):
    return int(speed_mps * 3600 / 1000)


def format_gear(gear):
    return str(gear) if gear else "R"


def setup_wifi():
    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(True)
    screen.fill(0)
    screen.text("Connect", 0, 0)
    screen.text("to", 0, 16)
    screen.text(WIFI_SSID, 0, 32)
    screen.show()
    sta_if.connect(WIFI_SSID, WIFI_PASSWORD)
    while not sta_if.isconnected():
        idle()
    ip = sta_if.ifconfig()[0]
    screen.fill(0)
    screen.text("Server", 0, 0)
    screen.text(ip, 0, 16)
    screen.text("Port {}".format(UDP_PORT), 0, 32)
    screen.show()
    return ip


def serve(ip):
    last_update = 0
    sock = usocket.socket(usocket.AF_INET, usocket.SOCK_DGRAM)
    sock.bind((ip, UDP_PORT))

    while True:
        data = sock.recv(1024)
        now = utime.ticks_ms()
        # Update every 50ms
        if now - last_update < 50:
            continue
        # Remove the 12 unknown bits
        data = (
            data[:PACKET_SIZE_BEFORE_UNKNOWN_DATA]
            + data[PACKET_SIZE_BEFORE_UNKNOWN_DATA + 12 :]
        )
        data = ustruct.unpack(PACKET_FORMAT, data)
        telemetry = Telemetry(*data)
        screen.fill(0)
        if telemetry.engine_max_rpm:  # Can be 0 in menus, or while fast travelling
            width = int(
                SSD1306_WIDTH
                * (telemetry.current_engine_rpm / telemetry.engine_max_rpm)
            )
        else:
            width = 0
        screen.fill_rect(0, 0, width, 10, 1)
        screen.text("Gear: {}".format(format_gear(telemetry.gear)), 0, 20)
        screen.text("{} KM/H".format(format_speed(telemetry.speed)), 0, 40)
        screen.show()
        last_update = now


ip = setup_wifi()
serve(ip)
