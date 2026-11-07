"""Live values, the temperature history and the documentation of the arm.

The operational data and the documentation are the example's own submodels.
The temperature history follows the IDTA template Time Series Data 1.1.1.
"""

import datetime

from basyx.aas import model
from basyx.aas.model import datatypes
from dateutil.relativedelta import relativedelta

from arm_facts import AXES
from arm_files import calibration
from arm_helpers import DATASHEET_PATH
from arm_helpers import ENVELOPE_PATH
from arm_helpers import PICTURE_PATH
from arm_helpers import collection
from arm_helpers import external
from arm_helpers import file_element
from arm_helpers import link
from arm_helpers import listing
from arm_helpers import meaning
from arm_helpers import mlp
from arm_helpers import moment
from arm_helpers import own_submodel
from arm_helpers import prop
from arm_helpers import qualifier
from arm_helpers import span
from arm_skills import HOME
from arm_skills import pose
from arm_templates import Template
from arm_templates import like


def _live(seconds: int) -> list[model.Qualifier]:
    return [
        qualifier(
            "UpdateInterval", relativedelta, relativedelta(seconds=seconds)
        )
    ]


def operational_data() -> model.Submodel:
    """Builds the live values of the arm.

    Returns:
        A submodel with the state, the mode, the counters, the six joints, the
        pose, the gripper and the last error. The reference to the current
        state and to the temperature history are set by
        `arm_links.link_all`.
    """
    joints = listing(
        "JointStates",
        model.SubmodelElementCollection,
        [
            collection(
                None,
                [
                    prop("AxisNumber", int, axis.number),
                    prop("ActualJointPosition", float, axis.position),
                    prop(
                        "JointTemperature",
                        float,
                        axis.temperature,
                        qualifiers=_live(1),
                    ),
                    prop("MotorCurrent", float, axis.current),
                ],
                "JointState",
            )
            for axis in AXES
        ],
        "JointState",
    )
    gripper = collection(
        "GripperStatus",
        [
            prop("GripperPosition", float, 80.0),
            prop("ObjectInGripper", bool, False),
            prop("VacuumLevel", float, 0.0),
            prop("ActualGripForce", float, 0.0),
        ],
    )
    last_error = collection(
        "LastError",
        [
            prop("ErrorCode", str, "E-1042"),
            mlp(
                "ErrorMessage",
                "Vacuum below the threshold while placing",
                "Unterdruck beim Ablegen unter dem Grenzwert",
                "Vácuo abaixo do limite ao colocar",
            ),
            prop("ErrorSeverity", str, "WARNING", coded=True),
            prop(
                "ErrorTimestamp",
                datetime.datetime,
                moment(2026, 10, 30, 14, 22, 5),
            ),
            prop("ErrorAcknowledged", bool, True),
        ],
    )
    elements: list[model.SubmodelElement] = [
        prop("CurrentState", str, "Idle", coded=True, qualifiers=_live(1)),
        link("CurrentStateReference", None),  # pyright: ignore[reportArgumentType]
        prop("OperatingMode", str, "AUTOMATIC", coded=True),
        prop(
            "CycleCount",
            datatypes.UnsignedLong,
            18452,
            qualifiers=_live(10),
        ),
        prop("OperatingHours", float, 1260.5),
        joints,
        pose("ToolCenterPoint", "ToolCenterPoint", HOME),
        gripper,
        last_error,
        link("TemperatureHistory", None),  # pyright: ignore[reportArgumentType]
        span("ObservedTemperatureRange", float, 36.2, 44.8),
    ]
    return own_submodel(
        "OperationalData", "OperationalData", elements, "OperationalSubmodel"
    )


def _temperature(axis_index: int, record: int) -> float:
    """Gives the temperature of one joint at one record of the history.

    The last record is the value that the operational data shows now, and the
    joints warm up by a few tenths of a degree in every step.
    """
    return round(AXES[axis_index].temperature - 0.4 * (5 - record), 1)


