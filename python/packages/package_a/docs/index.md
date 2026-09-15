# Python package A

`example-package-a` provides `GreetingService`. It depends on `example-core` and does not depend
on package B or either application.

```python
from example_package_a import GreetingService
```

## Python package A examples

### Default greeting

```python
from example_package_a import GreetingService

message = GreetingService().greet("Ada")
assert message.text == "Hello, Ada!"
assert message.source == "package_a"
```

### Custom prefix

```python
from example_package_a import GreetingService

message = GreetingService(prefix="Welcome").greet("Grace Hopper")
assert message.text == "Welcome, Grace Hopper!"
```

## Python package A API

```{automodule} example_package_a.service
:members:
:show-inheritance:
```
