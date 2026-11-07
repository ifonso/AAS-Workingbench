"""The concept descriptions of the example, as one table.

Every custom semantic id of the package points at one row of this table. A row
becomes a concept description with an IEC 61360 record: the preferred name and
the definition in English, German and Portuguese, the data type, the unit, and
a value list where the property takes one of a few coded values.

The data and the texts are fictional, like the rest of the example.
"""

from dataclasses import dataclass

from basyx.aas import model

NAMESPACE = "https://example.com/ids"
IEC_61360_TEMPLATE = (
    "https://admin-shell.io/DataSpecificationTemplates/"
    "DataSpecificationIEC61360/3/1"
)
Type = model.DataTypeIEC61360


@dataclass(frozen=True)
class Concept:
    """One concept description of the example.

    Attributes:
        name: The idShort of the description, and the last part of its id.
        names: The preferred name in English, German and Portuguese.
        definitions: The definition in the same three languages.
        data_type: The IEC 61360 data type, or None for a structure.
        unit: The unit of a measure, such as `mm`.
        values: The coded values of a value list, if the concept has one.
    """

    name: str
    names: tuple[str, str, str]
    definitions: tuple[str, str, str]
    data_type: model.DataTypeIEC61360 | None = None
    unit: str | None = None
    values: tuple[str, ...] = ()

    @property
    def id(self) -> str:
        """The id of the concept description, which is also the semantic id."""
        return f"{NAMESPACE}/concept/{self.name}"


def _c(
    name: str,
    data_type: model.DataTypeIEC61360 | None,
    names: tuple[str, str, str],
    definitions: tuple[str, str, str],
    unit: str | None = None,
    values: tuple[str, ...] = (),
) -> tuple[str, Concept]:
    return name, Concept(name, names, definitions, data_type, unit, values)


def _structure(
    name: str, names: tuple[str, str, str], definitions: tuple[str, str, str]
) -> tuple[str, Concept]:
    return _c(name, None, names, definitions)


def _measure(
    name: str,
    unit: str,
    names: tuple[str, str, str],
    definitions: tuple[str, str, str],
) -> tuple[str, Concept]:
    return _c(name, Type.REAL_MEASURE, names, definitions, unit)


def _text(
    name: str,
    names: tuple[str, str, str],
    definitions: tuple[str, str, str],
    values: tuple[str, ...] = (),
) -> tuple[str, Concept]:
    return _c(name, Type.STRING, names, definitions, None, values)


def _translatable(
    name: str, names: tuple[str, str, str], definitions: tuple[str, str, str]
) -> tuple[str, Concept]:
    return _c(name, Type.STRING_TRANSLATABLE, names, definitions)


def _count(
    name: str, names: tuple[str, str, str], definitions: tuple[str, str, str]
) -> tuple[str, Concept]:
    return _c(name, Type.INTEGER_COUNT, names, definitions)


def _flag(
    name: str, names: tuple[str, str, str], definitions: tuple[str, str, str]
) -> tuple[str, Concept]:
    return _c(name, Type.BOOLEAN, names, definitions)


def _moment(
    name: str, names: tuple[str, str, str], definitions: tuple[str, str, str]
) -> tuple[str, Concept]:
    return _c(name, Type.TIMESTAMP, names, definitions)


