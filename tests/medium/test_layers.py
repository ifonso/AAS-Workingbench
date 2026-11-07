"""The layer rule: `domain` and `application` do not import PyQt.

Each check imports the modules in a clean subprocess. pytest-qt has already
loaded PyQt6 in the test process, so `sys.modules` of this process says nothing.
"""

from pathlib import Path
import subprocess
import sys

import pytest

PACKAGE_DIR = Path(__file__).parents[2] / "src" / "aas_workingbench"

# Run in the subprocess. It imports the module, and also all submodules of a
# package when asked, and reports every loaded PyQt6 module. Isolated mode (-I)
# ignores the user's environment variables and the current directory.
_CHECK = """
import importlib
import pkgutil
import sys

package = importlib.import_module(sys.argv[1])
if sys.argv[2] == "all":
    for module in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        importlib.import_module(module.name)
loaded = sorted(
    name for name in sys.modules if name == "PyQt6" or name.startswith("PyQt6.")
)
print("\\n".join(loaded))
"""


def _loaded_qt_modules(
    module: str, with_submodules: bool = False
) -> tuple[int, list[str], str]:
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            _CHECK,
            module,
            "all" if with_submodules else "self",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return result.returncode, result.stdout.split(), result.stderr


def _layer(name: str) -> object:
    # The layers are created by the work packages that first need them.
    exists = (PACKAGE_DIR / name).is_dir()
    return pytest.param(
        f"aas_workingbench.{name}",
        id=name,
        marks=pytest.mark.skipif(
            not exists, reason=f"The {name} layer does not exist yet"
        ),
    )


@pytest.mark.parametrize("package", [_layer("domain"), _layer("application")])
def test_layer_imports_no_pyqt_when_all_modules_are_imported(
    package: str,
) -> None:
    returncode, qt_modules, stderr = _loaded_qt_modules(
        package, with_submodules=True
    )

    assert returncode == 0, stderr
    assert qt_modules == []


@pytest.mark.parametrize(
    "module",
    [
        "aas_workingbench",
        "aas_workingbench.utils.util_type",
        "aas_workingbench.additional.classes",
    ],
)
def test_module_imports_no_pyqt_when_it_is_the_documented_qt_free_module(
    module: str,
) -> None:
    returncode, qt_modules, stderr = _loaded_qt_modules(module)

    assert returncode == 0, stderr
    assert qt_modules == []


def test_check_reports_pyqt_when_a_module_imports_it() -> None:
    # Guards the check itself: a package that imports Qt must be reported.
    returncode, qt_modules, stderr = _loaded_qt_modules(
        "aas_workingbench.settings"
    )

    assert returncode == 0, stderr
    assert "PyQt6.QtCore" in qt_modules
