# Python package A examples

## Default greeting

```python
from example_package_a import GreetingService

message = GreetingService().greet("Ada")
assert message.text == "Hello, Ada!"
assert message.source == "package_a"
```

## Custom prefix

```python
from example_package_a import GreetingService

message = GreetingService(prefix="Welcome").greet("Grace Hopper")
assert message.text == "Welcome, Grace Hopper!"
```
