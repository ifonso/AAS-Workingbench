"""Adding, removing, and replacing members of the containers of AAS objects."""

from basyx.aas import model
import pytest
from tests.factories import make_external_reference
from tests.factories import make_property
from tests.factories import make_reference_to
from tests.factories import make_submodel

from aas_editor.domain import containers


def _ids(namespace_set: model.NamespaceSet[model.SubmodelElement]) -> list[str]:
    return [element.id_short or "" for element in namespace_set]


def _texts(texts: dict[str, str]) -> model.MultiLanguageTextType:
    return model.MultiLanguageTextType(texts)


class TestNamespaceSet:
    def test_add_appends_when_no_index_is_given(self) -> None:
        submodel = make_submodel(elements=[make_property("a")])

        position = containers.add_member(
            submodel.submodel_element, make_property("n")
        )

        assert position == 1
        assert _ids(submodel.submodel_element) == ["a", "n"]

    def test_add_inserts_at_the_index(self) -> None:
        submodel = make_submodel(
            elements=[make_property("a"), make_property("b")]
        )

        position = containers.add_member(
            submodel.submodel_element, make_property("n"), 1
        )

        assert position == 1
        assert _ids(submodel.submodel_element) == ["a", "n", "b"]

    def test_remove_tells_the_position(self) -> None:
        elements = [make_property("a"), make_property("b"), make_property("c")]
        submodel = make_submodel(elements=elements)

        position = containers.remove_member(
            submodel.submodel_element, elements[1]
        )

        assert position == 1
        assert _ids(submodel.submodel_element) == ["a", "c"]

    def test_replace_keeps_the_position(self) -> None:
        elements = [make_property("a"), make_property("b"), make_property("c")]
        submodel = make_submodel(elements=elements)

        containers.replace_member(
            submodel.submodel_element, elements[0], make_property("n")
        )

        assert _ids(submodel.submodel_element) == ["n", "b", "c"]

    def test_add_changes_nothing_when_the_id_short_is_taken(self) -> None:
        submodel = make_submodel(
            elements=[make_property("a"), make_property("b")]
        )

        with pytest.raises(model.AASConstraintViolation):
            containers.add_member(
                submodel.submodel_element, make_property("a"), 0
            )

        assert _ids(submodel.submodel_element) == ["a", "b"]


class TestList:
    def test_add_inserts_at_the_index(self) -> None:
        items = ["a", "c"]

        position = containers.add_member(items, "b", 1)

        assert position == 1
        assert items == ["a", "b", "c"]

    def test_add_appends_when_the_index_is_beyond_the_end(self) -> None:
        items = ["a"]

        position = containers.add_member(items, "b", 9)

        assert position == 1
        assert items == ["a", "b"]

    def test_remove_finds_the_object_by_identity_first(self) -> None:
        first = ["same"]
        second = ["same"]
        items = [first, second]

        position = containers.remove_member(items, second)

        assert position == 1
        assert items[0] is first

    def test_remove_raises_when_the_object_is_missing(self) -> None:
        with pytest.raises(KeyError):
            containers.remove_member(["a"], "b")

    def test_replace_keeps_the_position(self) -> None:
        items = ["a", "b", "c"]

        containers.replace_member(items, "b", "z")

        assert items == ["a", "z", "c"]


class TestConstrainedList:
    """The supplemental semantic ids and the specific asset ids of the SDK."""

    @staticmethod
    def _element() -> model.Property:
        element = make_property("a")
        element.semantic_id = make_external_reference("urn:main")
        element.supplemental_semantic_id.extend(
            [
                make_external_reference("urn:one"),
                make_external_reference("urn:two"),
            ]
        )
        return element

    def test_add_inserts_at_the_index(self) -> None:
        element = self._element()

        position = containers.add_member(
            element.supplemental_semantic_id,
            make_external_reference("urn:n"),
            1,
        )

        assert position == 1
        assert [
            key.key[0].value for key in element.supplemental_semantic_id
        ] == [
            "urn:one",
            "urn:n",
            "urn:two",
        ]

    def test_remove_tells_the_position(self) -> None:
        element = self._element()

        position = containers.remove_member(
            element.supplemental_semantic_id, make_external_reference("urn:two")
        )

        assert position == 1
        assert len(element.supplemental_semantic_id) == 1

    def test_replace_keeps_the_position(self) -> None:
        element = self._element()

        containers.replace_member(
            element.supplemental_semantic_id,
            make_external_reference("urn:one"),
            make_external_reference("urn:new"),
        )

        assert [
            key.key[0].value for key in element.supplemental_semantic_id
        ] == [
            "urn:new",
            "urn:two",
        ]


class TestSet:
    def test_add_has_no_position(self) -> None:
        references: set[model.ModelReference[model.Submodel]] = set()
        reference = make_reference_to(make_submodel())

        position = containers.add_member(references, reference)

        assert position is None
        assert reference in references

    def test_add_refuses_an_equal_member(self) -> None:
        submodel = make_submodel()
        references = {make_reference_to(submodel)}

        with pytest.raises(ValueError, match="Already in the set"):
            containers.add_member(references, make_reference_to(submodel))

    def test_remove_raises_when_the_member_is_missing(self) -> None:
        with pytest.raises(KeyError):
            containers.remove_member(set[str](), "a")

    def test_replace_puts_the_new_member_in_the_set(self) -> None:
        members = {"a", "b"}

        containers.replace_member(members, "a", "z")

        assert members == {"b", "z"}


class TestMapping:
    def test_add_puts_the_entry_at_the_position(self) -> None:
        texts = _texts({"en": "one", "de": "eins"})

        position = containers.add_member(texts, ("fr", "un"), 1)

        assert position == 1
        assert list(texts) == ["en", "fr", "de"]

    def test_add_refuses_a_key_that_is_used(self) -> None:
        texts = _texts({"en": "one"})

        with pytest.raises(ValueError, match="Key already used"):
            containers.add_member(texts, ("en", "two"))

    def test_remove_tells_the_position(self) -> None:
        texts = _texts({"en": "one", "de": "eins", "fr": "un"})

        position = containers.remove_member(texts, ("de", "eins"))

        assert position == 1
        assert list(texts) == ["en", "fr"]

    def test_remove_refuses_the_last_entry(self) -> None:
        texts = _texts({"en": "one"})

        with pytest.raises(KeyError):
            containers.remove_member(texts, ("en", "one"))

        assert list(texts) == ["en"]

    def test_replace_changes_the_value_of_the_same_key(self) -> None:
        texts = _texts({"en": "one", "de": "eins"})

        containers.replace_member(texts, ("en", "one"), ("en", "uno"))

        assert dict(texts) == {"en": "uno", "de": "eins"}

    def test_replace_keeps_the_position_when_the_key_changes(self) -> None:
        texts = _texts({"en": "one", "de": "eins", "fr": "un"})

        containers.replace_member(texts, ("de", "eins"), ("es", "uno"))

        assert list(texts) == ["en", "es", "fr"]

    def test_replace_changes_nothing_when_the_new_key_is_invalid(self) -> None:
        texts = _texts({"en": "one", "de": "eins"})

        with pytest.raises(ValueError, match="BCP 47"):
            containers.replace_member(
                texts, ("de", "eins"), ("not a tag!", "x")
            )

        assert dict(texts) == {"en": "one", "de": "eins"}


def test_position_of_is_none_for_a_set() -> None:
    assert containers.position_of({"a"}, "a") is None


def test_add_raises_for_a_container_of_an_unknown_kind() -> None:
    with pytest.raises(TypeError):
        containers.add_member(object(), "a")
