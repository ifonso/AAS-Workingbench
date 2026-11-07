"""Constants of the application that users see."""


def test_metamodel_version_is_3_1_when_shown_in_the_window_title(
    qapp: object,
) -> None:
    from aas_workingbench.settings.app_settings import AAS_METAMODEL_VERSION
    from aas_workingbench.settings.app_settings import WINDOW_TITLE

    assert AAS_METAMODEL_VERSION == "3.1"
    assert WINDOW_TITLE.endswith("(Metamodel V3.1)")
