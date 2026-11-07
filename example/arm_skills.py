"""What the arm can do and how: capabilities, operations, cycle, job, station.

These four submodels are the example's own. No bundled template covers them,
so their semantics are the concept descriptions of this package.

References between elements are set after the submodels exist, in
`arm_links.py`, because a model reference needs its target to be in the tree.
"""

import datetime

from basyx.aas import model
from basyx.aas.model import datatypes
from dateutil.relativedelta import relativedelta

from arm_concepts import NAMESPACE
from arm_helpers import SERIAL_NUMBER
from arm_helpers import collection
from arm_helpers import extension
from arm_helpers import external
from arm_helpers import find
from arm_helpers import link
from arm_helpers import listing
from arm_helpers import meaning
from arm_helpers import mlp
from arm_helpers import moment
from arm_helpers import own_submodel
from arm_helpers import prop
from arm_helpers import qualifier
from arm_helpers import reference_to
from arm_helpers import span

Pose = tuple[float, float, float, float, float, float]

HOME: Pose = (350.0, 0.0, 450.0, 180.0, 0.0, 0.0)
PICK: Pose = (420.0, -250.0, 25.0, 180.0, 0.0, 90.0)
PLACE: Pose = (-300.0, 380.0, 40.0, 180.0, 0.0, 0.0)
TOPIC = f"example/pp6/{SERIAL_NUMBER}/events"
# The steps of the capability pick and place, in order. The same capability
# can be a step twice, so the steps are numbered and not named.
STEPS = ("MoveToPose", "PickObject", "MoveToPose", "PlaceObject")


def pose(
    id_short: str | None, concept_name: str, values: Pose
) -> model.SubmodelElementCollection:
    """Builds a pose: a position in millimeters and an orientation in degrees.

    Args:
        id_short: The idShort, or None for an item of a list.
        concept_name: `Pose` or `ToolCenterPoint`.
        values: X, Y, Z, roll, pitch and yaw.

    Returns:
        The collection.
    """
    keys = ("PoseX", "PoseY", "PoseZ", "PoseRoll", "PosePitch", "PoseYaw")
    return collection(
        id_short,
        [
            prop(key, float, value)
            for key, value in zip(keys, values, strict=True)
        ],
        concept_name,
    )


def capabilities() -> model.Submodel:
    """Builds the submodel of the capabilities and operations.

    Returns:
        A submodel with four capabilities, their constraints, and the three
        operations that carry them out.
    """

    def cap(id_short: str, concept_name: str) -> model.Capability:
        return model.Capability(id_short, **meaning(concept_name))

    def operation(
        id_short: str,
        concept_name: str,
        limit: float,
        inputs: list[model.SubmodelElement],
        outputs: list[model.SubmodelElement],
        in_outputs: list[model.SubmodelElement],
    ) -> model.Operation:
        return model.Operation(
            id_short,
            input_variable=inputs,
            output_variable=outputs,
            in_output_variable=in_outputs,
            qualifier=[qualifier("MaxExecutionTime", float, limit)],
            extension=[extension("SafetyRelevant", bool, True)],
            **meaning(concept_name),
        )

    def speed() -> model.Property:
        return prop("Speed", float, 50.0, "SpeedOverride")

    def result() -> model.Property:
        return prop("Result", str, "OK", "OperationResult", coded=True)

    def cycle_counter() -> model.Property:
        return prop("CycleCounter", datatypes.UnsignedLong, 18452, "CycleCount")

    constraints = collection(
        "PickAndPlaceConstraints",
        [
            span("PartMassRange", float, 0.01, 5.2),
            span("PartSizeRange", float, 5.0, 80.0),
            listing(
                "GripMethods",
                model.Property,
                [
                    prop(None, str, "PARALLEL_FINGERS", "GripMethod", True),
                    prop(None, str, "VACUUM", "GripMethod", True),
                ],
                "GripMethod",
                "GripMethods",
                str,
            ),
        ],
        "CapabilityConstraints",
    )
    operations = [
        operation(
            "Pick",
            "PickOperation",
            10.0,
            [
                pose("TargetPose", "Pose", PICK),
                prop("ApproachHeight", float, 50.0),
                speed(),
                prop("GripForce", float, 40.0),
                prop("GripMethod", str, "PARALLEL_FINGERS", coded=True),
            ],
            [result(), prop("MeasuredGripWidth", float, 42.0)],
            [pose("ToolCenterPoint", "ToolCenterPoint", PICK)],
        ),
        operation(
            "Place",
            "PlaceOperation",
            10.0,
            [
                pose("TargetPose", "Pose", PLACE),
                prop("ApproachHeight", float, 50.0),
                speed(),
            ],
            [result()],
            [cycle_counter()],
        ),
        operation(
            "MoveTo",
            "MoveToOperation",
            20.0,
            [
                pose("TargetPose", "Pose", HOME),
                speed(),
                prop("MotionType", str, "JOINT", coded=True),
            ],
            [result(), prop("TravelTime", float, 1.35)],
            [pose("ToolCenterPoint", "ToolCenterPoint", HOME)],
        ),
    ]
    relations: list[model.SubmodelElement] = [
        model.RelationshipElement(
            f"ImplementedBy_{capability}",
            None,
            None,
            **meaning("CapabilityImplementedBy"),
        )
        for capability in ("PickObject", "PlaceObject", "MoveToPose")
    ]
    composition = [
        model.AnnotatedRelationshipElement(
            f"Step{order}",
            None,
            None,
            annotation=[prop("CompositionOrder", int, order)],
            **meaning("CapabilityComposedOf"),
        )
        for order, _ in enumerate(STEPS, 1)
    ]
    elements: list[model.SubmodelElement] = [
        cap("PickAndPlace", "PickAndPlaceCapability"),
        cap("PickObject", "PickCapability"),
        cap("PlaceObject", "PlaceCapability"),
        cap("MoveToPose", "MoveCapability"),
        constraints,
        *operations,
        *relations,
        *composition,
    ]
    return own_submodel(
        "Capabilities", "Capabilities", elements, "CapabilitiesSubmodel"
    )


