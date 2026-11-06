#  Copyright (C) 2025  Igor Garmaev, garmaev@gmx.net
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/
import copy
from enum import unique, Enum
from inspect import isabstract
from typing import List, Dict, Union, Iterable

from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtWidgets import (
    QGroupBox,
    QFormLayout,
    QLabel,
    QWidget,
    QPushButton,
    QDialog,
)
from basyx.aas.model import (
    Entity,
    EntityType,
    LangStringSet,
    ModelReference,
    MultiLanguageProperty,
    Referable,
)

import aas_editor.widgets as widgets
import aas_editor.widgets.buttons
from aas_editor.additional.classes import DictItem
from aas_editor.widgets.widgetUtil import InputWidgetUtil
from aas_editor.settings import (
    DEFAULT_COMPLETIONS,
    DEFAULTS,
    GENERATED_DEFAULTS,
    OBJECT_ROLE,
)
from aas_editor.utils.util import (
    getReqParams4init,
    getParamsAndTypehints4init,
    getDefaultVal,
    delAASParent,
    inheritors,
)

from aas_editor.utils.util_classes import ClassesInfo, PreObject
from aas_editor.utils.util_type import (
    isOptional,
    issubtype,
    getTypeName,
    typeHintToType,
    isoftype,
    isIterable,
    isIterableType,
    getArgs,
)
from aas_editor.utils.util import isValOk4Typehint
from aas_editor.application.hints import hints_mode
from aas_editor.domain.language_tags import check_language_tags
from aas_editor.domain.validation.field_checks import (
    entity_global_asset_id_problem,
)
from aas_editor.ui.inline_hints import attach_inline_hint
from aas_editor.domain.typed_values import check_new_object
from aas_editor.widgets.editWidgets import (
    BytesEdit,
    SpecialInputWidget,
    StandardInputWidget,
    TypedValueInputWidget,
    ValueTypeInputWidget,
)
from aas_editor.widgets.messsageBoxes import ErrorMessageBox


@unique
class GroupBoxType(Enum):
    SIMPLE = 0
    CLOSABLE = 1


class GroupBox(QGroupBox):
    """Groupbox which also can be closable groupbox"""

    closeClicked = pyqtSignal()

    def __init__(
        self,
        objTypeHint,
        parent=None,
        title="",
        paramsToHide: dict = None,
        rmDefParams=True,
        objVal=None,
        paramsToAttrs=None,
        optional=False,
        **kwargs,
    ):
        super().__init__(parent)
        if title:
            self.setTitle(title)

        self.objTypeHint = objTypeHint
        self.paramsToHide = (
            paramsToHide
            if paramsToHide
            else ClassesInfo.defaultParamsToHide(objTypeHint)
        )
        self.paramsToAttrs = (
            paramsToAttrs
            if paramsToAttrs
            else ClassesInfo.paramsToAttrs(objTypeHint)
        )
        self.rmDefParams = rmDefParams
        self.objVal = objVal
        self.optional = optional

        self.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.setLayout(QFormLayout(self))
        self.type = GroupBoxType.SIMPLE
        self.toggled.connect(lambda x: self.closeClicked.emit())

    def layout(self) -> QFormLayout:
        return super().layout()

    def setClosable(self, b: bool) -> None:
        self.type = GroupBoxType.CLOSABLE if b else GroupBoxType.SIMPLE
        self.setCheckable(b)

    def isClosable(self) -> bool:
        return self.isCheckable() and self.type is GroupBoxType.CLOSABLE

    def setVal(self, val):
        pass

    def _adjustWindow(self) -> None:
        try:
            self.window().adjustSize()
        except RuntimeError:
            # The box was deleted before the event loop got to this call.
            pass

    def adjustSize(self) -> None:
        oldSize = self.size()
        super(GroupBox, self).adjustSize()
        newSize = self.size()
        if oldSize != newSize:
            QTimer.singleShot(0, self._adjustWindow)
        newSize = self.size()
        if newSize.width() < oldSize.width():
            self.resize(oldSize.width(), newSize.height())


