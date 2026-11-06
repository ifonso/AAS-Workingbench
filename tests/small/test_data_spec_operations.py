"""Records, keys, empty attributes and value list imports."""

from basyx.aas import model
import pytest
from tests.factories import make_external_reference
from tests.factories import make_store
from tests.serialization import snapshot

from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import CommandStack
from aas_editor.application.commands import ReadOnlyError
from aas_editor.application.operations.data_specs import add_record_commands
from aas_editor.application.operations.data_specs import clear_empty_commands
from aas_editor.application.operations.data_specs import fix_keys_commands
from aas_editor.application.operations.data_specs import iec_records
from aas_editor.application.operations.data_specs import import_commands
from aas_editor.application.operations.data_specs import plan_fix_keys
from aas_editor.application.operations.data_specs import plan_value_list_import
from aas_editor.application.operations.data_specs import replace_record_commands
from aas_editor.domain.data_specifications import IEC_61360_TEMPLATE_KEY
from aas_editor.domain.data_specifications import Iec61360Draft
from aas_editor.domain.data_specifications import TemplateMatch
from aas_editor.domain.data_specifications import build_record
from aas_editor.domain.data_specifications import match_template


@pytest.fixture
def observer() -> ModelChangeObserver:
    return ModelChangeObserver()


def _content(**kwargs: object) -> model.DataSpecificationIEC61360:
    return model.DataSpecificationIEC61360(
        model.PreferredNameTypeIEC61360({"en": "N"}),
        **kwargs,  # type: ignore[arg-type]
    )


def _record(
    key: str = IEC_61360_TEMPLATE_KEY, **kwargs: object
) -> model.EmbeddedDataSpecification:
    return model.EmbeddedDataSpecification(
        make_external_reference(key), _content(**kwargs)
    )


def _concept(
    id_: str, *records: model.EmbeddedDataSpecification
) -> model.ConceptDescription:
    return model.ConceptDescription(
        id_, embedded_data_specifications=list(records)
    )


def _pair(value: str, id_: str) -> model.ValueReferencePair:
    return model.ValueReferencePair(value, make_external_reference(id_))


class TestRecords:
    def test_adding_a_record_is_one_step_with_undo_and_redo(
        self, observer: ModelChangeObserver
    ) -> None:
        concept = model.ConceptDescription("urn:cd:1", id_short="Speed")
        store = make_store(concept)
        stack = CommandStack()
        before = snapshot(store)
        record = build_record(Iec61360Draft(preferred_name=[("en", "Speed")]))

        for command in add_record_commands(observer, concept, record):
            stack.push(command)
        done = snapshot(store)
        stack.undo()

        assert concept.embedded_data_specifications == []
        assert snapshot(store) == before
        stack.redo()
        assert concept.embedded_data_specifications == [record]
        assert snapshot(store) == done

    def test_replacing_a_record_keeps_its_position(
        self, observer: ModelChangeObserver
    ) -> None:
        first, second = _record(), _record()
        concept = _concept("urn:cd:1", first, second)
        new = build_record(Iec61360Draft(preferred_name=[("en", "New")]))
        stack = CommandStack()

        for command in replace_record_commands(observer, concept, first, new):
            stack.push(command)

        assert concept.embedded_data_specifications == [new, second]
        stack.undo()
        assert concept.embedded_data_specifications == [first, second]

    def test_read_mode_refuses_a_new_record(
        self, observer: ModelChangeObserver
    ) -> None:
        concept = model.ConceptDescription("urn:cd:1")
        stack = CommandStack(is_editing=lambda: False)

        with pytest.raises(ReadOnlyError):
            for command in add_record_commands(observer, concept, _record()):
                stack.push(command)

        assert concept.embedded_data_specifications == []

    def test_only_records_with_iec_content_are_listed(self) -> None:
        concept = _concept("urn:cd:1", _record())

        ((record, content),) = iec_records(concept)

        assert record is concept.embedded_data_specifications[0]
        assert content is record.data_specification_content


