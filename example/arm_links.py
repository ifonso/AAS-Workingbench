"""Sets the references between the submodels of the example.

A model reference lists the keys from a submodel down to an element, so its
target has to be in its submodel first. The submodels are therefore built with
empty references, and this module fills them in once all of them exist.
"""

from typing import Any

from basyx.aas import model

from arm_helpers import AAS_ID
from arm_helpers import extension
from arm_helpers import find
from arm_helpers import reference_to
from arm_helpers import reference_to_shell
from arm_skills import STEPS

# The operation that carries out each capability.
OPERATION_OF = {
    "PickObject": "Pick",
    "PlaceObject": "Place",
    "MoveToPose": "MoveTo",
}
# The operations of the job, in order, one for each step of the sequence.
SEQUENCE = ("MoveTo", "Pick", "MoveTo", "Place", "MoveTo")


def _first(element: Any) -> Any:
    return element


def link_all(parts: dict[str, model.Submodel]) -> None:
    """Fills in every reference that points across submodels.

    Args:
        parts: The submodels by their idShort.
    """
    capabilities = parts["Capabilities"]
    behavior = parts["CycleBehavior"]
    job = parts["PickAndPlaceJob"]
    station = parts["PickAndPlaceStation"]
    operational = parts["OperationalData"]
    series = parts["TimeSeries"]

    # Capabilities: which operation carries out which capability.
    pick_and_place = find(capabilities, "PickAndPlace")
    for capability, operation in OPERATION_OF.items():
        relation: Any = find(capabilities, f"ImplementedBy_{capability}")
        relation.first = reference_to(find(capabilities, capability))
        relation.second = reference_to(find(capabilities, operation))
    for order, capability in enumerate(STEPS, start=1):
        relation = find(capabilities, f"Step{order}")
        relation.first = reference_to(pick_and_place)
        relation.second = reference_to(find(capabilities, capability))

    # The operation Place raises the event that a cycle is completed.
    cycle_completed = find(behavior, "CycleCompleted")
    place: Any = find(capabilities, "Place")
    place.extension.add(
        extension("RaisesEvent", None, None, [reference_to(cycle_completed)])
    )

    # Behavior: what each event is about, and where it is published.
    observed = {
        "CycleCompleted": find(operational, "CycleCount"),
        "ObjectDropped": find(operational, "GripperStatus", "ObjectInGripper"),
        "ErrorRaised": find(operational, "LastError"),
        "JobRequested": job,
    }
    broker = reference_to(find(behavior, "MessagingConfiguration"))
    for name, target in observed.items():
        event: Any = find(behavior, name)
        event.observed = reference_to(target)
        event.message_broker = broker

    # Job: the operations of the sequence.
    steps: Any = find(job, "Sequence")
    for step, operation in zip(steps.value, SEQUENCE, strict=True):
        step.value = reference_to(find(capabilities, operation))

    # Station: the arm, the poses, and the conveyor.
    poses = list(find(job, "Poses").value)  # pyright: ignore[reportAttributeAccessIssue]
    pose_names = [item.get_referable("PoseName").value for item in poses]  # pyright: ignore[reportAttributeAccessIssue]
    shell = reference_to_shell(AAS_ID)
    find(station, "Robot").value = shell  # pyright: ignore[reportAttributeAccessIssue]
    find(station, "PickLocation").value = reference_to(  # pyright: ignore[reportAttributeAccessIssue]
        poses[pose_names.index("Pick")]
    )
    find(station, "PlaceLocation").value = reference_to(  # pyright: ignore[reportAttributeAccessIssue]
        poses[pose_names.index("Place")]
    )
    conveyor = find(station, "InfeedConveyor")
    serves: Any = find(station, "ArmServesConveyor")
    serves.first = shell
    serves.second = reference_to(conveyor)
    feeds: Any = find(station, "ConveyorFeedsPickPose")
    feeds.first = reference_to(conveyor)
    feeds.second = reference_to(poses[pose_names.index("Pick")])

    # Operational data: the current state and the history.
    states = list(find(behavior, "CycleStates").value)  # pyright: ignore[reportAttributeAccessIssue]
    find(operational, "CurrentStateReference").value = reference_to(states[0])  # pyright: ignore[reportAttributeAccessIssue]
    find(operational, "TemperatureHistory").value = reference_to(  # pyright: ignore[reportAttributeAccessIssue]
        find(series, "Segments", "InternalSegment")
    )
