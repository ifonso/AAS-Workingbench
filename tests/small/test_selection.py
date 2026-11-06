"""Tests for the facts about a selection of several rows (F-EDT-09)."""

from tests.factories import make_collection
from tests.factories import make_operation
from tests.factories import make_property
from tests.factories import make_submodel

from aas_editor.domain.selection import MULTIPLE_HEADER
from aas_editor.domain.selection import has_mixed_variable_directions
from aas_editor.domain.selection import summarize
from aas_editor.domain.selection import variable_direction


def _operation():
    operation = make_operation(
        input_variables=[make_property("I1"), make_property("I2")],
        output_variables=[make_property("O1")],
        in_output_variables=[make_property("B1")],
    )
    make_submodel(elements=[operation])
    return operation


class TestVariableDirections:
    def test_each_variable_knows_its_direction(self) -> None:
        operation = _operation()

        assert [
            variable_direction(v)
            for v in (
                *operation.input_variable,
                *operation.output_variable,
                *operation.in_output_variable,
            )
        ] == ["input", "input", "output", "inoutput"]

    def test_an_element_outside_an_operation_has_no_direction(self) -> None:
        collection = make_collection("C", [make_property("P")])

        assert variable_direction(next(iter(collection.value))) is None
        assert variable_direction(object()) is None

    def test_variables_of_one_direction_are_not_mixed(self) -> None:
        operation = _operation()

        assert not has_mixed_variable_directions(list(operation.input_variable))

    def test_variables_of_two_directions_are_mixed(self) -> None:
        operation = _operation()
        chosen = [
            next(iter(operation.input_variable)),
            next(iter(operation.output_variable)),
        ]

        assert has_mixed_variable_directions(chosen)

    def test_an_element_that_is_no_variable_does_not_make_a_mix(self) -> None:
        operation = _operation()
        chosen = [next(iter(operation.input_variable)), make_property("Other")]

        assert not has_mixed_variable_directions(chosen)


class TestSummary:
    def test_two_siblings_get_the_header_of_package_explorer(self) -> None:
        collection = make_collection(
            "C", [make_property("A"), make_property("B")]
        )
        first, second = collection.value

        summary = summarize([(first, None), (second, None)])

        assert summary.header == MULTIPLE_HEADER == "Several elements selected"
        assert summary.kinds_text == "2 Property"
        assert summary.parents == 1
        assert summary.parent_line.startswith(
            "All in SubmodelElementCollection"
        )

    def test_rows_of_different_parents_are_counted(self) -> None:
        first = make_collection("C1", [make_property("A")])
        second = make_collection("C2", [make_property("B")])
        chosen = [next(iter(first.value)), next(iter(second.value))]

        summary = summarize([(obj, None) for obj in chosen])

        assert summary.parents == 2
        assert summary.parent_text is None
        assert "2 different parents" in summary.parent_line

    def test_the_kinds_are_counted_most_frequent_first(self) -> None:
        collection = make_collection(
            "C",
            [make_property("A"), make_property("B"), make_collection("D")],
        )

        summary = summarize([(obj, None) for obj in collection.value])

        assert summary.kinds == (
            ("Property", 2),
            ("SubmodelElementCollection", 1),
        )

    def test_one_row_and_none_have_their_own_headers(self) -> None:
        assert summarize([]).header == "Nothing selected"
        assert summarize([(make_property("A"), None)]).header == (
            "One element selected"
        )

    def test_the_summary_tells_about_mixed_directions(self) -> None:
        operation = _operation()
        chosen = [
            next(iter(operation.input_variable)),
            next(iter(operation.output_variable)),
        ]

        assert summarize([(obj, None) for obj in chosen]).mixed_directions