CONCEPTS: dict[str, Concept] = dict(
    [
        # ---- Technical data: performance
        _count(
            "NumberOfAxes",
            ("Number of axes", "Anzahl der Achsen", "Número de eixos"),
            (
                "Number of controlled rotary axes of the arm, without the gripper.",
                "Anzahl der geregelten Drehachsen des Arms, ohne Greifer.",
                "Número de eixos rotativos controlados do braço, sem a garra.",
            ),
        ),
        _measure(
            "RatedPayload",
            "kg",
            ("Rated payload", "Nennlast", "Carga nominal"),
            (
                "Largest mass that the arm carries at the tool flange, tool included.",
                "Größte Masse, die der Arm am Werkzeugflansch trägt, Werkzeug eingeschlossen.",
                "Maior massa que o braço carrega no flange da ferramenta, incluindo a ferramenta.",
            ),
        ),
        _measure(
            "MaximumReach",
            "mm",
            ("Maximum reach", "Maximale Reichweite", "Alcance máximo"),
            (
                "Largest distance from the axis of the first joint to the center of the tool flange.",
                "Größter Abstand von der Achse des ersten Gelenks zur Mitte des Werkzeugflanschs.",
                "Maior distância entre o eixo da primeira junta e o centro do flange da ferramenta.",
            ),
        ),
        _measure(
            "PoseRepeatability",
            "mm",
            (
                "Pose repeatability",
                "Wiederholgenauigkeit der Pose",
                "Repetibilidade da pose",
            ),
            (
                "Largest deviation of the tool center point when the same pose is approached again and again.",
                "Größte Abweichung des Werkzeugmittelpunkts beim wiederholten Anfahren derselben Pose.",
                "Maior desvio do ponto central da ferramenta ao alcançar a mesma pose repetidas vezes.",
            ),
        ),
        _measure(
            "MaximumTcpSpeed",
            "m/s",
            (
                "Maximum tool center point speed",
                "Maximale Geschwindigkeit des Werkzeugmittelpunkts",
                "Velocidade máxima do ponto central da ferramenta",
            ),
            (
                "Largest speed of the tool center point along a path.",
                "Größte Geschwindigkeit des Werkzeugmittelpunkts entlang einer Bahn.",
                "Maior velocidade do ponto central da ferramenta ao longo de uma trajetória.",
            ),
        ),
        _measure(
            "ArmMass",
            "kg",
            ("Mass of the arm", "Masse des Arms", "Massa do braço"),
            (
                "Mass of the arm with its inner cable harness, without the controller and the gripper.",
                "Masse des Arms mit innerem Kabelbaum, ohne Steuerung und Greifer.",
                "Massa do braço com seu chicote interno, sem o controlador e a garra.",
            ),
        ),
        _measure(
            "PickAndPlaceCycleRate",
            "cycles/min",
            (
                "Pick and place cycle rate",
                "Takt beim Pick-and-Place",
                "Taxa de ciclos de pegar e colocar",
            ),
            (
                "Number of pick and place cycles per minute with a 0.5 kg part over 25 mm up, 300 mm across and 25 mm down.",
                "Anzahl der Pick-and-Place-Zyklen pro Minute mit einem 0,5-kg-Teil über 25 mm hoch, 300 mm quer und 25 mm runter.",
                "Número de ciclos de pegar e colocar por minuto com uma peça de 0,5 kg, 25 mm para cima, 300 mm na horizontal e 25 mm para baixo.",
            ),
        ),
        # ---- Technical data: axes
        _count(
            "AxisNumber",
            ("Axis number", "Achsnummer", "Número do eixo"),
            (
                "Position of the axis in the kinematic chain, counted from the base.",
                "Position der Achse in der kinematischen Kette, von der Basis aus gezählt.",
                "Posição do eixo na cadeia cinemática, contada a partir da base.",
            ),
        ),
        _translatable(
            "AxisName",
            ("Axis name", "Achsbezeichnung", "Nome do eixo"),
            (
                "Name of the axis, such as base or elbow.",
                "Bezeichnung der Achse, etwa Basis oder Ellbogen.",
                "Nome do eixo, como base ou cotovelo.",
            ),
        ),
        _structure(
            "AxisList",
            ("Axes", "Achsen", "Eixos"),
            (
                "The joints of the arm, in order from the base.",
                "Die Gelenke des Arms, in Reihenfolge von der Basis.",
                "As juntas do braço, em ordem a partir da base.",
            ),
        ),
        _structure(
            "AxisDescription",
            ("Axis", "Achse", "Eixo"),
            (
                "One joint with its number, name, range of motion and speed.",
                "Ein Gelenk mit Nummer, Name, Bewegungsbereich und Geschwindigkeit.",
                "Uma junta com seu número, nome, faixa de movimento e velocidade.",
            ),
        ),
        _measure(
            "RangeOfMotion",
            "°",
            ("Range of motion", "Bewegungsbereich", "Faixa de movimento"),
            (
                "Smallest and largest angle that the joint reaches, from its zero position.",
                "Kleinster und größter Winkel, den das Gelenk erreicht, von der Nullstellung aus.",
                "Menor e maior ângulo que a junta alcança, a partir da posição zero.",
            ),
        ),
        _measure(
            "MaximumAxisSpeed",
            "°/s",
            (
                "Maximum axis speed",
                "Maximale Achsgeschwindigkeit",
                "Velocidade máxima do eixo",
            ),
            (
                "Largest angular speed of the joint.",
                "Größte Winkelgeschwindigkeit des Gelenks.",
                "Maior velocidade angular da junta.",
            ),
        ),
        # ---- Technical data: electrical
        _measure(
            "SupplyVoltage",
            "V",
            ("Supply voltage", "Versorgungsspannung", "Tensão de alimentação"),
            (
                "Range of the AC voltage at the input of the controller.",
                "Bereich der Wechselspannung am Eingang der Steuerung.",
                "Faixa da tensão alternada na entrada do controlador.",
            ),
        ),
        _measure(
            "SupplyFrequency",
            "Hz",
            (
                "Supply frequency",
                "Versorgungsfrequenz",
                "Frequência de alimentação",
            ),
            (
                "Range of the mains frequency at the input of the controller.",
                "Bereich der Netzfrequenz am Eingang der Steuerung.",
                "Faixa da frequência da rede na entrada do controlador.",
            ),
        ),
        _measure(
            "NominalPowerConsumption",
            "W",
            (
                "Nominal power consumption",
                "Nennleistungsaufnahme",
                "Consumo nominal de potência",
            ),
            (
                "Mean electrical power of arm and controller in the reference pick and place cycle.",
                "Mittlere elektrische Leistung von Arm und Steuerung im Referenz-Pick-and-Place-Zyklus.",
                "Potência elétrica média do braço e do controlador no ciclo de referência de pegar e colocar.",
            ),
        ),
        _measure(
            "MaximumPowerConsumption",
            "W",
            (
                "Maximum power consumption",
                "Maximale Leistungsaufnahme",
                "Consumo máximo de potência",
            ),
            (
                "Peak electrical power of arm and controller.",
                "Spitzenwert der elektrischen Leistung von Arm und Steuerung.",
                "Pico de potência elétrica do braço e do controlador.",
            ),
        ),
        _measure(
            "DcBusVoltage",
            "V",
            (
                "DC bus voltage of the arm",
                "Zwischenkreisspannung des Arms",
                "Tensão do barramento CC do braço",
            ),
            (
                "Voltage that the controller supplies to the joint drives.",
                "Spannung, mit der die Steuerung die Gelenkantriebe versorgt.",
                "Tensão que o controlador fornece aos acionamentos das juntas.",
            ),
        ),
        # ---- Technical data: environment
        _text(
            "ArmProtectionClass",
            (
                "Ingress protection of the arm",
                "Schutzart des Arms",
                "Grau de proteção do braço",
            ),
            (
                "IP code of the arm according to IEC 60529.",
                "IP-Schutzart des Arms nach IEC 60529.",
                "Código IP do braço conforme a IEC 60529.",
            ),
        ),
        _text(
            "ControllerProtectionClass",
            (
                "Ingress protection of the controller",
                "Schutzart der Steuerung",
                "Grau de proteção do controlador",
            ),
            (
                "IP code of the controller according to IEC 60529.",
                "IP-Schutzart der Steuerung nach IEC 60529.",
                "Código IP do controlador conforme a IEC 60529.",
            ),
        ),
        _measure(
            "OperatingTemperature",
            "°C",
            (
                "Ambient temperature in operation",
                "Umgebungstemperatur im Betrieb",
                "Temperatura ambiente em operação",
            ),
            (
                "Range of the air temperature around the arm in which it may work.",
                "Bereich der Lufttemperatur um den Arm, in dem er arbeiten darf.",
                "Faixa da temperatura do ar ao redor do braço em que ele pode trabalhar.",
            ),
        ),
        _measure(
            "StorageTemperature",
            "°C",
            (
                "Ambient temperature in storage",
                "Umgebungstemperatur bei Lagerung",
                "Temperatura ambiente no armazenamento",
            ),
            (
                "Range of the air temperature in which the arm may be stored.",
                "Bereich der Lufttemperatur, in dem der Arm gelagert werden darf.",
                "Faixa da temperatura do ar em que o braço pode ser armazenado.",
            ),
        ),
        _measure(
            "RelativeHumidity",
            "%",
            (
                "Relative humidity",
                "Relative Luftfeuchte",
                "Umidade relativa",
            ),
            (
                "Range of the relative air humidity in operation, without condensation.",
                "Bereich der relativen Luftfeuchte im Betrieb, ohne Kondensation.",
                "Faixa da umidade relativa do ar em operação, sem condensação.",
            ),
        ),
        _measure(
            "NoiseLevel",
            "dB(A)",
            ("Noise level", "Geräuschpegel", "Nível de ruído"),
            (
                "A-weighted sound pressure level at one meter in the reference cycle.",
                "A-bewerteter Schalldruckpegel in einem Meter Abstand im Referenzzyklus.",
                "Nível de pressão sonora ponderado em A a um metro no ciclo de referência.",
            ),
        ),
        # ---- Technical data: mounting and gripper
        _translatable(
            "MountingOrientation",
            (
                "Mounting orientation",
                "Einbaulage",
                "Orientação de montagem",
            ),
            (
                "Positions in which the base may be mounted.",
                "Lagen, in denen die Basis montiert werden darf.",
                "Posições em que a base pode ser montada.",
            ),
        ),
        _text(
            "BaseBoltPattern",
            (
                "Bolt pattern of the base",
                "Schraubenbild der Basis",
                "Padrão de parafusos da base",
            ),
            (
                "Number, thread and layout of the bolts that hold the base.",
                "Anzahl, Gewinde und Anordnung der Schrauben, die die Basis halten.",
                "Número, rosca e disposição dos parafusos que fixam a base.",
            ),
        ),
        _text(
            "ToolFlangeStandard",
            (
                "Tool flange standard",
                "Norm des Werkzeugflanschs",
                "Norma do flange da ferramenta",
            ),
            (
                "Standard that the tool flange follows.",
                "Norm, der der Werkzeugflansch folgt.",
                "Norma que o flange da ferramenta segue.",
            ),
        ),
        _translatable(
            "GripperType",
            ("Gripper type", "Greifertyp", "Tipo de garra"),
            (
                "Kind of gripper that the arm carries.",
                "Art des Greifers, den der Arm trägt.",
                "Tipo de garra que o braço carrega.",
            ),
        ),
        _measure(
            "GripStroke",
            "mm",
            ("Grip stroke", "Greifhub", "Curso de preensão"),
            (
                "Total travel of the two fingers, from open to closed.",
                "Gesamtweg der beiden Finger, von offen bis geschlossen.",
                "Curso total dos dois dedos, de aberto a fechado.",
            ),
        ),
        _measure(
            "GripForceRange",
            "N",
            (
                "Grip force range",
                "Greifkraftbereich",
                "Faixa de força de preensão",
            ),
            (
                "Smallest and largest force that the fingers can apply.",
                "Kleinste und größte Kraft, die die Finger aufbringen können.",
                "Menor e maior força que os dedos podem aplicar.",
            ),
        ),
        _measure(
            "MaximumVacuumLevel",
            "kPa",
            (
                "Maximum vacuum level",
                "Maximaler Unterdruck",
                "Nível máximo de vácuo",
            ),
            (
                "Largest negative pressure that the vacuum option reaches, below ambient pressure.",
                "Größter Unterdruck, den die Vakuumoption unter dem Umgebungsdruck erreicht.",
                "Maior pressão negativa que a opção de vácuo alcança, abaixo da pressão ambiente.",
            ),
        ),
        # ---- Bill of material
        _text(
            "PartArticleNumber",
            (
                "Part article number",
                "Artikelnummer des Bauteils",
                "Número do artigo da peça",
            ),
            (
                "Article number of a part in the catalog of the manufacturer.",
                "Artikelnummer eines Bauteils im Katalog des Herstellers.",
                "Número do artigo de uma peça no catálogo do fabricante.",
            ),
        ),
        _measure(
            "PartMass",
            "kg",
            ("Part mass", "Masse des Bauteils", "Massa da peça"),
            (
                "Mass of one part.",
                "Masse eines Bauteils.",
                "Massa de uma peça.",
            ),
        ),
        # ---- Qualifier types and extension names
        _measure(
            "MaxExecutionTime",
            "s",
            (
                "Maximum execution time",
                "Maximale Ausführungsdauer",
                "Tempo máximo de execução",
            ),
            (
                "Qualifier: the longest time that an operation may run before the controller aborts it.",
                "Qualifier: die längste Zeit, die eine Operation laufen darf, bevor die Steuerung sie abbricht.",
                "Qualifier: o maior tempo que uma operação pode rodar antes de o controlador abortá-la.",
            ),
        ),
        _text(
            "UpdateInterval",
            (
                "Update interval",
                "Aktualisierungsintervall",
                "Intervalo de atualização",
            ),
            (
                "Qualifier: how often the controller writes a new value, as an ISO 8601 duration.",
                "Qualifier: wie oft die Steuerung einen neuen Wert schreibt, als ISO-8601-Dauer.",
                "Qualifier: com que frequência o controlador grava um novo valor, como duração ISO 8601.",
            ),
        ),
        _flag(
            "OptionalPart",
            ("Optional part", "Optionales Bauteil", "Peça opcional"),
            (
                "Qualifier: true when the part is an option that an arm may be delivered without.",
                "Qualifier: wahr, wenn das Bauteil eine Option ist, ohne die ein Arm geliefert werden kann.",
                "Qualifier: verdadeiro quando a peça é um opcional sem o qual o braço pode ser entregue.",
            ),
        ),
        _flag(
            "SafetyRelevant",
            (
                "Safety relevant",
                "Sicherheitsrelevant",
                "Relevante para a segurança",
            ),
            (
                "Extension: true when running the operation can hurt a person or damage equipment.",
                "Extension: wahr, wenn das Ausführen der Operation Personen verletzen oder Anlagen beschädigen kann.",
                "Extension: verdadeiro quando executar a operação pode ferir uma pessoa ou danificar equipamentos.",
            ),
        ),
        _structure(
            "RaisesEvent",
            ("Raises event", "Löst Ereignis aus", "Dispara evento"),
            (
                "Extension: the event element that the operation raises when it ends.",
                "Extension: das Ereigniselement, das die Operation am Ende auslöst.",
                "Extension: o elemento de evento que a operação dispara ao terminar.",
            ),
        ),
        _flag(
            "FictionalExample",
            (
                "Fictional example",
                "Fiktives Beispiel",
                "Exemplo fictício",
            ),
            (
                "Extension: true when the data is made up for an example and describes no real product.",
                "Extension: wahr, wenn die Daten für ein Beispiel erfunden sind und kein reales Produkt beschreiben.",
                "Extension: verdadeiro quando os dados são inventados para um exemplo e não descrevem um produto real.",
            ),
        ),
        # ---- Submodels
        _structure(
            "CapabilitiesSubmodel",
            (
                "Pick and place capabilities",
                "Fähigkeiten zum Pick-and-Place",
                "Capacidades de pegar e colocar",
            ),
            (
                "What the arm can do, the operations that do it, and how they relate.",
                "Was der Arm kann, die Operationen, die es ausführen, und wie sie zusammenhängen.",
                "O que o braço pode fazer, as operações que o fazem e como elas se relacionam.",
            ),
        ),
        _structure(
            "BehaviorSubmodel",
            (
                "Cycle behavior",
                "Zyklusverhalten",
                "Comportamento do ciclo",
            ),
            (
                "The states and transitions of one pick and place cycle, its parameters and its events.",
                "Die Zustände und Übergänge eines Pick-and-Place-Zyklus, seine Parameter und seine Ereignisse.",
                "Os estados e transições de um ciclo de pegar e colocar, seus parâmetros e seus eventos.",
            ),
        ),
        _structure(
            "JobSubmodel",
            (
                "Pick and place job",
                "Pick-and-Place-Auftrag",
                "Tarefa de pegar e colocar",
            ),
            (
                "A job for the arm: the part, the quantity, the poses and the sequence of operations.",
                "Ein Auftrag für den Arm: das Teil, die Menge, die Posen und die Abfolge der Operationen.",
                "Uma tarefa para o braço: a peça, a quantidade, as poses e a sequência de operações.",
            ),
        ),
        _structure(
            "StationSubmodel",
            (
                "Pick and place station",
                "Pick-and-Place-Station",
                "Estação de pegar e colocar",
            ),
            (
                "The station in which the arm works, and what surrounds it.",
                "Die Station, in der der Arm arbeitet, und was ihn umgibt.",
                "A estação em que o braço trabalha e o que o cerca.",
            ),
        ),
        _structure(
            "OperationalSubmodel",
            (
                "Operational data",
                "Betriebsdaten",
                "Dados operacionais",
            ),
            (
                "Values that the controller keeps up to date while the arm runs.",
                "Werte, die die Steuerung aktuell hält, während der Arm läuft.",
                "Valores que o controlador mantém atualizados enquanto o braço funciona.",
            ),
        ),
        _structure(
            "DocumentationSubmodel",
            (
                "Documentation",
                "Dokumentation",
                "Documentação",
            ),
            (
                "Texts, pictures and files that explain the arm.",
                "Texte, Bilder und Dateien, die den Arm erklären.",
                "Textos, imagens e arquivos que explicam o braço.",
            ),
        ),
        # ---- Capabilities
        _structure(
            "PickAndPlaceCapability",
            (
                "Pick and place",
                "Pick-and-Place",
                "Pegar e colocar",
            ),
            (
                "Capability to take a part at one pose and set it down at another.",
                "Fähigkeit, ein Teil an einer Pose aufzunehmen und an einer anderen abzulegen.",
                "Capacidade de pegar uma peça em uma pose e depositá-la em outra.",
            ),
        ),
        _structure(
            "PickCapability",
            ("Pick", "Aufnehmen", "Pegar"),
            (
                "Capability to take a part with the gripper.",
                "Fähigkeit, ein Teil mit dem Greifer aufzunehmen.",
                "Capacidade de pegar uma peça com a garra.",
            ),
        ),
        _structure(
            "PlaceCapability",
            ("Place", "Ablegen", "Colocar"),
            (
                "Capability to set a held part down at a pose.",
                "Fähigkeit, ein gehaltenes Teil an einer Pose abzulegen.",
                "Capacidade de depositar uma peça segurada em uma pose.",
            ),
        ),
        _structure(
            "MoveCapability",
            ("Move to pose", "Pose anfahren", "Mover para a pose"),
            (
                "Capability to bring the tool center point to a pose.",
                "Fähigkeit, den Werkzeugmittelpunkt in eine Pose zu bringen.",
                "Capacidade de levar o ponto central da ferramenta a uma pose.",
            ),
        ),
        _structure(
            "CapabilityConstraints",
            (
                "Capability constraints",
                "Einschränkungen der Fähigkeit",
                "Restrições da capacidade",
            ),
            (
                "Limits on the parts that the arm can pick and place.",
                "Grenzen für die Teile, die der Arm aufnehmen und ablegen kann.",
                "Limites para as peças que o braço pode pegar e colocar.",
            ),
        ),
        _measure(
            "PartMassRange",
            "kg",
            (
                "Part mass range",
                "Massebereich der Teile",
                "Faixa de massa das peças",
            ),
            (
                "Smallest and largest mass of a part, the gripper included in the payload.",
                "Kleinste und größte Masse eines Teils, der Greifer ist in der Nutzlast enthalten.",
                "Menor e maior massa de uma peça, com a garra incluída na carga.",
            ),
        ),
        _measure(
            "PartSizeRange",
            "mm",
            (
                "Part size range",
                "Größenbereich der Teile",
                "Faixa de tamanho das peças",
            ),
            (
                "Smallest and largest width of a part between the fingers.",
                "Kleinste und größte Breite eines Teils zwischen den Fingern.",
                "Menor e maior largura de uma peça entre os dedos.",
            ),
        ),
        _structure(
            "GripMethods",
            ("Grip methods", "Greifverfahren", "Métodos de preensão"),
            (
                "The ways in which the gripper can hold a part.",
                "Die Arten, auf die der Greifer ein Teil halten kann.",
                "As maneiras como a garra pode segurar uma peça.",
            ),
        ),
        _text(
            "GripMethod",
            ("Grip method", "Greifverfahren", "Método de preensão"),
            (
                "How the gripper holds a part.",
                "Wie der Greifer ein Teil hält.",
                "Como a garra segura uma peça.",
            ),
            ("PARALLEL_FINGERS", "VACUUM"),
        ),
        _structure(
            "PickOperation",
            ("Pick operation", "Operation Aufnehmen", "Operação pegar"),
            (
                "Operation that moves to a pose, grips a part and lifts it.",
                "Operation, die eine Pose anfährt, ein Teil greift und es anhebt.",
                "Operação que vai a uma pose, segura uma peça e a levanta.",
            ),
        ),
        _structure(
            "PlaceOperation",
            ("Place operation", "Operation Ablegen", "Operação colocar"),
            (
                "Operation that moves to a pose, sets the part down and releases it.",
                "Operation, die eine Pose anfährt, das Teil absetzt und loslässt.",
                "Operação que vai a uma pose, deposita a peça e a solta.",
            ),
        ),
        _structure(
            "MoveToOperation",
            ("Move-to operation", "Operation Anfahren", "Operação mover para"),
            (
                "Operation that moves the tool center point to a pose without touching a part.",
                "Operation, die den Werkzeugmittelpunkt zu einer Pose bewegt, ohne ein Teil zu berühren.",
                "Operação que move o ponto central da ferramenta a uma pose sem tocar em uma peça.",
            ),
        ),
        _structure(
            "Pose",
            ("Pose", "Pose", "Pose"),
            (
                "Position in millimeters and orientation in degrees of the tool center point in the base frame of the arm.",
                "Position in Millimetern und Orientierung in Grad des Werkzeugmittelpunkts im Basiskoordinatensystem des Arms.",
                "Posição em milímetros e orientação em graus do ponto central da ferramenta no referencial da base do braço.",
            ),
        ),
        _measure(
            "PoseX",
            "mm",
            ("X position", "X-Position", "Posição X"),
            (
                "Position along the x axis of the base frame.",
                "Position entlang der x-Achse des Basiskoordinatensystems.",
                "Posição ao longo do eixo x do referencial da base.",
            ),
        ),
        _measure(
            "PoseY",
            "mm",
            ("Y position", "Y-Position", "Posição Y"),
            (
                "Position along the y axis of the base frame.",
                "Position entlang der y-Achse des Basiskoordinatensystems.",
                "Posição ao longo do eixo y do referencial da base.",
            ),
        ),
        _measure(
            "PoseZ",
            "mm",
            ("Z position", "Z-Position", "Posição Z"),
            (
                "Position along the z axis of the base frame.",
                "Position entlang der z-Achse des Basiskoordinatensystems.",
                "Posição ao longo do eixo z do referencial da base.",
            ),
        ),
        _measure(
            "PoseRoll",
            "°",
            ("Roll", "Rollwinkel", "Rolagem"),
            (
                "Rotation about the x axis.",
                "Drehung um die x-Achse.",
                "Rotação em torno do eixo x.",
            ),
        ),
        _measure(
            "PosePitch",
            "°",
            ("Pitch", "Nickwinkel", "Arfagem"),
            (
                "Rotation about the y axis.",
                "Drehung um die y-Achse.",
                "Rotação em torno do eixo y.",
            ),
        ),
        _measure(
            "PoseYaw",
            "°",
            ("Yaw", "Gierwinkel", "Guinada"),
            (
                "Rotation about the z axis.",
                "Drehung um die z-Achse.",
                "Rotação em torno do eixo z.",
            ),
        ),
        _measure(
            "SpeedOverride",
            "%",
            ("Speed", "Geschwindigkeit", "Velocidade"),
            (
                "Speed as a percentage of the maximum speed of the arm.",
                "Geschwindigkeit in Prozent der Höchstgeschwindigkeit des Arms.",
                "Velocidade como porcentagem da velocidade máxima do braço.",
            ),
        ),
        _measure(
            "GripForce",
            "N",
            ("Grip force", "Greifkraft", "Força de preensão"),
            (
                "Force that the fingers apply to the part.",
                "Kraft, mit der die Finger das Teil greifen.",
                "Força que os dedos aplicam à peça.",
            ),
        ),
        _measure(
            "ApproachHeight",
            "mm",
            ("Approach height", "Anfahrhöhe", "Altura de aproximação"),
            (
                "Height above the pose from which the tool moves straight down.",
                "Höhe über der Pose, von der aus das Werkzeug senkrecht nach unten fährt.",
                "Altura acima da pose a partir da qual a ferramenta desce na vertical.",
            ),
        ),
        _text(
            "OperationResult",
            ("Result", "Ergebnis", "Resultado"),
            (
                "How an operation ended.",
                "Wie eine Operation geendet hat.",
                "Como uma operação terminou.",
            ),
            ("OK", "OBJECT_NOT_FOUND", "GRIP_FAILED", "COLLISION", "TIMEOUT"),
        ),
        _measure(
            "MeasuredGripWidth",
            "mm",
            (
                "Measured grip width",
                "Gemessene Greifweite",
                "Largura de preensão medida",
            ),
            (
                "Distance between the fingers when the part is held.",
                "Abstand zwischen den Fingern, wenn das Teil gehalten wird.",
                "Distância entre os dedos quando a peça está segura.",
            ),
        ),
        _measure(
            "TravelTime",
            "s",
            ("Travel time", "Fahrzeit", "Tempo de deslocamento"),
            (
                "Time from the start of the motion to the arrival at the pose.",
                "Zeit vom Beginn der Bewegung bis zur Ankunft an der Pose.",
                "Tempo desde o início do movimento até a chegada à pose.",
            ),
        ),
        _text(
            "MotionType",
            ("Motion type", "Bewegungsart", "Tipo de movimento"),
            (
                "Whether the joints move together or the tool moves on a straight line.",
                "Ob sich die Gelenke gemeinsam bewegen oder das Werkzeug auf einer Geraden fährt.",
                "Se as juntas se movem juntas ou a ferramenta se move em linha reta.",
            ),
            ("JOINT", "LINEAR"),
        ),
        _structure(
            "ToolCenterPoint",
            (
                "Tool center point",
                "Werkzeugmittelpunkt",
                "Ponto central da ferramenta",
            ),
            (
                "The pose of the point that the program moves, at the end of the tool.",
                "Die Pose des Punktes, den das Programm bewegt, am Ende des Werkzeugs.",
                "A pose do ponto que o programa move, na ponta da ferramenta.",
            ),
        ),
        _structure(
            "CapabilityImplementedBy",
            ("Implemented by", "Umgesetzt durch", "Implementada por"),
            (
                "Relationship from an operation to the capability that it carries out.",
                "Beziehung von einer Operation zu der Fähigkeit, die sie ausführt.",
                "Relação de uma operação com a capacidade que ela executa.",
            ),
        ),
        _structure(
            "CapabilityComposedOf",
            ("Composed of", "Zusammengesetzt aus", "Composta de"),
            (
                "Relationship from a capability to a capability that is one of its steps.",
                "Beziehung von einer Fähigkeit zu einer Fähigkeit, die einer ihrer Schritte ist.",
                "Relação de uma capacidade com uma capacidade que é um de seus passos.",
            ),
        ),
        _count(
            "CompositionOrder",
            ("Order of the step", "Reihenfolge des Schritts", "Ordem do passo"),
            (
                "Position of the step in the composition, starting at one.",
                "Position des Schritts in der Zusammensetzung, beginnend bei eins.",
                "Posição do passo na composição, começando em um.",
            ),
        ),
        # ---- Behavior
        _structure(
            "CycleParameters",
            ("Cycle parameters", "Zyklusparameter", "Parâmetros do ciclo"),
            (
                "Settings that shape one pick and place cycle.",
                "Einstellungen, die einen Pick-and-Place-Zyklus prägen.",
                "Ajustes que moldam um ciclo de pegar e colocar.",
            ),
        ),
        _measure(
            "CycleTimeTarget",
            "s",
            ("Target cycle time", "Ziel-Zykluszeit", "Tempo de ciclo alvo"),
            (
                "Time that one cycle should take.",
                "Zeit, die ein Zyklus dauern soll.",
                "Tempo que um ciclo deve levar.",
            ),
        ),
        _measure(
            "MaximumAcceleration",
            "mm/s²",
            (
                "Maximum acceleration",
                "Maximale Beschleunigung",
                "Aceleração máxima",
            ),
            (
                "Largest acceleration of the tool center point along a path.",
                "Größte Beschleunigung des Werkzeugmittelpunkts entlang einer Bahn.",
                "Maior aceleração do ponto central da ferramenta ao longo de uma trajetória.",
            ),
        ),
        _measure(
            "RetractHeight",
            "mm",
            ("Retract height", "Abhebehöhe", "Altura de recuo"),
            (
                "Height to which the tool lifts the part after the grip.",
                "Höhe, auf die das Werkzeug das Teil nach dem Greifen anhebt.",
                "Altura até a qual a ferramenta levanta a peça após a preensão.",
            ),
        ),
        _measure(
            "GripDwellTime",
            "ms",
            (
                "Grip dwell time",
                "Haltezeit beim Greifen",
                "Tempo de espera na preensão",
            ),
            (
                "Time to wait after the fingers close and before the lift.",
                "Zeit, die nach dem Schließen der Finger vor dem Anheben gewartet wird.",
                "Tempo de espera após o fechamento dos dedos e antes da elevação.",
            ),
        ),
        _measure(
            "SpeedOverrideRange",
            "%",
            (
                "Speed override range",
                "Bereich der Geschwindigkeitsvorgabe",
                "Faixa de ajuste de velocidade",
            ),
            (
                "Smallest and largest speed that an operator may set.",
                "Kleinste und größte Geschwindigkeit, die ein Bediener einstellen darf.",
                "Menor e maior velocidade que um operador pode ajustar.",
            ),
        ),
        _structure(
            "CycleStates",
            ("Cycle states", "Zyklus-Zustände", "Estados do ciclo"),
            (
                "The states that a cycle goes through.",
                "Die Zustände, die ein Zyklus durchläuft.",
                "Os estados pelos quais um ciclo passa.",
            ),
        ),
        _structure(
            "CycleState",
            ("Cycle state", "Zyklus-Zustand", "Estado do ciclo"),
            (
                "One state of the cycle, with its name and meaning.",
                "Ein Zustand des Zyklus, mit seinem Namen und seiner Bedeutung.",
                "Um estado do ciclo, com seu nome e significado.",
            ),
        ),
        _text(
            "StateName",
            ("State name", "Zustandsname", "Nome do estado"),
            (
                "Name of a state of the cycle.",
                "Name eines Zustands des Zyklus.",
                "Nome de um estado do ciclo.",
            ),
            (
                "Idle",
                "MovingToPick",
                "Gripping",
                "MovingToPlace",
                "Releasing",
                "Returning",
                "Fault",
            ),
        ),
        _translatable(
            "StateDescription",
            (
                "State description",
                "Zustandsbeschreibung",
                "Descrição do estado",
            ),
            (
                "What the arm does in the state.",
                "Was der Arm im Zustand tut.",
                "O que o braço faz no estado.",
            ),
        ),
        _structure(
            "StateTransitions",
            ("State transitions", "Zustandsübergänge", "Transições de estado"),
            (
                "The transitions between the states of the cycle.",
                "Die Übergänge zwischen den Zuständen des Zyklus.",
                "As transições entre os estados do ciclo.",
            ),
        ),
        _structure(
            "StateTransition",
            ("State transition", "Zustandsübergang", "Transição de estado"),
            (
                "A change from one state to another, with its trigger and guard.",
                "Ein Wechsel von einem Zustand in einen anderen, mit Auslöser und Bedingung.",
                "Uma mudança de um estado para outro, com seu gatilho e condição.",
            ),
        ),
        _structure(
            "TransitionFrom",
            ("From state", "Von Zustand", "Do estado"),
            (
                "Reference to the state that the transition leaves.",
                "Verweis auf den Zustand, den der Übergang verlässt.",
                "Referência ao estado que a transição deixa.",
            ),
        ),
        _structure(
            "TransitionTo",
            ("To state", "Nach Zustand", "Para o estado"),
            (
                "Reference to the state that the transition enters.",
                "Verweis auf den Zustand, in den der Übergang führt.",
                "Referência ao estado em que a transição entra.",
            ),
        ),
        _text(
            "TransitionTrigger",
            ("Trigger", "Auslöser", "Gatilho"),
            (
                "Event that starts the transition.",
                "Ereignis, das den Übergang startet.",
                "Evento que inicia a transição.",
            ),
        ),
        _text(
            "TransitionGuard",
            ("Guard", "Bedingung", "Condição"),
            (
                "Condition that must hold for the transition to happen.",
                "Bedingung, die für den Übergang gelten muss.",
                "Condição que deve valer para a transição ocorrer.",
            ),
        ),
        _structure(
            "MessagingConfiguration",
            (
                "Messaging configuration",
                "Konfiguration der Nachrichten",
                "Configuração de mensagens",
            ),
            (
                "Where and how the arm publishes its events.",
                "Wo und wie der Arm seine Ereignisse veröffentlicht.",
                "Onde e como o braço publica seus eventos.",
            ),
        ),
        _c(
            "BrokerUri",
            Type.IRI,
            ("Broker address", "Adresse des Brokers", "Endereço do broker"),
            (
                "Address of the message broker that receives the events.",
                "Adresse des Message-Brokers, der die Ereignisse empfängt.",
                "Endereço do broker de mensagens que recebe os eventos.",
            ),
        ),
        _count(
            "MessageQos",
            ("Quality of service", "Dienstgüte", "Qualidade de serviço"),
            (
                "Delivery guarantee of the broker: 0 at most once, 1 at least once, 2 exactly once.",
                "Zustellgarantie des Brokers: 0 höchstens einmal, 1 mindestens einmal, 2 genau einmal.",
                "Garantia de entrega do broker: 0 no máximo uma vez, 1 pelo menos uma vez, 2 exatamente uma vez.",
            ),
        ),
        _structure(
            "CycleCompletedEvent",
            ("Cycle completed", "Zyklus abgeschlossen", "Ciclo concluído"),
            (
                "Event that the arm raises when it has placed a part and is back at home.",
                "Ereignis, das der Arm auslöst, wenn er ein Teil abgelegt hat und wieder in der Ausgangslage ist.",
                "Evento que o braço dispara quando colocou uma peça e voltou à posição inicial.",
            ),
        ),
        _structure(
            "ObjectDroppedEvent",
            ("Object dropped", "Objekt fallen gelassen", "Objeto derrubado"),
            (
                "Event that the arm raises when it loses the part while it moves.",
                "Ereignis, das der Arm auslöst, wenn er das Teil während der Bewegung verliert.",
                "Evento que o braço dispara quando perde a peça durante o movimento.",
            ),
        ),
        _structure(
            "ErrorRaisedEvent",
            ("Error raised", "Fehler aufgetreten", "Erro gerado"),
            (
                "Event that the arm raises when the last error changes.",
                "Ereignis, das der Arm auslöst, wenn sich der letzte Fehler ändert.",
                "Evento que o braço dispara quando o último erro muda.",
            ),
        ),
        _structure(
            "JobRequestedEvent",
            ("Job requested", "Auftrag angefordert", "Tarefa solicitada"),
            (
                "Event that the arm waits for: a higher system asks it to start a job.",
                "Ereignis, auf das der Arm wartet: ein übergeordnetes System fordert einen Auftrag an.",
                "Evento que o braço espera: um sistema superior pede que ele inicie uma tarefa.",
            ),
        ),
        # ---- Job
        _text(
            "JobId",
            ("Job id", "Auftragsnummer", "Identificador da tarefa"),
            (
                "Identifier of the job in the system that issued it.",
                "Kennung des Auftrags im System, das ihn erteilt hat.",
                "Identificador da tarefa no sistema que a emitiu.",
            ),
        ),
        _count(
            "JobPriority",
            ("Job priority", "Auftragspriorität", "Prioridade da tarefa"),
            (
                "Priority of the job, where a smaller number runs first.",
                "Priorität des Auftrags, wobei eine kleinere Zahl zuerst läuft.",
                "Prioridade da tarefa, em que um número menor roda primeiro.",
            ),
        ),
        _translatable(
            "JobPartType",
            ("Part to move", "Zu bewegendes Teil", "Peça a mover"),
            (
                "Description of the part that the job moves.",
                "Beschreibung des Teils, das der Auftrag bewegt.",
                "Descrição da peça que a tarefa move.",
            ),
        ),
        _count(
            "JobQuantity",
            ("Quantity", "Menge", "Quantidade"),
            (
                "Number of parts that the job moves.",
                "Anzahl der Teile, die der Auftrag bewegt.",
                "Número de peças que a tarefa move.",
            ),
        ),
        _moment(
            "JobScheduledStart",
            ("Scheduled start", "Geplanter Start", "Início programado"),
            (
                "Time at which the job should start, in UTC.",
                "Zeitpunkt, zu dem der Auftrag starten soll, in UTC.",
                "Momento em que a tarefa deve começar, em UTC.",
            ),
        ),
        _structure(
            "JobPoses",
            ("Job poses", "Posen des Auftrags", "Poses da tarefa"),
            (
                "The poses that the job visits, in order.",
                "Die Posen, die der Auftrag anfährt, in Reihenfolge.",
                "As poses que a tarefa visita, em ordem.",
            ),
        ),
        _structure(
            "JobPose",
            ("Job pose", "Pose des Auftrags", "Pose da tarefa"),
            (
                "A named pose with the speed and the gripper action at it.",
                "Eine benannte Pose mit der Geschwindigkeit und der Greiferaktion dort.",
                "Uma pose nomeada com a velocidade e a ação da garra nela.",
            ),
        ),
        _text(
            "PoseName",
            ("Pose name", "Posenname", "Nome da pose"),
            (
                "Name of a pose in the job.",
                "Name einer Pose im Auftrag.",
                "Nome de uma pose na tarefa.",
            ),
        ),
        _text(
            "GripperAction",
            ("Gripper action", "Greiferaktion", "Ação da garra"),
            (
                "What the gripper does when the arm reaches the pose.",
                "Was der Greifer tut, wenn der Arm die Pose erreicht.",
                "O que a garra faz quando o braço chega à pose.",
            ),
            ("NONE", "CLOSE", "OPEN", "VACUUM_ON", "VACUUM_OFF"),
        ),
        _structure(
            "JobSequence",
            ("Job sequence", "Ablauf des Auftrags", "Sequência da tarefa"),
            (
                "The operations that the job runs, in order, as references.",
                "Die Operationen, die der Auftrag ausführt, in Reihenfolge, als Verweise.",
                "As operações que a tarefa executa, em ordem, como referências.",
            ),
        ),
        _structure(
            "JobStep",
            ("Job step", "Schritt des Auftrags", "Passo da tarefa"),
            (
                "Reference to the operation of one step.",
                "Verweis auf die Operation eines Schritts.",
                "Referência à operação de um passo.",
            ),
        ),
        # ---- Station
        _text(
            "StationId",
            ("Station id", "Stationskennung", "Identificador da estação"),
            (
                "Identifier of the station in the plant.",
                "Kennung der Station in der Anlage.",
                "Identificador da estação na planta.",
            ),
        ),
        _translatable(
            "StationName",
            ("Station name", "Stationsname", "Nome da estação"),
            (
                "Name of the station.",
                "Name der Station.",
                "Nome da estação.",
            ),
        ),
        _translatable(
            "StationLocation",
            ("Station location", "Standort der Station", "Local da estação"),
            (
                "Where the station is in the plant.",
                "Wo die Station in der Anlage steht.",
                "Onde a estação fica na planta.",
            ),
        ),
        _structure(
            "ArmWorkspace",
            (
                "Workspace of the arm",
                "Arbeitsraum des Arms",
                "Espaço de trabalho do braço",
            ),
            (
                "The box, in the base frame, that contains the reachable poses used in the station.",
                "Der Quader im Basiskoordinatensystem, der die in der Station genutzten erreichbaren Posen enthält.",
                "A caixa, no referencial da base, que contém as poses alcançáveis usadas na estação.",
            ),
        ),
        _measure(
            "WorkspaceX",
            "mm",
            (
                "Workspace along x",
                "Arbeitsraum entlang x",
                "Espaço de trabalho em x",
            ),
            (
                "Smallest and largest x of the workspace.",
                "Kleinstes und größtes x des Arbeitsraums.",
                "Menor e maior x do espaço de trabalho.",
            ),
        ),
        _measure(
            "WorkspaceY",
            "mm",
            (
                "Workspace along y",
                "Arbeitsraum entlang y",
                "Espaço de trabalho em y",
            ),
            (
                "Smallest and largest y of the workspace.",
                "Kleinstes und größtes y des Arbeitsraums.",
                "Menor e maior y do espaço de trabalho.",
            ),
        ),
        _measure(
            "WorkspaceZ",
            "mm",
            (
                "Workspace along z",
                "Arbeitsraum entlang z",
                "Espaço de trabalho em z",
            ),
            (
                "Smallest and largest z of the workspace.",
                "Kleinstes und größtes z des Arbeitsraums.",
                "Menor e maior z do espaço de trabalho.",
            ),
        ),
        _structure(
            "RobotReference",
            ("Robot", "Roboter", "Robô"),
            (
                "Reference to the shell of the arm that works in the station.",
                "Verweis auf die Verwaltungsschale des Arms, der in der Station arbeitet.",
                "Referência à casca de administração do braço que trabalha na estação.",
            ),
        ),
        _structure(
            "PickLocationReference",
            ("Pick location", "Aufnahmeort", "Local de coleta"),
            (
                "Reference to the pose in the job where parts are picked.",
                "Verweis auf die Pose im Auftrag, an der Teile aufgenommen werden.",
                "Referência à pose na tarefa em que as peças são pegas.",
            ),
        ),
        _structure(
            "PlaceLocationReference",
            ("Place location", "Ablageort", "Local de colocação"),
            (
                "Reference to the pose in the job where parts are set down.",
                "Verweis auf die Pose im Auftrag, an der Teile abgelegt werden.",
                "Referência à pose na tarefa em que as peças são depositadas.",
            ),
        ),
        _structure(
            "SafetyScannerReference",
            (
                "Safety scanner",
                "Sicherheitslaserscanner",
                "Scanner de segurança",
            ),
            (
                "Reference to the asset of the scanner that watches the station.",
                "Verweis auf das Asset des Scanners, der die Station überwacht.",
                "Referência ao ativo do scanner que vigia a estação.",
            ),
        ),
        _structure(
            "InfeedConveyor",
            ("Infeed conveyor", "Zuführband", "Esteira de alimentação"),
            (
                "The conveyor that brings parts to the pick pose.",
                "Das Förderband, das Teile zur Aufnahmepose bringt.",
                "A esteira que traz peças até a pose de coleta.",
            ),
        ),
        _structure(
            "WorkTable",
            ("Work table", "Arbeitstisch", "Mesa de trabalho"),
            (
                "The table that carries the arm and receives the parts.",
                "Der Tisch, der den Arm trägt und die Teile aufnimmt.",
                "A mesa que sustenta o braço e recebe as peças.",
            ),
        ),
        _measure(
            "ConveyorSpeed",
            "mm/s",
            ("Conveyor speed", "Bandgeschwindigkeit", "Velocidade da esteira"),
            (
                "Speed of the belt of the conveyor.",
                "Geschwindigkeit des Gurts des Förderbands.",
                "Velocidade da correia da esteira.",
            ),
        ),
        _measure(
            "TableHeight",
            "mm",
            ("Table height", "Tischhöhe", "Altura da mesa"),
            (
                "Height of the table top above the floor.",
                "Höhe der Tischplatte über dem Boden.",
                "Altura do tampo da mesa acima do piso.",
            ),
        ),
        _structure(
            "ArmServesConveyor",
            (
                "Arm serves conveyor",
                "Arm bedient Förderband",
                "Braço atende esteira",
            ),
            (
                "Relationship from the arm to the conveyor whose parts it picks.",
                "Beziehung vom Arm zum Förderband, dessen Teile er aufnimmt.",
                "Relação do braço com a esteira cujas peças ele pega.",
            ),
        ),
        _structure(
            "ConveyorFeedsPickPose",
            (
                "Conveyor feeds pick pose",
                "Förderband versorgt Aufnahmepose",
                "Esteira alimenta a pose de coleta",
            ),
            (
                "Relationship from the conveyor to the pose where its parts are picked.",
                "Beziehung vom Förderband zur Pose, an der seine Teile aufgenommen werden.",
                "Relação da esteira com a pose em que suas peças são pegas.",
            ),
        ),
        _measure(
            "TransferDistance",
            "mm",
            (
                "Transfer distance",
                "Übergabeabstand",
                "Distância de transferência",
            ),
            (
                "Distance from the end of the belt to the pick pose.",
                "Abstand vom Ende des Gurts zur Aufnahmepose.",
                "Distância do fim da correia até a pose de coleta.",
            ),
        ),
        # ---- Operational data
        _text(
            "CurrentState",
            ("Current state", "Aktueller Zustand", "Estado atual"),
            (
                "State of the cycle now, by name.",
                "Zustand des Zyklus jetzt, nach Namen.",
                "Estado do ciclo agora, pelo nome.",
            ),
            (
                "Idle",
                "MovingToPick",
                "Gripping",
                "MovingToPlace",
                "Releasing",
                "Returning",
                "Fault",
            ),
        ),
        _structure(
            "CurrentStateReference",
            (
                "Current state element",
                "Element des aktuellen Zustands",
                "Elemento do estado atual",
            ),
            (
                "Reference to the state in the cycle behavior that is current now.",
                "Verweis auf den Zustand im Zyklusverhalten, der jetzt aktuell ist.",
                "Referência ao estado do comportamento do ciclo que está ativo agora.",
            ),
        ),
        _text(
            "OperatingMode",
            ("Operating mode", "Betriebsart", "Modo de operação"),
            (
                "Mode in which the controller runs the arm: automatic, manual at reduced speed or manual at high speed.",
                "Betriebsart, in der die Steuerung den Arm fährt: automatisch, manuell mit reduzierter Geschwindigkeit oder manuell mit hoher Geschwindigkeit.",
                "Modo em que o controlador opera o braço: automático, manual em velocidade reduzida ou manual em alta velocidade.",
            ),
            ("AUTOMATIC", "MANUAL_REDUCED", "MANUAL_HIGH"),
        ),
        _count(
            "CycleCount",
            ("Cycle count", "Zyklenzähler", "Contador de ciclos"),
            (
                "Number of pick and place cycles since the arm was commissioned.",
                "Anzahl der Pick-and-Place-Zyklen seit der Inbetriebnahme des Arms.",
                "Número de ciclos de pegar e colocar desde o comissionamento do braço.",
            ),
        ),
        _measure(
            "OperatingHours",
            "h",
            ("Operating hours", "Betriebsstunden", "Horas de operação"),
            (
                "Hours with the drives powered since commissioning.",
                "Stunden mit eingeschalteten Antrieben seit der Inbetriebnahme.",
                "Horas com os acionamentos energizados desde o comissionamento.",
            ),
        ),
        _structure(
            "JointStates",
            ("Joint states", "Gelenkzustände", "Estados das juntas"),
            (
                "The live values of the six joints.",
                "Die Echtzeitwerte der sechs Gelenke.",
                "Os valores em tempo real das seis juntas.",
            ),
        ),
        _structure(
            "JointState",
            ("Joint state", "Gelenkzustand", "Estado da junta"),
            (
                "Position, temperature and current of one joint.",
                "Position, Temperatur und Strom eines Gelenks.",
                "Posição, temperatura e corrente de uma junta.",
            ),
        ),
        _measure(
            "ActualJointPosition",
            "°",
            (
                "Actual joint position",
                "Istposition des Gelenks",
                "Posição real da junta",
            ),
            (
                "Angle of the joint now.",
                "Winkel des Gelenks jetzt.",
                "Ângulo da junta agora.",
            ),
        ),
        _measure(
            "JointTemperature",
            "°C",
            ("Joint temperature", "Gelenktemperatur", "Temperatura da junta"),
            (
                "Temperature of the motor housing of the joint.",
                "Temperatur des Motorgehäuses des Gelenks.",
                "Temperatura da carcaça do motor da junta.",
            ),
        ),
        _measure(
            "MotorCurrent",
            "A",
            ("Motor current", "Motorstrom", "Corrente do motor"),
            (
                "Current that the drive of the joint delivers now.",
                "Strom, den der Antrieb des Gelenks jetzt liefert.",
                "Corrente que o acionamento da junta fornece agora.",
            ),
        ),
        _structure(
            "GripperStatus",
            ("Gripper status", "Greiferstatus", "Estado da garra"),
            (
                "Live values of the gripper.",
                "Echtzeitwerte des Greifers.",
                "Valores em tempo real da garra.",
            ),
        ),
        _measure(
            "GripperPosition",
            "mm",
            ("Gripper opening", "Greiferöffnung", "Abertura da garra"),
            (
                "Distance between the fingers now.",
                "Abstand zwischen den Fingern jetzt.",
                "Distância entre os dedos agora.",
            ),
        ),
        _flag(
            "ObjectInGripper",
            ("Object in gripper", "Objekt im Greifer", "Objeto na garra"),
            (
                "True when the sensors of the gripper detect a held part.",
                "Wahr, wenn die Sensoren des Greifers ein gehaltenes Teil erkennen.",
                "Verdadeiro quando os sensores da garra detectam uma peça segura.",
            ),
        ),
        _measure(
            "VacuumLevel",
            "kPa",
            ("Vacuum level", "Unterdruck", "Nível de vácuo"),
            (
                "Negative pressure at the suction cup now.",
                "Unterdruck am Sauger jetzt.",
                "Pressão negativa na ventosa agora.",
            ),
        ),
        _measure(
            "ActualGripForce",
            "N",
            ("Actual grip force", "Ist-Greifkraft", "Força de preensão real"),
            (
                "Force that the fingers apply now.",
                "Kraft, die die Finger jetzt aufbringen.",
                "Força que os dedos aplicam agora.",
            ),
        ),
        _structure(
            "LastError",
            ("Last error", "Letzter Fehler", "Último erro"),
            (
                "The most recent error that the controller reported.",
                "Der jüngste Fehler, den die Steuerung gemeldet hat.",
                "O erro mais recente que o controlador informou.",
            ),
        ),
        _text(
            "ErrorCode",
            ("Error code", "Fehlercode", "Código de erro"),
            (
                "Code of the error in the error list of the controller.",
                "Code des Fehlers in der Fehlerliste der Steuerung.",
                "Código do erro na lista de erros do controlador.",
            ),
        ),
        _translatable(
            "ErrorMessage",
            ("Error message", "Fehlertext", "Mensagem de erro"),
            (
                "Text that explains the error to an operator.",
                "Text, der dem Bediener den Fehler erklärt.",
                "Texto que explica o erro ao operador.",
            ),
        ),
        _text(
            "ErrorSeverity",
            ("Error severity", "Schwere des Fehlers", "Gravidade do erro"),
            (
                "How serious the error is.",
                "Wie schwer der Fehler ist.",
                "Qual a gravidade do erro.",
            ),
            ("INFO", "WARNING", "ERROR", "FATAL"),
        ),
        _moment(
            "ErrorTimestamp",
            ("Error time", "Zeitpunkt des Fehlers", "Momento do erro"),
            (
                "Time at which the error occurred, in UTC.",
                "Zeitpunkt, zu dem der Fehler auftrat, in UTC.",
                "Momento em que o erro ocorreu, em UTC.",
            ),
        ),
        _flag(
            "ErrorAcknowledged",
            ("Error acknowledged", "Fehler quittiert", "Erro reconhecido"),
            (
                "True when an operator has acknowledged the error.",
                "Wahr, wenn ein Bediener den Fehler quittiert hat.",
                "Verdadeiro quando um operador reconheceu o erro.",
            ),
        ),
        _structure(
            "TemperatureHistory",
            (
                "Temperature history",
                "Temperaturverlauf",
                "Histórico de temperatura",
            ),
            (
                "Reference to the time series segment that holds recent joint temperatures.",
                "Verweis auf das Zeitreihensegment mit den jüngsten Gelenktemperaturen.",
                "Referência ao segmento de série temporal com as temperaturas recentes das juntas.",
            ),
        ),
        _measure(
            "ObservedTemperatureRange",
            "°C",
            (
                "Observed joint temperature range",
                "Beobachteter Gelenktemperaturbereich",
                "Faixa observada de temperatura das juntas",
            ),
            (
                "Lowest and highest joint temperature in the last hour.",
                "Niedrigste und höchste Gelenktemperatur in der letzten Stunde.",
                "Menor e maior temperatura das juntas na última hora.",
            ),
        ),
        # ---- Documentation
        _translatable(
            "ProductOverview",
            ("Product overview", "Produktübersicht", "Visão geral do produto"),
            (
                "Short text that introduces the arm.",
                "Kurzer Text, der den Arm vorstellt.",
                "Texto curto que apresenta o braço.",
            ),
        ),
        _translatable(
            "ExampleDisclaimer",
            ("Example disclaimer", "Hinweis zum Beispiel", "Aviso do exemplo"),
            (
                "Text that says the data is fictional.",
                "Text, der sagt, dass die Daten fiktiv sind.",
                "Texto que diz que os dados são fictícios.",
            ),
        ),
        _translatable(
            "SafetyNotice",
            ("Safety notice", "Sicherheitshinweis", "Aviso de segurança"),
            (
                "Text that warns about the hazards of a moving arm.",
                "Text, der vor den Gefahren eines bewegten Arms warnt.",
                "Texto que alerta sobre os perigos de um braço em movimento.",
            ),
        ),
        _structure(
            "SearchKeywords",
            ("Keywords", "Schlagwörter", "Palavras-chave"),
            (
                "Words under which the arm can be found.",
                "Wörter, unter denen der Arm zu finden ist.",
                "Palavras sob as quais o braço pode ser encontrado.",
            ),
        ),
        _translatable(
            "SearchKeyword",
            ("Keyword", "Schlagwort", "Palavra-chave"),
            (
                "One word under which the arm can be found.",
                "Ein Wort, unter dem der Arm zu finden ist.",
                "Uma palavra sob a qual o braço pode ser encontrado.",
            ),
        ),
        _c(
            "ArmPicture",
            Type.FILE,
            ("Picture of the arm", "Bild des Arms", "Imagem do braço"),
            (
                "Drawing of the arm that picks a part from a table.",
                "Zeichnung des Arms, der ein Teil von einem Tisch aufnimmt.",
                "Desenho do braço pegando uma peça de uma mesa.",
            ),
        ),
        _c(
            "DatasheetFile",
            Type.FILE,
            ("Datasheet", "Datenblatt", "Folha de dados"),
            (
                "PDF file with the main data of the arm.",
                "PDF-Datei mit den wichtigsten Daten des Arms.",
                "Arquivo PDF com os dados principais do braço.",
            ),
        ),
        _c(
            "WorkEnvelopeDrawing",
            Type.FILE,
            (
                "Work envelope drawing",
                "Zeichnung des Arbeitsraums",
                "Desenho do envelope de trabalho",
            ),
            (
                "Top view of the area that the arm reaches.",
                "Draufsicht auf den Bereich, den der Arm erreicht.",
                "Vista de topo da área que o braço alcança.",
            ),
        ),
        _c(
            "JointCalibration",
            Type.BLOB,
            (
                "Joint calibration",
                "Gelenkkalibrierung",
                "Calibração das juntas",
            ),
            (
                "JSON data with the zero offsets of the six joints, measured at the factory.",
                "JSON-Daten mit den Nullpunktabweichungen der sechs Gelenke, im Werk gemessen.",
                "Dados JSON com os desvios de zero das seis juntas, medidos na fábrica.",
            ),
        ),
        # ---- Time series variables, one for each joint
        *[
            _measure(
                f"Joint{n}Temperature",
                "°C",
                (
                    f"Temperature of joint {n}",
                    f"Temperatur von Gelenk {n}",
                    f"Temperatura da junta {n}",
                ),
                (
                    f"Temperature of the motor housing of joint {n}, as a recorded variable.",
                    f"Temperatur des Motorgehäuses von Gelenk {n}, als aufgezeichnete Variable.",
                    f"Temperatura da carcaça do motor da junta {n}, como variável registrada.",
                ),
            )
            for n in range(1, 7)
        ],
    ]
)