class ObjGroupBox(GroupBox):
    def __init__(
        self,
        objTypeHint,
        parent=None,
        paramsToHide: dict = None,
        objVal=None,
        paramsToAttrs: dict = None,
        **kwargs,
    ):
        super().__init__(
            objTypeHint,
            objVal=objVal,
            parent=parent,
            paramsToHide=paramsToHide,
            paramsToAttrs=paramsToAttrs,
            **kwargs,
        )

        self.inputWidgets: List[QWidget] = []
        self.paramWidgets: Dict[str, QWidget] = {}
        # Widget of a value -> the widget it follows, to link each pair once.
        self._linkedWidgets: Dict[QWidget, QWidget] = {}

        reqInitParamsTypehints = getReqParams4init(
            self.objTypeHint,
            self.rmDefParams,
            self.paramsToHide,
            delOptional=False,
        )
        self.defaultParams = tuple(
            getParamsAndTypehints4init(self.objTypeHint)[1].keys()
        )

        sortedReqInitParamsTypehints = sorted(
            reqInitParamsTypehints.items(),
            key=lambda x: int(x[0] in self.defaultParams),
        )
        self.reqParamsDict = dict(sortedReqInitParamsTypehints)
        self.kwargs = kwargs.copy() if kwargs else {}
        self.initLayout()
        self._initNotice()

    def initLayout(self):
        if self.reqParamsDict:
            for param in self.reqParamsDict:
                self.kwargs["completions"] = DEFAULT_COMPLETIONS.get(
                    self.objTypeHint, {}
                ).get(param, [])
                val = self.getVal4param(param)
                widget = self.getInitialInputWidget(param, val, **self.kwargs)
                self.insertInputWidget(widget, param)

    def getVal4param(self, param):
        attr = self.paramsToAttrs.get(param, param)
        if hasattr(self.objVal, attr):
            val = getattr(self.objVal, attr)
        elif param in GENERATED_DEFAULTS.get(self.objTypeHint, {}):
            val = GENERATED_DEFAULTS[self.objTypeHint][param]()
        else:
            val = DEFAULTS.get(self.objTypeHint, {}).get(
                param, getDefaultVal(self.objTypeHint, param, None)
            )
        return val

    def getInitialInputWidget(self, param: str, val, **kwargs) -> QWidget:
        paramTypeHint = self.reqParamsDict[param]
        if self._startsWithLanguages(param) and val is None:
            # A new MultiLanguageProperty starts with a row for each default
            # language, not with a button that makes the text (F-EDT-04 AC2).
            kwargs["optional"] = True
            return self.getInputWidget(param, val, **kwargs)
        if isOptional(paramTypeHint):
            if val is None or (
                isinstance(val, PreObject)
                and val.existingObjUsed
                and val.existingObj is None
            ):
                return self.getCreatePushBtn(param)
        return self.getInputWidget(param, val, **kwargs)

    def _startsWithLanguages(self, param: str) -> bool:
        """Tell whether a parameter is the text of a new MultiLanguageProperty."""
        return (
            self.objVal is None
            and param == "value"
            and self.objTypeHint is MultiLanguageProperty
        )

    def getInputWidget(self, param: str, val, **kwargs) -> QWidget:
        paramTypeHint = self.reqParamsDict[param]
        if self._startsWithLanguages(param):
            from aas_editor.ui.user_defaults import default_languages

            kwargs["startLanguages"] = default_languages()
        print(f"Getting widget for param: {param} of type: {paramTypeHint}")
        # A parameter named by the caller takes a text of several lines.
        kwargs["multiline"] = param in kwargs.get("multilineParams", ())
        widget = InputWidgetUtil.getInputWidget(
            paramTypeHint, objVal=val, **kwargs
        )
        self.paramWidgets[param] = widget
        if self.objTypeHint is Entity and param in (
            "entity_type",
            "global_asset_id",
        ):
            signal = getattr(widget.widget, "currentIndexChanged", None) or (
                widget.widget.textChanged
            )
            signal.connect(self._refreshNotice)
        # Advice under the fields that the rules know, while hints mode is on
        attach_inline_hint(
            getattr(self.objTypeHint, "__name__", ""), param, widget
        )

        if widget.optional and isinstance(
            widget, (GroupBox, StandardInputWidget)
        ):
            widget.setClosable(True)
            widget.closeClicked.connect(
                self.replaceOptionalParamWidgetWithCreateBtn
            )
        return widget

    def insertInputWidget(self, widget: QWidget, param: str, row: int = -1):
        title = self.getWidgetTitle(param)
        self.layout().insertRow(row, title, widget)
        self.inputWidgets.append(widget)
        self.linkValueWidgets()
        self.adjustSize()

    def linkValueWidgets(self):
        """Make the widgets of a value follow the widgets they depend on.

        A value is checked against the value type of the same object, and the
        bytes of a Blob suggest the content type of a file that is loaded.
        Widgets that are not there yet are linked when they are created.
        """
        typeWidget = self.paramWidgets.get("value_type")
        contentTypeWidget = self.paramWidgets.get("content_type")
        # A value type that the form does not ask for, like the one a list
        # fixes for its children, is one of the hidden parameters.
        fixedType = self.paramsToHide.get("value_type")
        for widget in list(self.paramWidgets.values()):
            if isinstance(widget, TypedValueInputWidget) and isinstance(
                typeWidget, ValueTypeInputWidget
            ):
                if self._linkedWidgets.get(widget) is typeWidget:
                    continue
                typeWidget.widget.value_type_changed.connect(
                    widget.setValueType
                )
                widget.setValueType(typeWidget.widget.value_type())
                self._linkedWidgets[widget] = typeWidget
            elif isinstance(widget, TypedValueInputWidget) and fixedType:
                widget.setValueType(fixedType)
            elif (
                isinstance(widget, SpecialInputWidget)
                and isinstance(widget.widget, BytesEdit)
                and isinstance(contentTypeWidget, StandardInputWidget)
            ):
                if self._linkedWidgets.get(widget) is contentTypeWidget:
                    continue
                bytesEdit, lineEdit = widget.widget, contentTypeWidget.widget
                bytesEdit.set_content_type(lineEdit.text())
                lineEdit.textChanged.connect(bytesEdit.set_content_type)
                bytesEdit.content_type_suggested.connect(
                    lambda suggested, line=lineEdit: (
                        line.setText(suggested) if not line.text() else None
                    )
                )
                self._linkedWidgets[widget] = contentTypeWidget

    def _initNotice(self):
        """Add the line that asks a new self-managed entity for its asset id.

        It sits under the row of the global asset id, which is a button until
        the user creates the field, and follows the type and the text
        (F-EDT-04 AC17).
        """
        self.noticeLabel = None
        if self.objTypeHint is not Entity or "entity_type" not in (
            self.reqParamsDict
        ):
            return
        label = QLabel(self)
        label.setWordWrap(True)
        label.setStyleSheet("font-style: italic;")
        self.noticeLabel = label
        row = self._rowOfParam("global_asset_id")
        self.layout().insertRow(
            row + 1 if row is not None else self.layout().rowCount(), label
        )
        self._refreshNotice()

    def _rowOfParam(self, param: str):
        layout = self.layout()
        title = self.getWidgetTitle(param)
        for row in range(layout.rowCount()):
            item = layout.itemAt(row, QFormLayout.ItemRole.LabelRole)
            if item is not None and getattr(item.widget(), "text", None):
                if item.widget().text() == title:
                    return row
        return None

    def _refreshNotice(self, *_):
        """Show or hide the entity notice for the current type and text."""
        label = getattr(self, "noticeLabel", None)
        if label is None:
            return
        typeWidget = self.paramWidgets.get("entity_type")
        textWidget = self.paramWidgets.get("global_asset_id")
        selfManaged = (
            typeWidget is not None
            and typeWidget.widget.currentData()
            is EntityType.SELF_MANAGED_ENTITY
        )
        text = textWidget.widget.text() if textWidget is not None else ""
        problem = (
            entity_global_asset_id_problem(selfManaged, text)
            if hints_mode().is_on
            else None
        )
        label.setText(problem or "")
        label.setVisible(problem is not None)

    def getWidgetTitle(self, param: str):
        title = param.strip("_")
        if param not in self.defaultParams:
            title = f"{title}*"
        return title

    def getPreObj(self):
        kwargs = {}
        for param, widget in self.paramWidgets.items():
            kwargs[param] = widget.getPreObj()
        for param, value in self.paramsToHide.items():
            value = delAASParent(value)
            kwargs[param] = value
        try:
            return PreObject(self.objTypeHint, (), kwargs)
        except TypeError:
            positional_arg_defaults = ClassesInfo.positionalArgDefaults(
                self.objTypeHint
            )
            for arg in positional_arg_defaults:
                kwargs[arg] = positional_arg_defaults[arg]
            for arg in ClassesInfo.defaultParamsToHide(object):
                try:
                    kwargs.pop(arg)
                except KeyError:
                    continue
        return PreObject(self.objTypeHint, (), kwargs)

    def getObj2add(self):
        """Return resulting obj due to user input data

        :raise ValueError if the values contradict each other, like a Range
            with a minimum above its maximum
        """
        obj = self.getPreObj().init()
        check_new_object(obj)
        return obj

    def delInputWidget(self, widget: QWidget):
        self.inputWidgets.remove(widget)
        for paramName, paramWidget in self.paramWidgets.items():
            if widget is paramWidget:
                self.paramWidgets.pop(paramName)
                break
        self.layout().removeRow(widget)
        self.adjustSize()

    def replaceOptionalParamWidgetWithCreateBtn(self):
        widget = self.sender()
        widgetRow = self.findWidgetRow(widget)

        widgets = list(self.paramWidgets.values())
        if widgetRow is not None and widget in widgets:
            params = list(self.paramWidgets.keys())
            paramName = params[widgets.index(widget)]
            btn = self.getCreatePushBtn(paramName)
            self.layout().insertRow(
                widgetRow, self.getWidgetTitle(paramName), btn
            )
            self.delInputWidget(widget)
        self._refreshNotice()
        self.layout().update()

    def findWidgetRow(self, widget: QWidget):
        layout: QFormLayout = self.layout()
        for row in range(layout.rowCount()):
            item = layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if widget == item.widget():
                return row
        return None

    def getCreatePushBtn(self, paramName: str):
        btn = widgets.buttons.CreateOptionalParamBtn(
            "Create",
            paramName=paramName,
            objTypehint=self.reqParamsDict[paramName],
            parent=self,
            clicked=self.addWidget4optionalParam,
        )
        return btn

    def addWidget4optionalParam(self):
        layout: QFormLayout = self.layout()
        for row in range(layout.rowCount()):
            try:
                item = layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
                if self.sender() == item.widget():
                    createBtn: widgets.buttons.CreateOptionalParamBtn = (
                        item.widget()
                    )
                    kwargs = copy.copy(self.kwargs)
                    kwargs.update({"optional": True})
                    widget = self.getInputWidget(
                        createBtn.paramName, val=None, **kwargs
                    )
                    layout.removeRow(row)
                    self.insertInputWidget(widget, createBtn.paramName, row)
                    break
            except Exception as e:
                ErrorMessageBox.withTraceback(self, str(e)).exec()

    def setVal4param(self, param: str, val):
        paramWidget = self.paramWidgets[param]
        paramWidget.setVal(val)

    def setVal(self, val):
        if val and isValOk4Typehint(val, self.objTypeHint):
            self.objVal = val
            for widget in reversed(self.inputWidgets):
                self.delInputWidget(widget)
            self.initLayout()
        else:
            print(
                "Value does not fit to req obj type",
                type(val),
                self.objTypeHint,
            )


