#  Copyright (C) 2025  Igor Garmaev, garmaev@gmx.net
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/
from inspect import isabstract
from typing import Union

from PyQt6.QtWidgets import QWidget
from basyx.aas.model import (
    ExternalReference,
    LangStringSet,
    ModelReference,
    Reference,
)

import aas_editor.widgets as widgets
import aas_editor.widgets.editWidgets
import aas_editor.widgets.groupBoxes
from aas_editor.domain.typed_values import is_value_hint, is_value_type_hint
from aas_editor.settings import DEFAULT_INHERITOR
from aas_editor.utils.util import (
    getParamsAndTypehints4init,
    getReqParams4init,
    inheritors,
)
from aas_editor.utils.util_classes import ClassesInfo
from aas_editor.utils.util_type import (
    removeOptional,
    isOptional,
    isIterableType,
    issubtype,
    isUnion,
    getArgs,
)
from aas_editor.utils.util import isSimpleIterableType, isValOk4Typehint


class InputWidgetUtil:
    @classmethod
    def handleTypeHint(cls, objTypeHint, parent):
        return cls._handleTypeHint(objTypeHint, parent)

    @classmethod
    def _handleTypeHint(cls, objTypeHint, parent):
        objTypeHint = removeOptional(objTypeHint)
        return objTypeHint

    @classmethod
    def getInputWidget(
        cls,
        objTypeHint,
        rmDefParams=True,
        title="",
        paramsToHide: dict = None,
        parent=None,
        objVal=None,
        paramsToAttrs=None,
        includeInheritedTyps=True,
        **kwargs,
    ) -> QWidget:
        optional = True if isOptional(objTypeHint) else False
        objTypeHint = cls.handleTypeHint(objTypeHint, parent)

        if objVal and not isValOk4Typehint(objVal, objTypeHint):
            print(
                "Given object type does not match to real object type:",
                objTypeHint,
                objVal,
            )
            objVal = None

        paramsToAttrs = (
            paramsToAttrs
            if paramsToAttrs
            else ClassesInfo.paramsToAttrs(objTypeHint)
        )
        paramsToHide = cls.handleParamsToHide(
            objTypeHint, objVal, rmDefParams, paramsToHide, paramsToAttrs
        )

        kwargs = {
            **kwargs,
            "rmDefParams": rmDefParams,
            "title": title,
            "paramsToHide": paramsToHide,
            "paramsToAttrs": paramsToAttrs,
            "parent": parent,
            "objVal": objVal,
            "optional": optional,
        }
        widget = cls.getWidget4typehint(
            objTypeHint, includeInheritedTyps, **kwargs
        )
        return widget

    @classmethod
    def handleParamsToHide(
        cls, objTypeHint, objVal, rmDefParams, paramsToHide, paramsToAttrs
    ):
        # if obj is given and rmDefParams = True, save all not mandatory init params of obj with val in paramsToHide
        # if obj is given and rmDefParams = False, save all hidden init params of obj with val in paramsToHide
        # and show user only required params to set

        paramsToHide = (
            paramsToHide
            if paramsToHide
            else ClassesInfo.defaultParamsToHide(objTypeHint)
        )

        params, paramsDefaults = getParamsAndTypehints4init(objTypeHint)
        reqParams = getReqParams4init(objTypeHint, rmDefParams=True)
        hiddenAttrs = ClassesInfo.hiddenAttrs(objTypeHint)

        for param in params.keys():
            attr = paramsToAttrs.get(param, param)

            if rmDefParams and objVal:
                if param in reqParams:
                    continue
                else:
                    paramsToHide[param] = getattr(objVal, attr)
            elif attr in hiddenAttrs and param not in paramsToHide:
                if objVal:
                    paramsToHide[param] = getattr(objVal, attr)
                elif param in paramsDefaults:
                    paramsToHide[param] = paramsDefaults[param]
        return paramsToHide

    @classmethod
    def getWidget4typehint(cls, objTypeHint, includeInheritedTyps, **kwargs):
        if is_value_type_hint(objTypeHint):
            # A list of the XSD types, not a list of Python classes.
            widget = widgets.editWidgets.ValueTypeInputWidget(
                objTypeHint, **kwargs
            )
        elif is_value_hint(objTypeHint):
            # One line of text that follows the value type, not a list of types.
            widget = widgets.editWidgets.TypedValueInputWidget(
                objTypeHint, **kwargs
            )
        elif objTypeHint is Reference:
            # The user chooses external or model, and can pick the target.
            from aas_editor.ui.reference_fields import ReferenceGroupBox

            widget = ReferenceGroupBox(
                inheritors(objTypeHint),
                defType=DEFAULT_INHERITOR.get(objTypeHint, None),
                **kwargs,
            )
        elif issubtype(objTypeHint, ModelReference):
            from aas_editor.ui.reference_fields import ModelReferenceField

            widget = ModelReferenceField(objTypeHint, **kwargs)
        elif objTypeHint is ExternalReference:
            from aas_editor.ui.reference_fields import ExternalReferenceField

            widget = ExternalReferenceField(objTypeHint, **kwargs)
        elif isabstract(objTypeHint) and not isIterableType(objTypeHint):
            objTypes = inheritors(objTypeHint)
            kwargs["defType"] = DEFAULT_INHERITOR.get(objTypeHint, None)
            widget = widgets.groupBoxes.TypeOptionObjGroupBox(
                objTypes, **kwargs
            )
        elif issubtype(objTypeHint, LangStringSet):
            if kwargs.get("objVal") is None and "startLanguages" not in kwargs:
                # "Create w/ default": a new text starts with one empty row in
                # the default language (F-EDT-06 AC1).
                from aas_editor.ui.user_defaults import first_default_language

                kwargs["startLanguages"] = (first_default_language(),)
            widget = widgets.groupBoxes.LangStringSetGroupBox(
                objTypeHint, **kwargs
            )
        elif isSimpleIterableType(objTypeHint):
            widget = widgets.groupBoxes.IterableGroupBox(objTypeHint, **kwargs)
        elif isUnion(objTypeHint):
            objTypes = getArgs(objTypeHint)
            widget = widgets.groupBoxes.TypeOptionObjGroupBox(
                objTypes, **kwargs
            )
        elif issubtype(objTypeHint, ModelReference):
            widget = widgets.groupBoxes.ModelReferenceGroupBox(
                objTypeHint, **kwargs
            )
        elif issubtype(
            objTypeHint, widgets.editWidgets.SpecialInputWidget.types
        ):
            widget = widgets.editWidgets.SpecialInputWidget(
                objTypeHint, **kwargs
            )
        elif issubtype(
            objTypeHint, widgets.editWidgets.StandardInputWidget.types
        ):
            widget = widgets.editWidgets.StandardInputWidget(
                objTypeHint, **kwargs
            )
        elif includeInheritedTyps and inheritors(objTypeHint):
            objTypes = list(inheritors(objTypeHint))
            objTypes.append(objTypeHint)
            kwargs["defType"] = DEFAULT_INHERITOR.get(objTypeHint, None)
            widget = widgets.groupBoxes.TypeOptionObjGroupBox(
                objTypes, **kwargs
            )
        else:
            widget = widgets.groupBoxes.ObjGroupBox(objTypeHint, **kwargs)
        return widget
