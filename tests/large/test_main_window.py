#  Copyright (C) 2021  Igor Garmaev, garmaev@gmx.net
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/

import sys
from pathlib import Path
from typing import Any
from unittest import TestCase

import pytest

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

from PyQt6.QtCore import QEventLoop
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from aas_workingbench.settings.app_settings import OBJECT_ROLE

NAME_ROLE = None

AASX_FILE = Path(__file__).parents[1] / "data" / "TestPackage.aasx"

# How long a walk through the rows may take before it counts as stuck.
WATCHDOG_MS = 300_000
WATCHDOG_EXIT_CODE = 2
FAILED_STEP_EXIT_CODE = 3


# The session QApplication outlives every test. When each test created and
# dropped its own, Qt deleted objects that the widgets share between windows.
@pytest.mark.usefixtures("qapp")
class TestUi(TestCase):
    def setUp(self) -> None:
        self.app = QApplication.instance() or QApplication(sys.argv)

        # Imported here because aas_workingbench.dialogs reads the primary screen at
        # import time, which fails until a QApplication exists.
        global NAME_ROLE
        from aas_workingbench.editorApp import EditorApp
        from aas_workingbench.settings.app_settings import NAME_ROLE

        self.window = EditorApp(fileToOpen=str(AASX_FILE))
        self.window.show()

        self.packTreeView = self.window.mainTreeView
        self.packTreeView.expandAll()
        self.tab1 = self.window.mainTabWidget.widget(0)
        self.attrsTreeView = self.tab1.attrsTreeView

        self.itemsGenerator = self.packTreeView.model().iterItems()
        self.attrsGenerator = None

        self.timer = QTimer()
        self.timer.setInterval(0)
        # The walk runs in a loop of its own. Ending the loop of the
        # application emits `aboutToQuit`, which shuts QtWebEngine down, and
        # the next test that ended it crashed the process in that signal.
        self.loop = QEventLoop()

    def tearDown(self) -> None:
        self.timer.stop()
        self.window.close()

    def testViews(self):
        self._startTest(self._testViews)

    def _testViews(self):
        try:
            try:
                self._nextItemInRightTree()
            except (StopIteration, TypeError):
                self._nextItemInLeftTree()
        except StopIteration:
            self.loop.exit(0)
            print("Test is completed")

    def testLinks(self):
        self._startTest(self._testLinks)

    def _testLinks(self):
        currIndex = self.attrsTreeView.currentIndex()
        print(currIndex.data(NAME_ROLE))
        self.assertTrue(self.window.mainTabWidget.count() <= 2)
        try:
            try:
                if self.window.mainTabWidget.currentIndex() == 1:
                    # Tab of link item is opened, and the tree follows it.
                    # Two items can have the same name, such as a submodel and
                    # the concept description of its semanticId, so the
                    # objects are compared and not the names.
                    current = self.packTreeView.currentIndex()
                    linkTab: Any = self.window.mainTabWidget.widget(1)
                    self.assertTrue(current.isValid())
                    self.assertIs(
                        current.data(OBJECT_ROLE),
                        linkTab.packItem.data(OBJECT_ROLE),
                    )
                    self.assertIsNot(current.data(OBJECT_ROLE), self.linkSource)
                    self.window.mainTabWidget.removeTab(1)
                    return
                elif self.attrsTreeView.openInNewTabAct.isEnabled():
                    self.linkSource = self.packTreeView.currentIndex().data(
                        OBJECT_ROLE
                    )
                    # Open link item in new tab
                    self.attrsTreeView.openInNewTabAct.trigger()
                    self._nextItemInRightTree()
                    return
                else:
                    self._nextItemInRightTree()
                    return
            except StopIteration as e:
                print(e)
                self._nextItemInLeftTree()
        except StopIteration:
            self.loop.exit(0)
            print("Test is completed")

    def testEditCreate(self):
        self._startTest(self._testEditCreate)

    def _testEditCreate(self):
        currIndex = self.attrsTreeView.currentIndex()
        print(currIndex.data(NAME_ROLE))
        try:
            try:
                if self.attrsTreeView.editCreateInDialogAct.isEnabled():
                    # Edit current item if possible
                    # The stubbed dialog returns at once. Closing the active
                    # window here would close the main window and end the run.
                    self.attrsTreeView.editCreateInDialogAct.trigger()
                    self._nextItemInRightTree()
                    return
                else:
                    self._nextItemInRightTree()
                    return
            except StopIteration as e:
                print(e)
                self._nextItemInLeftTree()
        except StopIteration:
            self.loop.exit(0)
            print("Test is completed")

    def _startTest(self, testFunc):
        failures: list[BaseException] = []

        def step():
            # A step that fails would fail again on every tick of the timer,
            # and pytest-qt keeps each exception with its traceback: the
            # memory grew by hundreds of megabytes a second until the machine
            # had none left. The first failure ends the walk instead.
            try:
                testFunc()
            except BaseException as error:
                failures.append(error)
                self.timer.stop()
                self.loop.exit(FAILED_STEP_EXIT_CODE)

        self.timer.timeout.connect(step)
        self.timer.start()
        # A walk that never ends fails when the watchdog fires. The slowest of
        # the three runs takes about a minute.
        watchdog = QTimer()
        watchdog.setSingleShot(True)
        watchdog.timeout.connect(lambda: self.loop.exit(WATCHDOG_EXIT_CODE))
        watchdog.start(WATCHDOG_MS)
        try:
            exitCode = self.loop.exec()
        finally:
            # A timer that keeps firing would run the test step again later,
            # against a window that is already closed.
            self.timer.stop()
            watchdog.stop()
        if failures:
            raise failures[0]
        self.assertEqual(exitCode, 0)

    def _nextItemInLeftTree(self):
        pack_index = next(self.itemsGenerator)
        print(pack_index.data(NAME_ROLE))
        self.packTreeView.setCurrentIndex(pack_index)
        self.attrsGenerator = self.attrsTreeView.model().iterItems()

    def _nextItemInRightTree(self):
        if not self.attrsGenerator:
            raise StopIteration("Generator is empty")
        attrIndex = next(self.attrsGenerator)
        self.attrsTreeView.setCurrentIndex(attrIndex)
