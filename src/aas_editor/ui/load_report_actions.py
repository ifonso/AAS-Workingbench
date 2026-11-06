"""The action that shows what was left out of a package when it opened.

The dialog opens by itself when a package is opened in failsafe mode. This
action brings it back later, from the context menu of the package tree, for
any item of a package that has a report.
"""

from aas_editor.domain.load_report import LoadReport
from aas_editor.ui.actions import ActionContext
from aas_editor.ui.actions import ActionSpec
from aas_editor.ui.actions import default_registry
from aas_editor.ui.actions import register_action
from aas_editor.ui.actions import ViewKind
from aas_editor.ui.load_report_dialog import show_load_report

ACTION_ID = "package.load_report"


def report_of(package: object | None) -> LoadReport:
    """Returns what the SDK left out of a package, or an empty report."""
    report = getattr(package, "loadReport", None)
    return report if isinstance(report, LoadReport) else LoadReport()


def _has_report(context: ActionContext) -> bool:
    return bool(report_of(context.package))


def _show(context: ActionContext) -> None:
    package = context.package
    name = str(getattr(package, "name", "The package"))
    show_load_report(name, report_of(package), context.view)


def register_load_report_actions() -> None:
    """Adds the action to the registry, once.

    Call it before the first view is created, from the composition root.
    """
    registered = {
        spec.action_id for spec in default_registry().specs_for(ViewKind.ANY)
    }
    if ACTION_ID in registered:
        return
    register_action(
        ActionSpec(
            ACTION_ID,
            "Show what was left out when opened...",
            _show,
            _has_report,
            mutates=False,
            views=ViewKind.PACKAGES,
            status_tip=(
                "List the content that the SDK left out when it read this "
                "package"
            ),
        )
    )
