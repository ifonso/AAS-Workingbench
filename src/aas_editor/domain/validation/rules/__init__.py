"""The rules of the editor, one module for each topic."""

from aas_editor.domain.validation.rule import Rule
from aas_editor.domain.validation.rules import assets
from aas_editor.domain.validation.rules import files
from aas_editor.domain.validation.rules import identity
from aas_editor.domain.validation.rules import references
from aas_editor.domain.validation.rules import templates
from aas_editor.domain.validation.rules import values

# In the order that findings with the same severity are listed.
ALL_RULES: tuple[Rule, ...] = (
    *identity.RULES,
    *references.RULES,
    *files.RULES,
    *values.RULES,
    *assets.RULES,
    *templates.RULES,
)
