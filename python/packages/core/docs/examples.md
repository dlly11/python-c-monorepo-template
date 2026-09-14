# Python core examples

## Normalize input

```python
from example_core import normalize_name

name = normalize_name("  Ada   Lovelace  ")
assert name == "Ada Lovelace"
```

Blank or whitespace-only names raise `ValueError`.

## Create a message

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