class SingleWidgetGroupBox(GroupBox):
    def __init__(
        self,
        widget: Union[
            widgets.editWidgets.StandardInputWidget,
            widgets.editWidgets.SpecialInputWidget,
        ],
        parent=None,
    ):
        super(SingleWidgetGroupBox, self).__init__(widget.objType, parent)
        self.inputWidget = widget
        self.layout().addWidget(widget)

    def getPreObj(self):
        return self.inputWidget.getPreObj()

    def getObj2add(self):
        """Return resulting obj due to user input data"""
        return self.getPreObj().init()

    def setVal(self, val):
        self.inputWidget.setVal(val)


class IterableGroupBox(GroupBox):
    def __init__(self, objTypeHint, **kwargs):
        super().__init__(objTypeHint, **kwargs)
        self.argTypes = list(getArgs(self.objTypeHint))
        self.kwargs = kwargs.copy() if kwargs else {}
        plusButton = QPushButton(
            f"Add Item", self, toolTip="Add item", clicked=self._addInputWidget
        )
        self.layout().addRow(plusButton)
        self.inputWidgets = []
        self.setVal(self.objVal)

    def _getItemType(self):
        if ... in self.argTypes:
            self.argTypes.remove(...)

        if not issubtype(self.objTypeHint, dict):
            if len(self.argTypes) == 1:
                argType = self.argTypes[0]
            else:
                raise TypeError(
                    f"expected 1 argument, got {len(self.argTypes)}",
                    self.argTypes,
                )
        else:  # if parentType = dict
            if len(self.argTypes) == 2:
                DictItem.__new__.__annotations__["key"] = self.argTypes[0]
                DictItem.__new__.__annotations__["value"] = self.argTypes[1]
                argType = DictItem
            else:
                raise TypeError(
                    f"expected 2 arguments, got {len(self.argTypes)}",
                    self.argTypes,
                )
        return argType

    def _addInputWidget(self, objVal=None):
        itemType = self._getItemType()

        self.kwargs.update(
            {
                "title": f"{getTypeName(itemType)} {len(self.inputWidgets) + 1}",
                "rmDefParams": self.rmDefParams,
                "objVal": objVal,
            }
        )
        widget = InputWidgetUtil.getInputWidget(itemType, **self.kwargs)
        if not isinstance(widget, GroupBox):
            widget = SingleWidgetGroupBox(widget)
        widget.setClosable(True)
        widget.setFlat(True)
        widget.toggled.connect(lambda: self.delInputWidget(widget))
        self.inputWidgets.append(widget)
        self.layout().insertRow(self.layout().count() - 1, widget)
        self.adjustSize()

    def delInputWidget(self, widget: QWidget):
        self.layout().removeWidget(widget)
        widget.close()
        self.inputWidgets.remove(widget)
        for i, widget in enumerate(self.inputWidgets):
            res: str = widget.title().rstrip("0123456789")
            widget.setTitle(f"{res}{i + 1}")
        self.adjustSize()
        self.window().adjustSize()

    def getPreObj(self):
        listObj = []
        for widget in self.inputWidgets:
            listObj.append(widget.getPreObj())
        typ = typeHintToType(self.objTypeHint)
        return PreObject(typ, (listObj,), {})

    def getObj2add(self):
        """Return resulting obj due to user input data"""
        return self.getPreObj().init()

    def setVal(self, val):
        if isinstance(val, dict):
            val = [DictItem(key, value) for key, value in val.items()]
        elif isoftype(val, PreObject) and issubtype(val.objType, dict):
            val = [
                DictItem(item[0], item[1]) for item in val.args
            ]  # FIXME: look how PreObjects for dicts are created
        elif isoftype(val, PreObject) and issubtype(val.objType, LangStringSet):
            val = [
                DictItem(item[0], item[1]) for item in val.args[0].args[0]
            ]  # FIXME: look how PreObjects for dicts are created

        if val and (
            isIterable(val)
            or (isoftype(val, PreObject) and isIterableType(val.objType))
        ):
            for widget in reversed(self.inputWidgets):
                self.delInputWidget(widget)
            self.objVal = val
            for val in self.objVal:
                self._addInputWidget(val)
        else:
            print("Value is not iterable")
            for widget in reversed(self.inputWidgets):
                self.delInputWidget(widget)