def temperature_history() -> model.Submodel:
    """Builds the time series of the joint temperatures.

    Returns:
        The submodel, from the template Time Series Data 1.1.1, with one
        internal segment of six records, ten seconds apart.
    """
    t = Template("series")
    metadata = t.at("Metadata")
    variables = [
        prop(
            f"Joint{axis.number}Temperature",
            float,
            None,
        )
        for axis in AXES
    ]
    meta = like(
        metadata,
        children=[
            like(
                t.at("Metadata", "Name"),
                {
                    "en": "Joint temperatures of the first test cycle",
                    "de": "Gelenktemperaturen des ersten Testzyklus",
                    "pt": "Temperaturas das juntas do primeiro ciclo de teste",
                },
            ),
            like(
                t.at("Metadata", "Description"),
                {
                    "en": "Motor housing temperatures of the six joints, one record every ten seconds.",
                    "de": "Motorgehäusetemperaturen der sechs Gelenke, alle zehn Sekunden ein Datensatz.",
                    "pt": "Temperaturas da carcaça dos motores das seis juntas, um registro a cada dez segundos.",
                },
            ),
            like(
                t.at("Metadata", "Record"),
                children=[
                    like(
                        t.at("Metadata", "Record", "Time"),
                        None,
                        id_short="Time01",
                    ),
                    *variables,
                ],
            ),
        ],
    )
    segment_t = t.at("Segments", "InternalSegment")

    def attribute(
        name: str, value: object, **extra: object
    ) -> model.SubmodelElement:
        return like(segment_t.get_referable(name), value, **extra)  # pyright: ignore[reportAttributeAccessIssue]

    records = [
        like(
            t.at("Segments", "InternalSegment", "Records", "Record"),
            id_short=f"Record{index + 1:02d}",
            children=[
                like(
                    t.at(
                        "Segments",
                        "InternalSegment",
                        "Records",
                        "Record",
                        "Time",
                    ),
                    10 * index,
                    id_short="Time01",
                ),
                *[
                    prop(
                        f"Joint{axis.number}Temperature",
                        float,
                        _temperature(position, index),
                    )
                    for position, axis in enumerate(AXES)
                ],
            ],
        )
        for index in range(6)
    ]
    segment = like(
        segment_t,
        children=[
            attribute(
                "Name",
                {
                    "en": "First test cycle",
                    "de": "Erster Testzyklus",
                    "pt": "Primeiro ciclo de teste",
                },
            ),
            attribute(
                "Description",
                {
                    "en": "Six records while the arm ran its first job after commissioning.",
                    "de": "Sechs Datensätze, während der Arm nach der Inbetriebnahme seinen ersten Auftrag fuhr.",
                    "pt": "Seis registros enquanto o braço executava sua primeira tarefa após o comissionamento.",
                },
            ),
            attribute("RecordCount", 6),
            attribute("StartTime", "2026-11-06T09:00:00Z"),
            attribute("EndTime", "2026-11-06T09:00:50Z"),
            attribute("Duration", "PT50S"),
            attribute("SamplingInterval", 10),
            attribute(
                "State",
                "completed",
                # The value of the enumeration, as the specification of the
                # template writes it for a finished segment.
                value_id=external(
                    "https://admin-shell.io/idta/TimeSeries/Segment/State/Completed/1/1"
                ),
            ),
            attribute("LastUpdate", "2026-11-06T09:00:50Z"),
            like(
                t.at("Segments", "InternalSegment", "Records"),
                children=records,
            ),
        ],
    )
    elements = [meta, like(t.at("Segments"), children=[segment])]
    return t.instance("TimeSeries", elements)


def documentation() -> model.Submodel:
    """Builds the documentation: texts, files and one Blob.

    Returns:
        A submodel with multi-language texts in English, German and
        Portuguese, three files of the package, and a Blob of calibration
        data.
    """
    keywords = [
        ("Robot arm", "Roboterarm", "Braço robótico"),
        ("Pick and place", "Pick-and-Place", "Pegar e colocar"),
        ("Six axes", "Sechs Achsen", "Seis eixos"),
        ("Example", "Beispiel", "Exemplo"),
    ]
    elements: list[model.SubmodelElement] = [
        mlp(
            "ProductOverview",
            "A six-axis arm with a payload of 6 kg and a reach of 900 mm. It picks parts and places them with a repeatability of 0.03 mm.",
            "Ein sechsachsiger Arm mit 6 kg Nutzlast und 900 mm Reichweite. Er nimmt Teile auf und legt sie mit einer Wiederholgenauigkeit von 0,03 mm ab.",
            "Um braço de seis eixos com carga de 6 kg e alcance de 900 mm. Ele pega peças e as coloca com repetibilidade de 0,03 mm.",
        ),
        mlp(
            "ExampleDisclaimer",
            "This package is an example. The arm, the company and all numbers are made up, and no part of it describes a real product.",
            "Dieses Paket ist ein Beispiel. Der Arm, die Firma und alle Zahlen sind erfunden, und nichts davon beschreibt ein reales Produkt.",
            "Este pacote é um exemplo. O braço, a empresa e todos os números são inventados, e nada nele descreve um produto real.",
        ),
        mlp(
            "SafetyNotice",
            "A moving arm can hurt people. Keep out of its area while the drives are on.",
            "Ein bewegter Arm kann Menschen verletzen. Der Bereich ist bei eingeschalteten Antrieben zu meiden.",
            "Um braço em movimento pode ferir pessoas. Mantenha-se fora de sua área enquanto os acionamentos estiverem ligados.",
        ),
        listing(
            "SearchKeywords",
            model.MultiLanguageProperty,
            [
                mlp(None, *words, concept_name="SearchKeyword")
                for words in keywords
            ],
            "SearchKeyword",
        ),
        file_element("ArmPicture", PICTURE_PATH, "image/png"),
        file_element("DatasheetFile", DATASHEET_PATH, "application/pdf"),
        file_element("WorkEnvelopeDrawing", ENVELOPE_PATH, "image/png"),
        model.Blob(
            "JointCalibration",
            "application/json",
            calibration(),
            **meaning("JointCalibration"),
        ),
    ]
    return own_submodel(
        "Documentation", "Documentation", elements, "DocumentationSubmodel"
    )
