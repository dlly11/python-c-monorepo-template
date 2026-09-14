# Python package B examples

## Default farewell

```python
from example_package_b import FarewellService

message = FarewellService().farewell("Ada")
assert message.text == "Goodbye, Ada!"
assert message.source == "package_b"
```

## Custom prefix

```python
from example_package_b import FarewellService

message = FarewellService(prefix="Until next time").farewell("Grace")
assert message.text == "Until next time, Grace!"
```
