"""Draws the pictures and writes the PDF files of the example.

Everything is made here, from nothing: the pictures are shapes that Qt draws
on an image (no text, no font, no photo), and the PDF files are written byte
by byte with the base fonts that every reader has. So no file of the package
has a license of its own.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field
import json
import math

from PyQt6.QtCore import QBuffer
from PyQt6.QtCore import QByteArray
from PyQt6.QtCore import QIODevice
from PyQt6.QtCore import QPointF
from PyQt6.QtCore import QRectF
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush
from PyQt6.QtGui import QColor
from PyQt6.QtGui import QImage
from PyQt6.QtGui import QLinearGradient
from PyQt6.QtGui import QPainter
from PyQt6.QtGui import QPainterPath
from PyQt6.QtGui import QPen

from arm_facts import ARM_MASS_KG
from arm_facts import AXES
from arm_facts import CYCLE_RATE
from arm_facts import GRIP_FORCE_N
from arm_facts import GRIP_STROKE_MM
from arm_facts import MANUFACTURER
from arm_facts import MAXIMUM_POWER_W
from arm_facts import MAXIMUM_VACUUM_KPA
from arm_facts import NOMINAL_POWER_W
from arm_facts import PAYLOAD_KG
from arm_facts import PRODUCT_NAME
from arm_facts import REACH_MM
from arm_facts import REPEATABILITY_MM
from arm_facts import TCP_SPEED_M_S

SIZE = (960, 640)


def _color(name: str) -> QColor:
    return QColor(name)


def _canvas(width: int, height: int) -> tuple[QImage, QPainter]:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    return image, painter


def _png(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(data)


def _background(painter: QPainter, width: int, height: int) -> None:
    gradient = QLinearGradient(0, 0, 0, height)
    gradient.setColorAt(0, _color("#f4f7fb"))
    gradient.setColorAt(1, _color("#dde6f0"))
    painter.fillRect(0, 0, width, height, QBrush(gradient))


def _link(
    painter: QPainter, start: QPointF, end: QPointF, width: float, fill: str
) -> None:
    painter.setPen(
        QPen(_color("#16324f"), width + 6, cap=Qt.PenCapStyle.RoundCap)
    )
    painter.drawLine(start, end)
    painter.setPen(QPen(_color(fill), width, cap=Qt.PenCapStyle.RoundCap))
    painter.drawLine(start, end)
    painter.setPen(
        QPen(
            _color("#ffffff"),
            max(2.0, width / 8),
            cap=Qt.PenCapStyle.RoundCap,
        )
    )
    painter.setOpacity(0.35)
    offset = QPointF(-width / 5, -width / 5)
    painter.drawLine(start + offset, end + offset)
    painter.setOpacity(1.0)


def _joint(painter: QPainter, center: QPointF, radius: float) -> None:
    painter.setPen(QPen(_color("#16324f"), 4))
    painter.setBrush(_color("#1f3f63"))
    painter.drawEllipse(center, radius, radius)
    painter.setBrush(_color("#cfd9e6"))
    painter.drawEllipse(center, radius * 0.45, radius * 0.45)


def draw_arm() -> bytes:
    """Draws the arm picking a part, in side view.

    Returns:
        A PNG file.
    """
    width, height = SIZE
    image, painter = _canvas(width, height)
    _background(painter, width, height)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_color("#5b6675"))
    painter.drawRect(QRectF(0, 530, width, 110))
    painter.setBrush(_color("#47505c"))
    painter.drawRect(QRectF(0, 530, width, 12))
    # The base and the pedestal.
    painter.setBrush(_color("#3b4654"))
    painter.drawRoundedRect(QRectF(225, 498, 150, 34), 8, 8)
    painter.setBrush(_color("#4a5a6e"))
    painter.drawRect(QRectF(262, 440, 76, 60))
    base, shoulder = QPointF(300, 440), QPointF(300, 380)
    elbow, wrist1 = QPointF(470, 230), QPointF(650, 255)
    wrist2, flange = QPointF(705, 305), QPointF(705, 352)
    _link(painter, base, shoulder, 56, "#2b6cb0")
    _link(painter, shoulder, elbow, 46, "#3182ce")
    _link(painter, elbow, wrist1, 38, "#2b6cb0")
    _link(painter, wrist1, wrist2, 30, "#3182ce")
    _link(painter, wrist2, flange, 28, "#2b6cb0")
    for center, radius in (
        (base, 34),
        (shoulder, 31),
        (elbow, 28),
        (wrist1, 23),
        (wrist2, 21),
        (flange, 18),
    ):
        _joint(painter, center, radius)
    # The gripper, with two fingers that hold the part.
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_color("#2d3748"))
    painter.drawRoundedRect(QRectF(668, 366, 74, 24), 5, 5)
    painter.setBrush(_color("#8a97a8"))
    painter.drawRoundedRect(QRectF(672, 390, 12, 66), 3, 3)
    painter.drawRoundedRect(QRectF(726, 390, 12, 66), 3, 3)
    painter.setBrush(_color("#ed8936"))
    painter.drawRoundedRect(QRectF(684, 408, 42, 42), 4, 4)
    # The place target and the path of the part.
    painter.setBrush(_color("#c6f6d5"))
    painter.setPen(QPen(_color("#38a169"), 3, Qt.PenStyle.DashLine))
    painter.drawRoundedRect(QRectF(820, 482, 56, 48), 4, 4)
    path = QPainterPath(QPointF(705, 470))
    path.cubicTo(QPointF(740, 380), QPointF(820, 380), QPointF(848, 470))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(_color("#38a169"), 4, Qt.PenStyle.DashLine))
    painter.drawPath(path)
    painter.end()
    return _png(image)


def draw_thumbnail() -> bytes:
    """Draws a small version of the arm picture.

    Returns:
        A PNG file.
    """
    image = QImage.fromData(draw_arm(), "PNG").scaled(
        240,
        160,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    return _png(image)


def draw_envelope() -> bytes:
    """Draws the area that the arm reaches, in top view.

    Returns:
        A PNG file.
    """
    width, height = SIZE
    image, painter = _canvas(width, height)
    _background(painter, width, height)
    center = QPointF(width / 2, height / 2)
    scale = 280 / REACH_MM
    outer = REACH_MM * scale
    painter.setPen(QPen(_color("#2b6cb0"), 3))
    painter.setBrush(_color("#bee3f8"))
    painter.drawEllipse(center, outer, outer)
    # The wedge behind the base, which the first joint does not reach.
    painter.setBrush(_color("#fed7d7"))
    painter.setPen(QPen(_color("#c53030"), 2, Qt.PenStyle.DashLine))
    rect = QRectF(center.x() - outer, center.y() - outer, 2 * outer, 2 * outer)
    painter.drawPie(rect, int(265 * 16), int(10 * 16))
    painter.setPen(QPen(_color("#718096"), 1, Qt.PenStyle.DotLine))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for fraction in (0.25, 0.5, 0.75):
        painter.drawEllipse(center, outer * fraction, outer * fraction)
    for angle in range(0, 360, 45):
        painter.drawLine(
            center,
            center
            + QPointF(
                outer * math.cos(math.radians(angle)),
                outer * math.sin(math.radians(angle)),
            ),
        )
    painter.setPen(QPen(_color("#16324f"), 4))
    painter.setBrush(_color("#3b4654"))
    painter.drawEllipse(center, 22, 22)
    # The pick pose and the place pose of the example job.
    painter.setPen(QPen(_color("#c05621"), 3))
    painter.setBrush(_color("#ed8936"))
    pick = QPointF(center.x() + 0.30 * outer, center.y() - 0.55 * outer)
    painter.drawRect(QRectF(pick.x() - 14, pick.y() - 14, 28, 28))
    painter.setPen(QPen(_color("#2f855a"), 3))
    painter.setBrush(_color("#68d391"))
    place = QPointF(center.x() - 0.45 * outer, center.y() - 0.25 * outer)
    painter.drawRect(QRectF(place.x() - 14, place.y() - 14, 28, 28))
    painter.setPen(QPen(_color("#38a169"), 3, Qt.PenStyle.DashLine))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawLine(pick, place)
    painter.end()
    return _png(image)


def draw_logo() -> bytes:
    """Draws the logo of the fictional manufacturer.

    Returns:
        A PNG file.
    """
    image, painter = _canvas(256, 256)
    painter.fillRect(0, 0, 256, 256, _color("#ffffff"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_color("#16324f"))
    painter.drawRoundedRect(QRectF(16, 16, 224, 224), 40, 40)
    hexagon = QPainterPath()
    for index in range(6):
        angle = math.radians(60 * index - 30)
        point = QPointF(128 + 78 * math.cos(angle), 128 + 78 * math.sin(angle))
        if index == 0:
            hexagon.moveTo(point)
        else:
            hexagon.lineTo(point)
    hexagon.closeSubpath()
    painter.setBrush(_color("#3182ce"))
    painter.drawPath(hexagon)
    painter.setPen(QPen(_color("#ffffff"), 16, cap=Qt.PenCapStyle.RoundCap))
    painter.drawLine(QPointF(96, 168), QPointF(128, 108))
    painter.drawLine(QPointF(128, 108), QPointF(170, 120))
    painter.setBrush(_color("#ed8936"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(QPointF(172, 122), 14, 14)
    painter.end()
    return _png(image)


def draw_marking() -> bytes:
    """Draws a symbol for the marking of the nameplate.

    It is a plain crossed circle, so that nobody takes it for the mark of a
    real conformity or certification.

    Returns:
        A PNG file.
    """
    image, painter = _canvas(128, 128)
    painter.fillRect(0, 0, 128, 128, _color("#ffffff"))
    painter.setPen(QPen(_color("#4a5568"), 8))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QPointF(64, 64), 50, 50)
    painter.setPen(QPen(_color("#c53030"), 8, cap=Qt.PenCapStyle.RoundCap))
    painter.drawLine(QPointF(34, 34), QPointF(94, 94))
    painter.drawLine(QPointF(94, 34), QPointF(34, 94))
    painter.end()
    return _png(image)


# ---- PDF


@dataclass
class _Page:
    """The content stream of one page, in points from the lower left corner."""

    operations: list[str] = field(default_factory=list)

    def text(
        self,
        x: float,
        y: float,
        text: str,
        size: float = 10,
        bold: bool = False,
        color: str = "0 0 0",
    ) -> None:
        escaped = (
            text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        )
        font = "F2" if bold else "F1"
        self.operations.append(
            f"BT {color} rg /{font} {size} Tf {x} {y} Td ({escaped}) Tj ET"
        )

    def rule(self, x1: float, y: float, x2: float) -> None:
        self.operations.append(f"0.6 G 0.5 w {x1} {y} m {x2} {y} l S")


def _pdf(pages: Sequence[_Page]) -> bytes:
    """Writes a PDF file with the base fonts, without compression."""
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    add(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{5 + 2 * i} 0 R" for i in range(len(pages)))
    add(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    add(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>"
    )
    add(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
        b"/Encoding /WinAnsiEncoding >>"
    )
    for index, page in enumerate(pages):
        stream = "\n".join(page.operations).encode("cp1252")
        add(
            (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                "/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
                f"/Contents {6 + 2 * index} 0 R >>"
            ).encode()
        )
        add(
            b"<< /Length "
            + str(len(stream)).encode()
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    ).encode()
    return bytes(out)


_RED = "0.77 0.19 0.19"


def _title(page: _Page, title: str, subtitle: str, notice: str) -> float:
    page.text(50, 790, title, 20, bold=True)
    page.text(50, 770, subtitle, 11)
    page.text(50, 752, notice, 9, bold=True, color=_RED)
    page.rule(50, 742, 545)
    return 722


def _table(
    page: _Page, top: float, rows: Sequence[tuple[str, str]], gap: float = 18
) -> float:
    y = top
    for label, value in rows:
        page.text(50, y, label, 10, bold=True)
        page.text(250, y, value, 10)
        y -= gap
        page.rule(50, y + gap - 5, 545)
    return y


def datasheet() -> bytes:
    """Writes the datasheet of the arm.

    Returns:
        A PDF file of one page, in English.
    """
    page = _Page()
    y = _title(
        page,
        PRODUCT_NAME,
        "Datasheet: 6-axis arm for pick and place",
        "FICTIONAL EXAMPLE. The data is made up and describes no real product.",
    )
    y = _table(
        page,
        y,
        [
            ("Manufacturer", MANUFACTURER),
            ("Axes", "6, rotary"),
            ("Rated payload", f"{PAYLOAD_KG:g} kg, tool included"),
            ("Maximum reach", f"{REACH_MM:g} mm"),
            ("Pose repeatability", f"+/- {REPEATABILITY_MM:g} mm"),
            ("Tool center point speed", f"up to {TCP_SPEED_M_S:g} m/s"),
            ("Pick and place cycle rate", f"{CYCLE_RATE:g} cycles/min"),
            ("Mass of the arm", f"{ARM_MASS_KG:g} kg"),
            (
                "Power consumption",
                f"{NOMINAL_POWER_W:g} W nominal, {MAXIMUM_POWER_W:g} W peak",
            ),
            ("Supply", "100 to 240 V AC, 47 to 63 Hz"),
            ("Ingress protection", "IP54 arm, IP20 controller"),
            ("Ambient temperature", "0 to 45 deg C in operation"),
            ("Mounting", "floor, ceiling or wall"),
            (
                "Gripper",
                f"2 fingers, {GRIP_STROKE_MM:g} mm stroke, "
                f"{GRIP_FORCE_N[0]:g} to {GRIP_FORCE_N[1]:g} N",
            ),
            ("Vacuum option", f"-{MAXIMUM_VACUUM_KPA:g} kPa"),
        ],
    )
    page.text(50, y - 12, "Joints", 12, bold=True)
    y -= 34
    page.text(50, y, "Joint", 9, bold=True)
    page.text(200, y, "Range (deg)", 9, bold=True)
    page.text(330, y, "Speed (deg/s)", 9, bold=True)
    for axis in AXES:
        y -= 16
        page.text(50, y, f"J{axis.number}  {axis.name[0]}", 9)
        page.text(200, y, f"{axis.low:g} to {axis.high:g}", 9)
        page.text(330, y, f"{axis.speed:g}", 9)
    return _pdf([page])


_QUICKSTART = {
    "en": (
        "Quick start",
        "Fictional example. Not a real manual.",
        [
            "1. Bolt the base to a rigid table with four M8 bolts.",
            "2. Connect the arm to the controller and the controller to the mains.",
            "3. Clear the area of the arm, then switch the controller on.",
            "4. Select the mode AUTOMATIC and load the job from the station.",
            "5. Press Start. The arm picks, places and returns home.",
            "Stop the arm with the emergency stop before you reach into its area.",
        ],
    ),
    "de": (
        "Kurzanleitung",
        "Fiktives Beispiel. Kein echtes Handbuch.",
        [
            "1. Die Basis mit vier M8-Schrauben auf einem steifen Tisch festschrauben.",
            "2. Den Arm an die Steuerung und die Steuerung ans Netz anschließen.",
            "3. Den Bereich des Arms räumen, dann die Steuerung einschalten.",
            "4. Die Betriebsart AUTOMATIC wählen und den Auftrag der Station laden.",
            "5. Start drücken. Der Arm nimmt auf, legt ab und fährt zurück.",
            "Den Arm mit dem Not-Halt stoppen, bevor man in seinen Bereich greift.",
        ],
    ),
}


def quickstart(language: str) -> bytes:
    """Writes the quick start guide.

    Args:
        language: `en` or `de`.

    Returns:
        A PDF file of one page.
    """
    title, notice, steps = _QUICKSTART[language]
    page = _Page()
    y = _title(page, PRODUCT_NAME, title, notice)
    for step in steps:
        page.text(50, y, step, 11)
        y -= 24
    return _pdf([page])


def calibration() -> bytes:
    """Writes the calibration data that the Blob element holds.

    Returns:
        JSON text as bytes: the zero offset of each joint in degrees.
    """
    offsets = {
        f"J{axis.number}": round(0.02 * ((axis.number * 7) % 5 - 2), 3)
        for axis in AXES
    }
    document = {
        "example": "fictional",
        "measuredAt": "2026-03-15",
        "unit": "deg",
        "zeroOffsets": offsets,
    }
    return json.dumps(document, indent=2, sort_keys=True).encode("utf-8")
