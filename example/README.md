# Example package: a robot arm that picks and places

`robot_arm_pick_and_place.aasx` is a complete example for AAS Workingbench: an Asset Administration Shell, in metamodel V3.1, for a six-axis arm that does pick and place.
The arm is made up: the "Workingbench Example Arm PP-6" of an invented manufacturer at `example.com`.
Every number, name, address, date and certificate in it is fictional, the pictures and the PDF files were drawn by the script, and no part describes a real product.

## What is in it

The package has one shell and 14 submodels.
Eight of them follow the IDTA templates that the editor bundles, and read their semantic ids from those files.
The other six are the example's own, and their semantic ids are the concept descriptions (IEC 61360) of the package, with names and definitions in English, German and Portuguese.

| Submodel | What it is for |
|---|---|
| `Nameplate` | Digital Nameplate 3.0.1: manufacturer, type, serial number, year, markings, address, logo. |
| `ContactInformations` | Contact Information 1.0.1: a technical and a commercial contact. |
| `TechnicalData` | Technical Data 2.0.1: performance, the six axes with ranges and speeds, supply, environment, mounting and gripper. |
| `HandoverDocumentation` | Handover Documentation 2.0.1: a datasheet and a quick start guide, classified as VDI 2770 asks. |
| `HierarchicalStructures` | Bill of Material 1.1.1: base, six joints with motor and encoder, wrist, gripper with fingers and a vacuum option, and controller, as entities with statements. |
| `Capabilities` | The capabilities Pick and Place, Pick, Place and Move, and the operations `Pick`, `Place` and `MoveTo` with input, output and in/out variables. |
| `CycleBehavior` | The states and transitions of one cycle, its parameters, the messaging configuration and the events `CycleCompleted`, `ObjectDropped`, `ErrorRaised` and `JobRequested`. |
| `PickAndPlaceJob` | A job with a list of seven poses and the sequence of operations that it runs. |
| `PickAndPlaceStation` | The station: its workspace, references to the arm and to the pick and place poses, a conveyor and a table. |
| `OperationalData` | Live values: the state, the mode, the cycle count, the joints, the gripper and the last error. |
| `TimeSeries` | Time Series Data 1.1.1: six records of the joint temperatures. |
| `SoftwareNameplate` | Software Nameplate 1.0.1: the firmware of the controller. |
| `CarbonFootprint` | Carbon Footprint 1.0.1: a made-up footprint of production. |
| `Documentation` | Texts in three languages, the picture, the datasheet, and a Blob with calibration data. |

All 14 types of submodel elements appear in it.
The Digital Nameplate template is the only bundled file that is not in metamodel V3.1, because the IDTA published it only that way.
The package also carries the concept descriptions that those templates hold for the semantic ids that it uses, so that a reader finds the meaning of an element in the package.
Of the other bundled templates the example uses none: Functional Safety would make safety claims for a made-up product, Provision of 3D Models would need a CAD file that this example cannot draw license-free, and the rest (such as Asset Interfaces Description, Reliability or the AI templates) need data that a made-up arm does not have.
There is no template for capabilities in the bundle, so the capabilities are modeled here directly.

## Open it

Start the editor and open the file from the File menu, or give it on the command line:

```sh
uv run python -m aas_workingbench example/robot_arm_pick_and_place.aasx
```

Running the editor rewrites the tracked file `src/aas_workingbench/settings/settings.ini`.
Discard that change with `git checkout -- src/aas_workingbench/settings/settings.ini`.

## Rebuild it

The script `build_robot_arm.py` writes the file with the BaSyx SDK, and draws the pictures and writes the PDF files itself:

```sh
uv run python example/build_robot_arm.py
```

The other `arm_*.py` files next to it hold the model.
The test `tests/medium/test_robot_arm_example.py` checks that the file is what the script makes, so change the script and write the file again, never the file alone.