_STATES = (
    (
        "Idle",
        "The arm waits at home for a job.",
        "Der Arm wartet in der Ausgangslage auf einen Auftrag.",
        "O braço espera na posição inicial por uma tarefa.",
    ),
    (
        "MovingToPick",
        "The arm moves to the pick pose with the gripper open.",
        "Der Arm fährt mit offenem Greifer zur Aufnahmepose.",
        "O braço vai à pose de coleta com a garra aberta.",
    ),
    (
        "Gripping",
        "The gripper closes on the part and checks the grip.",
        "Der Greifer schließt sich um das Teil und prüft den Griff.",
        "A garra fecha sobre a peça e verifica a preensão.",
    ),
    (
        "MovingToPlace",
        "The arm carries the part to the place pose.",
        "Der Arm trägt das Teil zur Ablagepose.",
        "O braço leva a peça até a pose de colocação.",
    ),
    (
        "Releasing",
        "The gripper opens and the part stays at the place pose.",
        "Der Greifer öffnet sich und das Teil bleibt an der Ablagepose.",
        "A garra abre e a peça fica na pose de colocação.",
    ),
    (
        "Returning",
        "The arm moves back to home.",
        "Der Arm fährt zurück in die Ausgangslage.",
        "O braço volta à posição inicial.",
    ),
    (
        "Fault",
        "The arm has stopped after an error, until an operator resets it.",
        "Der Arm steht nach einem Fehler, bis ein Bediener ihn zurücksetzt.",
        "O braço parou após um erro, até um operador reiniciá-lo.",
    ),
)

# From state, to state, trigger, guard.
_TRANSITIONS = (
    (0, 1, "StartCommand", "a job is loaded and no error is pending"),
    (1, 2, "PoseReached", "the pick pose is reached within the tolerance"),
    (2, 3, "GripConfirmed", "the gripper detects the part"),
    (3, 4, "PoseReached", "the place pose is reached within the tolerance"),
    (4, 5, "ReleaseConfirmed", "the gripper no longer detects the part"),
    (5, 0, "HomeReached", "the home pose is reached"),
    (1, 6, "CollisionDetected", "a joint torque is above its limit"),
    (2, 6, "GripFailed", "the gripper detects no part after the dwell time"),
    (3, 6, "ObjectDropped", "the gripper loses the part while moving"),
    (6, 0, "ResetCommand", "an operator has acknowledged the error"),
)