def concept(name: str) -> Concept:
    """Looks up a concept by name.

    Args:
        name: The idShort of the concept.

    Returns:
        The concept.

    Raises:
        KeyError: If the table has no such concept.
    """
    return CONCEPTS[name]


def semantic_id(name: str) -> model.ExternalReference:
    """Builds the semantic id that points at a concept of the table.

    Args:
        name: The idShort of the concept.

    Returns:
        An external reference with the id of the concept as its only key.
    """
    return model.ExternalReference(
        (model.Key(model.KeyTypes.GLOBAL_REFERENCE, concept(name).id),)
    )


def value_id(name: str, value: str) -> model.ExternalReference:
    """Builds the reference to one coded value of a concept's value list.

    Args:
        name: The idShort of the concept.
        value: One of the values in the concept's list.

    Returns:
        An external reference that identifies the value.

    Raises:
        KeyError: If the value is not in the list of the concept.
    """
    if value not in concept(name).values:
        raise KeyError(f"{value!r} is not in the value list of {name}")
    return model.ExternalReference(
        (
            model.Key(
                model.KeyTypes.GLOBAL_REFERENCE,
                f"{NAMESPACE}/value/{name}/{value}",
            ),
        )
    )


def _languages(texts: tuple[str, str, str]) -> dict[str, str]:
    return dict(zip(("en", "de", "pt"), texts, strict=True))


