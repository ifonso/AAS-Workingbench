"""Operations that change several objects at once and keep references intact.

Each operation first makes a plan without changing anything, so a user
interface can show what would happen. The plan then builds the commands, which
the caller pushes on the command stack of the package inside one group, so a
single undo takes everything back.
"""