class LangStringSetGroupBox(IterableGroupBox):
    """The rows of a multi-language text, a language and a text each.

    A new row starts with the first default language that no row has yet, and
    `startLanguages` gives a new box an empty row for each of them (F-EDT-04
    AC2). A row whose text stays empty is left out of the text that is made,
    because the SDK refuses an empty text, and so is the whole text when no
    row has one.
    """

    def __init__(self, objTypeHint, **kwargs):
        self.langStringTypeHint = objTypeHint
        objTypeHint = Dict[str, str]
        # The text of a language may have line breaks, its language may not.
        kwargs["multilineParams"] = {"value"}
        # Only this box starts with rows, so its rows must not get the wish.
        startLanguages = tuple(kwargs.pop("startLanguages", ()))
        super().__init__(objTypeHint, **kwargs)
        if not self.inputWidgets:
            for language in startLanguages:
                self._addInputWidget(DictItem(language, ""))

    def _addInputWidget(self, objVal=None):
        # The button passes its `checked` state as the first argument.
        if objVal is None or isinstance(objVal, bool):
            objVal = DictItem(self._nextLanguage(), "")
        super()._addInputWidget(objVal)

    def _nextLanguage(self) -> str:
        """Return the first default language that no row has, or nothing."""
        from aas_editor.ui.user_defaults import default_languages

        used = set()
        for widget in self.inputWidgets:
            row = getattr(widget, "inputWidget", widget)
            key = getattr(row, "paramWidgets", {}).get("key")
            if key is not None:
                used.add(key.widget.text().lower())
        return next(
            (tag for tag in default_languages() if tag.lower() not in used),
            "",
        )

    def _filledWidgets(self):
        """Return the rows that have a text."""
        return [
            widget for widget in self.inputWidgets if widget.getObj2add().value
        ]

    def getPreObj(self):
        problems = check_language_tags(
            widget.getObj2add().key for widget in self._filledWidgets()
        )
        if problems:
            raise ValueError("\n".join(problems))
        listObj = [widget.getPreObj() for widget in self._filledWidgets()]
        if not listObj and self.optional:
            return PreObject.useExistingObject(None)
        preObjDict = PreObject(typeHintToType(Dict[str, str]), (listObj,), {})
        return PreObject(self.langStringTypeHint, (preObjDict,), {})

    def setVal(self, val):
        if isinstance(val, LangStringSet):
            super().setVal(copy.copy(val._dict))
        else:
            super().setVal(val)