def concept_description(entry: Concept) -> model.ConceptDescription:
    """Builds the concept description of one table row.

    Args:
        entry: The row.

    Returns:
        A concept description with an IEC 61360 record.
    """
    pairs = (
        set(
            {
                model.ValueReferencePair(value, value_id(entry.name, value))
                for value in entry.values
            }
        )
        if entry.values
        else None
    )
    record = model.DataSpecificationIEC61360(
        preferred_name=model.PreferredNameTypeIEC61360(_languages(entry.names)),
        data_type=entry.data_type,
        definition=model.DefinitionTypeIEC61360(_languages(entry.definitions)),
        unit=entry.unit,
        value_list=pairs,
    )
    return model.ConceptDescription(
        entry.id,
        id_short=entry.name,
        display_name=model.MultiLanguageNameType(_languages(entry.names)),
        description=model.MultiLanguageTextType(_languages(entry.definitions)),
        administration=model.AdministrativeInformation(
            version="1", revision="0"
        ),
        embedded_data_specifications=[
            model.EmbeddedDataSpecification(
                data_specification=model.ExternalReference(
                    (
                        model.Key(
                            model.KeyTypes.GLOBAL_REFERENCE,
                            IEC_61360_TEMPLATE,
                        ),
                    )
                ),
                data_specification_content=record,
            )
        ],
    )
