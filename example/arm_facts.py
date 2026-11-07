"""The numbers of the fictional arm, in one place.

The nameplate, the technical data, the datasheet and the operational data all
read from here, so that they agree. Nothing here describes a real product.
"""

from dataclasses import dataclass

PRODUCT_NAME = "Workingbench Example Arm PP-6"
MANUFACTURER = "Workingbench Example Robotics (fictional)"

PAYLOAD_KG = 6.0
REACH_MM = 900.0
REPEATABILITY_MM = 0.03
TCP_SPEED_M_S = 1.2
ARM_MASS_KG = 28.0
CYCLE_RATE = 30.0
NOMINAL_POWER_W = 180.0
MAXIMUM_POWER_W = 600.0
DC_BUS_V = 48.0
SUPPLY_VOLTAGE_V = (100.0, 240.0)
SUPPLY_FREQUENCY_HZ = (47.0, 63.0)
OPERATING_TEMPERATURE_C = (0.0, 45.0)
STORAGE_TEMPERATURE_C = (-20.0, 60.0)
HUMIDITY_PERCENT = (20.0, 80.0)
NOISE_DB_A = 62.0
GRIP_STROKE_MM = 80.0
GRIP_FORCE_N = (20.0, 80.0)
MAXIMUM_VACUUM_KPA = 80.0
PART_MASS_KG = (0.01, 5.2)
PART_SIZE_MM = (5.0, 80.0)


@dataclass(frozen=True)
class Axis:
    """One joint of the arm.

    Attributes:
        number: The position in the chain, from the base.
        name: The name in English, German and Portuguese.
        low: The smallest angle in degrees.
        high: The largest angle in degrees.
        speed: The largest speed in degrees per second.
        temperature: The temperature now, in degrees Celsius.
        position: The angle now, in degrees.
        current: The motor current now, in amperes.
    """

    number: int
    name: tuple[str, str, str]
    low: float
    high: float
    speed: float
    temperature: float
    position: float
    current: float


AXES = (
    Axis(1, ("Base rotation", "Basisdrehung", "Rotação da base"), -175.0, 175.0, 180.0, 41.2, 12.5, 0.9),
    Axis(2, ("Shoulder", "Schulter", "Ombro"), -130.0, 130.0, 180.0, 44.8, -62.0, 2.4),
    Axis(3, ("Elbow", "Ellbogen", "Cotovelo"), -150.0, 150.0, 200.0, 43.1, 98.0, 1.7),
    Axis(4, ("Wrist 1", "Handgelenk 1", "Punho 1"), -190.0, 190.0, 300.0, 38.9, -35.5, 0.6),
    Axis(5, ("Wrist 2", "Handgelenk 2", "Punho 2"), -120.0, 120.0, 300.0, 37.5, 90.0, 0.5),
    Axis(6, ("Wrist 3", "Handgelenk 3", "Punho 3"), -360.0, 360.0, 400.0, 36.2, 0.0, 0.3),
)  # fmt: skip
