"""The validation service outlives its Qt object when the application closes.

A hints bar tells the service that it is gone from its `destroyed` signal, and
the package reports changes to the service without Qt. When the application
closes, Qt may have destroyed the service and its timer by then.
"""

from types import SimpleNamespace

from basyx.aas import model
from basyx.aas.adapter.aasx import DictSupplementaryFileContainer
from PyQt6 import sip

from aas_editor.application.changes import Change
from aas_editor.application.changes import observer_for
from aas_editor.ui.validation_service import ValidationService


class _Package:
    def save_source(self) -> SimpleNamespace:
        return SimpleNamespace(
            objects=model.DictObjectStore(),
            files=DictSupplementaryFileContainer(),
        )


def test_a_view_can_stop_listening_after_qt_destroyed_the_service(
    qapp: object,
) -> None:
    package = _Package()
    service = ValidationService(package)
    view = object()
    service.listen(view)
    sip.delete(service)

    service.stop_listening(view)

    assert not service.is_listened_to


def test_a_change_after_qt_destroyed_the_service_is_ignored(
    qapp: object,
) -> None:
    package = _Package()
    service = ValidationService(package)
    service.listen(object())
    sip.delete(service)

    observer_for(package).notify(Change.changed(package))

    assert service.is_stale
