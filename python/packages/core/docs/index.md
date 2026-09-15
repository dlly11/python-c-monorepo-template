# Python core

`example-core` owns the shared message value, message categories, name normalization, and message
construction used by the other Python packages. It has no workspace dependencies.

Import its public API from `example_core`:

```python
from example_core import Message, MessageKind, create_message, normalize_name
```

## Python core examples

### Normalize input

```python
from example_core import normalize_name

name = normalize_name("  Ada   Lovelace  ")
assert name == "Ada Lovelace"
```

Blank or whitespace-only names raise `ValueError`.

### Create a message

```python
from example_core import MessageKind, create_message

message = create_message(
    kind=MessageKind.GREETING,
    source="example",
    prefix="Welcome",
    name="Ada Lovelace",
)

assert message.text == "Welcome, Ada Lovelace!"
```

## Python core API

```{automodule} example_core.messages
:members:
:show-inheritance:
```