class TypeOptionObjGroupBox(GroupBox):
    """GroupBox with option to choose widget for which type will be generated"""

    def __init__(self, objTypes: Iterable, defType=str, **kwargs):
        objTypes = list(objTypes)
        super(TypeOptionObjGroupBox, self).__init__(objTypes[0], **kwargs)

        self.objTypes = objTypes
        # remove abstract types
        for typ in list(self.objTypes):
            if isabstract(typ):
                self.objTypes.remove(typ)

        self.initTypeComboBox(defType=defType)
        currObjType = self.typeComboBox.currentData()

        kwargs["parent"] = self
        kwargs["title"] = ""
        self.widget = QWidget()
        self.replaceGroupBoxWidget(currObjType, **kwargs)
        self.layout().addRow(self.widget)

        # change input widget for new type if type in combobox changed
        self.typeComboBox.currentIndexChanged.connect(
            lambda i: self.replaceGroupBoxWidget(
                self.typeComboBox.itemData(i), **kwargs
            )
        )

    def initTypeComboBox(self, defType=str):
        """Init func for ComboBox where desired Type of input data will be chosen"""
        self.typeComboBox = widgets.editWidgets.CompleterComboBox(self)
        for typ in self.objTypes:
            self.typeComboBox.addItem(getTypeName(typ), typ)
            self.typeComboBox.model().sort(0, Qt.SortOrder.AscendingOrder)
        if self.objVal:
            objValType = (
                self.objVal.objType
                if isoftype(self.objVal, PreObject)
                else type(self.objVal)
            )
            self.typeComboBox.setCurrentIndex(
                self.typeComboBox.findData(objValType)
            )
        elif defType is not None and defType in self.objTypes:
            index = self.typeComboBox.findText(
                getTypeName(defType), Qt.MatchFlag.MatchExactly
            )
            if index > -1:
                self.typeComboBox.setCurrentIndex(index)
        else:
            self.typeComboBox.setCurrentIndex(0)
        self.layout().addRow(self.typeComboBox)

    def replaceGroupBoxWidget(self, objType, **kwargs):
        """Changes input GroupBox due to objType structure"""
        kwargs["objVal"] = self.objVal
        kwargs["paramsToHide"] = {}
        kwargs["paramsToAttrs"] = {}
        includeInheritedTyps = False if inheritors(objType) else False
        newWidget = InputWidgetUtil.getInputWidget(
            objType, includeInheritedTyps=includeInheritedTyps, **kwargs
        )
        self.layout().replaceWidget(self.widget, newWidget)
        self.widget.close()
        newWidget.showMinimized()
        self.widget = newWidget
        if isinstance(self.widget, QGroupBox):
            self.widget.setFlat(True)
        if (
            isinstance(self.widget, (ObjGroupBox, IterableGroupBox))
            and not self.widget.inputWidgets
        ):
            self.widget.hide()
        self.adjustSize()

    def getPreObj(self):
        return self.widget.getPreObj()

    def getObj2add(self):
        """Return resulting obj due to user input data"""
        return self.widget.getObj2add()

    def setVal(self, val):
        valType = val.objType if isoftype(val, PreObject) else type(val)
        if valType in self.objTypes:
            self.objVal = val
            self.typeComboBox.setCurrentIndex(
                self.typeComboBox.findData(type(self.objVal))
            )