class TestFixKeys:
    def test_the_plan_sorts_records_by_how_the_key_is_wrong(self) -> None:
        good = _concept("urn:cd:good", _record())
        older = _concept(
            "urn:cd:older",
            _record(
                "http://admin-shell.io/DataSpecificationTemplates/"
                "DataSpecificationIEC61360/3/0"
            ),
        )
        wrong = _concept("urn:cd:wrong", _record("0112/2///62683#ACE053#001"))

        plan = plan_fix_keys([good, older, wrong])

        assert [c.id for c, _ in plan.unknown] == ["urn:cd:wrong"]
        assert [c.id for c, _ in plan.other_spelling] == ["urn:cd:older"]
        assert plan.correct == 1
        assert not plan.is_empty

    def test_a_description_without_records_has_nothing_to_fix(self) -> None:
        plan = plan_fix_keys([model.ConceptDescription("urn:cd:1")])

        assert plan.is_empty
        assert plan.correct == 0

    def test_every_record_of_a_description_is_fixed_in_one_run(
        self, observer: ModelChangeObserver
    ) -> None:
        # The original stops after the first record of each description.
        concept = _concept("urn:cd:1", _record("a"), _record("b"), _record("c"))
        store = make_store(concept)
        stack = CommandStack()
        before = snapshot(store)
        plan = plan_fix_keys([concept])

        with stack.group("Fix"):
            for command in fix_keys_commands(observer, plan, True):
                stack.push(command)

        assert [
            match_template(r.data_specification)
            for r in concept.embedded_data_specifications
        ] == [TemplateMatch.CURRENT] * 3
        assert plan_fix_keys([concept]).is_empty
        stack.undo()
        assert snapshot(store) == before

    def test_other_spellings_are_left_unless_the_user_asks(
        self, observer: ModelChangeObserver
    ) -> None:
        older = _record(
            "https://admin-shell.io/DataSpecificationTemplates/"
            "DataSpecificationIec61360/3/0"
        )
        concept = _concept("urn:cd:1", older)
        plan = plan_fix_keys([concept])

        assert fix_keys_commands(observer, plan, False) == []
        assert len(fix_keys_commands(observer, plan, True)) == 1

    def test_the_fixed_reference_is_the_template_reference(
        self, observer: ModelChangeObserver
    ) -> None:
        concept = _concept("urn:cd:1", _record("nonsense"))
        stack = CommandStack()

        for command in fix_keys_commands(
            observer, plan_fix_keys([concept]), False
        ):
            stack.push(command)

        reference = concept.embedded_data_specifications[0].data_specification
        assert isinstance(reference, model.ExternalReference)
        assert [(k.type, k.value) for k in reference.key] == [
            (model.KeyTypes.GLOBAL_REFERENCE, IEC_61360_TEMPLATE_KEY)
        ]


class TestClearEmpty:
    def test_empty_attributes_are_removed_and_the_name_stays(
        self, observer: ModelChangeObserver
    ) -> None:
        content = _content(unit="", symbol="  ", value_list=set())
        concept = _concept(
            "urn:cd:1",
            model.EmbeddedDataSpecification(
                make_external_reference("k"), content
            ),
        )
        store = make_store(concept)
        stack = CommandStack()
        before = snapshot(store)

        with stack.group("Clear"):
            for command in clear_empty_commands(observer, content):
                stack.push(command)

        assert content.unit is None
        assert content.symbol is None
        assert content.value_list is None
        assert dict(content.preferred_name) == {"en": "N"}
        stack.undo()
        assert content.unit == ""
        assert content.value_list == set()
        assert snapshot(store) == before

    def test_content_without_empty_attributes_has_no_commands(
        self, observer: ModelChangeObserver
    ) -> None:
        assert clear_empty_commands(observer, _content(unit="m")) == []


class TestValueListImport:
    def test_new_pairs_are_added_to_the_old_ones(
        self, observer: ModelChangeObserver
    ) -> None:
        old = _pair("Red", "urn:red")
        content = _content(value_list={old})
        concept = _concept(
            "urn:cd:1",
            model.EmbeddedDataSpecification(
                make_external_reference("k"), content
            ),
        )
        store = make_store(concept)
        stack = CommandStack()
        before = snapshot(store)
        plan = plan_value_list_import(content, [_pair("Blue", "urn:blue")])

        for command in import_commands(observer, plan):
            stack.push(command)

        assert {p.value for p in content.value_list or ()} == {"Red", "Blue"}
        assert old in (content.value_list or ())
        stack.undo()
        assert content.value_list == {old}
        assert snapshot(store) == before
        stack.redo()
        assert {p.value for p in content.value_list or ()} == {"Red", "Blue"}

    def test_a_pair_that_the_list_has_is_not_added_twice(self) -> None:
        content = _content(value_list={_pair("Red", "urn:red")})

        plan = plan_value_list_import(
            content, [_pair("Red", "urn:red"), _pair("Green", "urn:green")]
        )

        assert [p.value for p in plan.added] == ["Green"]
        assert [p.value for p in plan.duplicates] == ["Red"]

    def test_a_pair_twice_in_the_input_is_added_once(self) -> None:
        content = _content()

        plan = plan_value_list_import(
            content, [_pair("Red", "urn:red"), _pair("Red", "urn:red")]
        )

        assert len(plan.added) == 1
        assert len(plan.duplicates) == 1

    def test_the_same_value_with_another_id_is_another_pair(self) -> None:
        content = _content(value_list={_pair("Red", "urn:red")})

        plan = plan_value_list_import(content, [_pair("Red", "urn:rot")])

        assert len(plan.added) == 1

    def test_importing_only_duplicates_makes_no_command(
        self, observer: ModelChangeObserver
    ) -> None:
        content = _content(value_list={_pair("Red", "urn:red")})
        plan = plan_value_list_import(content, [_pair("Red", "urn:red")])

        assert import_commands(observer, plan) == []

    def test_the_first_import_creates_the_list(
        self, observer: ModelChangeObserver
    ) -> None:
        content = _content()
        stack = CommandStack()
        plan = plan_value_list_import(content, [_pair("Red", "urn:red")])

        for command in import_commands(observer, plan):
            stack.push(command)
        assert content.value_list is not None
        stack.undo()

        assert content.value_list is None