def cycle_behavior() -> model.Submodel:
    """Builds the submodel of the cycle: parameters, states and events.

    Returns:
        A submodel with a state machine, its parameters, the messaging
        configuration and four events. The events observe elements of other
        submodels, which `arm_links.link_all` sets.
    """
    parameters = collection(
        "CycleParameters",
        [
            prop("CycleTimeTarget", float, 2.0),
            prop("MaximumAcceleration", float, 3000.0),
            prop("ApproachHeight", float, 50.0),
            prop("RetractHeight", float, 100.0),
            prop("GripDwellTime", float, 150.0),
            span("SpeedOverrideRange", float, 5.0, 100.0),
        ],
    )
    states = listing(
        "CycleStates",
        model.SubmodelElementCollection,
        [
            collection(
                None,
                [
                    prop("StateName", str, name, coded=True),
                    mlp("StateDescription", en, de, pt),
                ],
                "CycleState",
            )
            for name, en, de, pt in _STATES
        ],
        "CycleState",
    )
    transitions = listing(
        "StateTransitions",
        model.SubmodelElementCollection,
        [
            collection(
                None,
                [
                    link("From", None, "TransitionFrom"),  # pyright: ignore[reportArgumentType]
                    link("To", None, "TransitionTo"),  # pyright: ignore[reportArgumentType]
                    prop("Trigger", str, trigger, "TransitionTrigger"),
                    prop("Guard", str, guard, "TransitionGuard"),
                ],
                "StateTransition",
            )
            for _, _, trigger, guard in _TRANSITIONS
        ],
        "StateTransition",
    )
    messaging = collection(
        "MessagingConfiguration",
        [
            prop(
                "BrokerUri",
                datatypes.AnyURI,
                "mqtt://broker.example.com:1883",
            ),
            prop("MessageQos", int, 1),
        ],
    )

    def event(
        id_short: str,
        concept_name: str,
        direction: model.Direction,
        state: model.StateOfEvent,
        topic: str,
        updated: datetime.datetime | None,
    ) -> model.BasicEventElement:
        placeholder = model.ModelReference(
            (model.Key(model.KeyTypes.SUBMODEL, "urn:placeholder"),),
            model.Submodel,
        )
        return model.BasicEventElement(
            id_short,
            placeholder,
            direction,
            state,
            message_topic=f"{TOPIC}/{topic}",
            last_update=updated,
            min_interval=relativedelta(seconds=1),
            **meaning(concept_name),
        )

    events = [
        event(
            "CycleCompleted",
            "CycleCompletedEvent",
            model.Direction.OUTPUT,
            model.StateOfEvent.ON,
            "cycle-completed",
            moment(2026, 11, 6, 8, 59, 40),
        ),
        event(
            "ObjectDropped",
            "ObjectDroppedEvent",
            model.Direction.OUTPUT,
            model.StateOfEvent.ON,
            "object-dropped",
            moment(2026, 10, 12, 16, 3, 51),
        ),
        event(
            "ErrorRaised",
            "ErrorRaisedEvent",
            model.Direction.OUTPUT,
            model.StateOfEvent.ON,
            "error-raised",
            moment(2026, 10, 30, 14, 22, 5),
        ),
        event(
            "JobRequested",
            "JobRequestedEvent",
            model.Direction.INPUT,
            model.StateOfEvent.OFF,
            "job-requested",
            None,
        ),
    ]
    elements: list[model.SubmodelElement] = [
        parameters,
        states,
        transitions,
        messaging,
        *events,
    ]
    submodel = own_submodel(
        "CycleBehavior", "CycleBehavior", elements, "BehaviorSubmodel"
    )
    _link_transitions(submodel)
    return submodel


def _link_transitions(submodel: model.Submodel) -> None:

    states = list(find(submodel, "CycleStates").value)  # pyright: ignore[reportAttributeAccessIssue]
    transitions = list(find(submodel, "StateTransitions").value)  # pyright: ignore[reportAttributeAccessIssue]
    for item, (start, end, _, _) in zip(transitions, _TRANSITIONS, strict=True):
        item.get_referable("From").value = reference_to(states[start])
        item.get_referable("To").value = reference_to(states[end])


_POSES = (
    ("Home", HOME, 100.0, "NONE"),
    ("PickApproach", (420.0, -250.0, 120.0, 180.0, 0.0, 90.0), 60.0, "NONE"),
    ("Pick", PICK, 25.0, "CLOSE"),
    ("PickRetreat", (420.0, -250.0, 120.0, 180.0, 0.0, 90.0), 60.0, "NONE"),
    ("PlaceApproach", (-300.0, 380.0, 140.0, 180.0, 0.0, 0.0), 60.0, "NONE"),
    ("Place", PLACE, 25.0, "OPEN"),
    ("PlaceRetreat", (-300.0, 380.0, 140.0, 180.0, 0.0, 0.0), 60.0, "NONE"),
)


