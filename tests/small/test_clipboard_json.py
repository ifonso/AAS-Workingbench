"""Tests for AAS JSON on the clipboard."""

import json

from basyx.aas import model
import pytest
from tests.factories import make_collection
from tests.factories import make_concept_description
from tests.factories import make_list
from tests.factories import make_operation
from tests.factories import make_property
from tests.factories import make_submodel

from aas_editor.domain.clipboard_json import ClipboardError
from aas_editor.domain.clipboard_json import clone
from aas_editor.domain.clipboard_json import dump_objects
from aas_editor.domain.clipboard_json import load_objects


class TestRoundTrip:
    def test_a_property_comes_back_with_the_same_content(self) -> None:
        original = make_property("Voltage", "230")

        (copied,) = load_objects(dump_objects([original]))

        assert isinstance(copied, model.Property)
        assert (copied.id_short, copied.value) == ("Voltage", "230")
        assert copied.value_type is model.datatypes.String

    def test_several_objects_come_back_in_order(self) -> None:
        objects = [make_property("A"), make_property("B")]

        copied = load_objects(dump_objects(objects))

        assert [o.id_short for o in copied] == ["A", "B"]

    def test_the_text_is_a_json_array_of_the_metamodel(self) -> None:
        text = dump_objects([make_property("P")])

        assert json.loads(text)[0]["modelType"] == "Property"

    def test_a_copy_has_no_parent(self) -> None:
        collection = make_collection("C", [make_property("P")])
        make_submodel(elements=[collection])

        copied = clone(collection)

        assert copied.parent is None
        assert copied is not collection

    @pytest.mark.parametrize(
        "element",
        [
            make_collection("C", [make_property("a")]),
            make_list("L", [make_property("x", "1"), make_property("y", "2")]),
            make_operation("O", [make_property("i")], [make_property("o")]),
        ],
        ids=["collection", "list", "operation"],
    )
    def test_containers_keep_their_members_in_order(
        self, element: model.SubmodelElement
    ) -> None:
        copied = clone(element)

        assert dump_objects([copied]) == dump_objects([element])

    def test_a_submodel_and_a_concept_description_round_trip(self) -> None:
        submodel = make_submodel(elements=[make_property("P")])
        concept = make_concept_description()

        copied = load_objects(dump_objects([submodel, concept]))

        assert [type(o) for o in copied] == [
            model.Submodel,
            model.ConceptDescription,
        ]


class TestBadContent:
    @pytest.mark.parametrize(
        "text",
        [
            "hello",
            "",
            "   ",
            "[1, 2, 3]",
            '{"a": 1}',
            "[]",
            "[{",
            '{"modelType": "Nonsense"}',
            '{"modelType": "Property"}',
            '[{"modelType": "Property", "idShort": "1bad", "valueType": "xs:string"}]',
            "__import__('os').system('echo x')",
            '"just a string"',
        ],
    )
    def test_text_that_is_no_aas_object_is_refused_with_a_message(
        self, text: str
    ) -> None:
        with pytest.raises(ClipboardError) as error:
            load_objects(text)

        assert str(error.value)

    def test_deeply_nested_json_is_refused_and_does_not_crash(self) -> None:
        with pytest.raises(ClipboardError):
            load_objects("[" * 50_000)

    def test_huge_text_is_refused(self) -> None:
        with pytest.raises(ClipboardError):
            load_objects("[" + " " * 30_000_000 + "]")

    def test_python_code_is_never_evaluated(self) -> None:
        marker = "evaluated"
        text = f'[{{"modelType": "Property", "idShort": "{marker}"}}]'

        with pytest.raises(ClipboardError):
            load_objects(text)
