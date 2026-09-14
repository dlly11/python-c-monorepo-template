# Python core

`example-core` owns the shared message value, message categories, name normalization, and message
construction used by the other Python packages. It has no workspace dependencies.

Import its public API from `example_core`:

```python
from example_core import Message, MessageKind, create_message, normalize_name
```

```{toctree}
:maxdepth: 1

examples
api
```