class ModelReferenceGroupBox(ObjGroupBox):
    # use CHOOSE_FRM_VIEW if no chooseFrmView is given
    # can be changed outside of class
    CHOOSE_FRM_VIEW = None

    def __init__(self, objTypeHint, chooseFrmView=None, **kwargs):
        super(ModelReferenceGroupBox, self).__init__(objTypeHint, **kwargs)
        self.chooseFrmView: "TreeView" = (
            chooseFrmView if chooseFrmView else self.CHOOSE_FRM_VIEW
        )
        if self.chooseFrmView:
            plusButton = QPushButton(
                f"Choose from local",
                self,
                toolTip="Choose element for reference",
                clicked=self.chooseFromLocal,
            )
            self.layout().addRow(plusButton)

    def chooseFromLocal(self):
        from aas_editor.treeviews.treeview_pack import PackTreeView
        from aas_editor.dialogs import ChooseItemDialog

        tree = PackTreeView(editEnabled=False)
        sourceModel = self.chooseFrmView.sourceModel()
        tree.setModel(sourceModel)

        dialog = ChooseItemDialog(
            view=tree,
            parent=self,
            title="Choose item for reference",
            validator=lambda chosenIndex: isinstance(
                chosenIndex.data(OBJECT_ROLE), Referable
            ),
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            print("Item adding accepted")
            item = dialog.getChosenItem()
            referable = item.data(OBJECT_ROLE)
            reference = ModelReference.from_referable(referable)
            self.setVal(reference)
        else:
            print("Item adding cancelled")
        dialog.deleteLater()


class OptionGroupBox(QGroupBox):
    def currOption(self):
        pass

    def chosenOption(self):
        pass

    def applyChosenOption(self):
        pass