def pick_and_place_job() -> model.Submodel:
    """Builds a job: the part, the quantity, seven poses and the operations.

    Returns:
        A submodel. The steps point at the operations of the capabilities
        submodel, which `arm_links.link_all` sets.
    """
    poses = listing(
        "Poses",
        model.SubmodelElementCollection,
        [
            collection(
                None,
                [
                    prop("PoseName", str, name),
                    pose("Pose", "Pose", values),
                    prop("Speed", float, speed, "SpeedOverride"),
                    prop("GripperAction", str, action, coded=True),
                ],
                "JobPose",
            )
            for name, values, speed, action in _POSES
        ],
        "JobPose",
        "JobPoses",
    )
    sequence = listing(
        "Sequence",
        model.ReferenceElement,
        [
            link(None, None, "JobStep")  # pyright: ignore[reportArgumentType]
            for _ in range(5)
        ],
        "JobStep",
        "JobSequence",
    )
    elements: list[model.SubmodelElement] = [
        prop("JobId", str, "JOB-2026-0007"),
        prop("JobPriority", int, 2),
        mlp(
            "JobPartType",
            "Aluminium cube, 40 mm",
            "Aluminiumwürfel, 40 mm",
            "Cubo de alumínio, 40 mm",
        ),
        prop("JobQuantity", int, 120),
        prop("JobScheduledStart", datetime.datetime, moment(2026, 11, 6, 10)),
        poses,
        sequence,
    ]
    return own_submodel(
        "PickAndPlaceJob", "PickAndPlaceJob", elements, "JobSubmodel"
    )


def station() -> model.Submodel:
    """Builds the description of the station in which the arm works.

    Returns:
        A submodel with the workspace of the arm, references to the pick and
        place poses, and two entities, the conveyor and the table. The
        references are set by `arm_links.link_all`.
    """
    workspace = collection(
        "ArmWorkspace",
        [
            span("WorkspaceX", float, -900.0, 900.0),
            span("WorkspaceY", float, -900.0, 900.0),
            span("WorkspaceZ", float, -300.0, 1100.0),
        ],
    )
    references: list[model.SubmodelElement] = [
        link("Robot", None, "RobotReference"),  # pyright: ignore[reportArgumentType]
        link("PickLocation", None, "PickLocationReference"),  # pyright: ignore[reportArgumentType]
        link("PlaceLocation", None, "PlaceLocationReference"),  # pyright: ignore[reportArgumentType]
        link(
            "SafetyScanner",
            external(f"{NAMESPACE}/asset/safety-scanner/SS-0007"),
            "SafetyScannerReference",
        ),
    ]
    conveyor = model.Entity(
        "InfeedConveyor",
        model.EntityType.SELF_MANAGED_ENTITY,
        [prop("ConveyorSpeed", float, 120.0)],
        global_asset_id=f"{NAMESPACE}/asset/conveyor/CV-0012",
        **meaning("InfeedConveyor"),
    )
    table = model.Entity(
        "WorkTable",
        model.EntityType.CO_MANAGED_ENTITY,
        [prop("TableHeight", float, 800.0)],
        **meaning("WorkTable"),
    )
    serves = model.RelationshipElement(
        "ArmServesConveyor", None, None, **meaning("ArmServesConveyor")
    )
    feeds = model.AnnotatedRelationshipElement(
        "ConveyorFeedsPickPose",
        None,
        None,
        annotation=[prop("TransferDistance", float, 150.0)],
        **meaning("ConveyorFeedsPickPose"),
    )
    elements: list[model.SubmodelElement] = [
        prop("StationId", str, "ST-04"),
        mlp(
            "StationName",
            "Parts transfer station 4",
            "Teileübergabestation 4",
            "Estação de transferência de peças 4",
        ),
        mlp(
            "StationLocation",
            "Hall 2, line 4",
            "Halle 2, Linie 4",
            "Galpão 2, linha 4",
        ),
        workspace,
        *references,
        conveyor,
        table,
        serves,
        feeds,
    ]
    return own_submodel(
        "PickAndPlaceStation",
        "PickAndPlaceStation",
        elements,
        "StationSubmodel",
    )
