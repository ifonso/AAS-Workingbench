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
from unittest import TestCase

import pytest

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

NAME_ROLE = None

AASX_FILE = Path(__file__).parents[1] / "data" / "TestPackage.aasx"

# How long a walk through the rows may take before it counts as stuck.
WATCHDOG_MS = 300_000
WATCHDOG_EXIT_CODE = 2


# The session QApplication outlives every test. When each test created and
# dropped its own, Qt deleted objects that the widgets share between windows.
@pytest.mark.usefixtures("qapp")
class TestUi(TestCase):
    def setUp(self) -> None:
        self.app = QApplication.instance() or QApplication(sys.argv)

        # Imported here because aas_editor.dialogs reads the primary screen at
        # import time, which fails until a QApplication exists.
        global NAME_ROLE
        from aas_editor.editorApp import EditorApp
        from aas_editor.settings.app_settings import NAME_ROLE

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
            self.app.exit(0)
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
                    # Tab of link item is opened
                    self.assertTrue(self.packTreeView.currentIndex().isValid())
                    self.assertNotEqual(
                        self.currIterPackIndex.data(NAME_ROLE),
                        self.packTreeView.currentIndex().data(NAME_ROLE),
                    )
                    self.window.mainTabWidget.removeTab(1)
                    return
                elif self.attrsTreeView.openInNewTabAct.isEnabled():
                    self.currIterPackIndex = self.packTreeView.currentIndex()
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
            self.app.exit(0)
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
            self.app.exit(0)
            print("Test is completed")

    def _startTest(self, testFunc):
        self.timer.timeout.connect(testFunc)
        self.timer.start()
        # An exception in a step does not end the event loop: pytest-qt records
        # it and the timer fires again, so a step that fails on every row would
        # run for ever. The watchdog ends the loop with a failure instead. The
        # slowest of the three runs takes about a minute.
        watchdog = QTimer()
        watchdog.setSingleShot(True)
        watchdog.timeout.connect(lambda: self.app.exit(WATCHDOG_EXIT_CODE))
        watchdog.start(WATCHDOG_MS)
        try:
            self.assertEqual(self.app.exec(), 0)
        finally:
            # A timer that keeps firing would run the test step again later,
            # against a window that is already closed.
            self.timer.stop()
            watchdog.stop()

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
