# Type Checking Notes

## Type Checking with `ty`

This project uses [`ty`](https://docs.astral.sh/ty/) for static type checking, which is a fast, modern alternative to mypy.

## Current Status

The codebase has been configured for type checking with `ty`. Some type errors remain due to:

1. **Third-party library stubs**: Some LangChain/LangGraph imports don't have complete type stubs
2. **Dynamic typing**: Some libraries use dynamic typing that's hard to statically analyze

## Running Type Checks

```bash
# Check all files
uvx ty check

# Check specific directory
uvx ty check backend/

# With different output format
uvx ty check --output-format concise
```

## Configuration

Type checking is configured in `pyproject.toml`:

```toml
[tool.ty.rules]
# Error on critical issues
possibly-unresolved-reference = "error"
unresolved-import = "error"
unresolved-name = "error"
call-non-callable = "error"
division-by-zero = "error"
invalid-argument-type = "error"
invalid-return-type = "error"
unknown-argument = "error"
unknown-keyword-argument = "error"
# Warn on potential issues
possibly-missing-attribute = "warn"
unused-ignore-comment = "warn"
```

## Suppressing Errors

When you encounter false positives or issues with third-party libraries:

### Inline Suppression

```python
# Suppress a specific error on one line
result = some_function()  # type: ignore[unknown-argument]

# Suppress multiple errors
value = complex_call()  # type: ignore[unknown-argument, invalid-return-type]
```

### File-level Overrides

In `pyproject.toml`:

```toml
[[tool.ty.overrides]]
include = ["backend/mcp/**"]

[tool.ty.overrides.rules]
# Relax rules for MCP integration code
unresolved-import = "warn"
```

## Common Suppressions in This Project

### LangGraph/LangChain Imports

Some LangGraph modules don't have complete type stubs:

```python
from langgraph.checkpoint.sqlite import SqliteSaver  # type: ignore[import-not-found]
```

### Dynamic Library Arguments

ChatOpenAI accepts `model_name` but ty doesn't recognize it:

```python
self.llm = ChatOpenAI(model_name=model_name, temperature=0)  # type: ignore[call-arg]
```

### Return Type Mismatches

When compiled graphs have complex return types:

```python
def _build_graph(self) -> Any:  # Returns CompiledGraph but type is complex
    workflow = StateGraph(AgentState)
    # ...
    return workflow.compile(checkpointer=self.checkpointer)
```

## Improving Type Coverage

To improve type checking over time:

1. **Add type stubs**: Create `.pyi` files for untyped libraries
2. **Use Protocol classes**: For duck-typed interfaces
3. **Add assertions**: Help ty understand runtime guarantees
4. **Update library versions**: Newer versions may have better typing

## Available Rules

See the [ty rules documentation](https://docs.astral.sh/ty/reference/rules/) for all available rules.

Some useful rules not currently enabled:

- `index-out-of-bounds` - Detect list/tuple index errors
- `unsupported-operator` - Invalid operator usage
- `invalid-parameter-default` - Type mismatches in defaults
- `redundant-cast` - Unnecessary type casts

Add these in `pyproject.toml` as needed.

## Integration with CI/CD

For CI/CD pipelines:

```bash
# Exit with error code if type check fails
uvx ty check

# Error on warnings too
uvx ty check --error-on-warning
```

In `pyproject.toml`:

```toml
[tool.ty.terminal]
error-on-warning = true  # Treat warnings as errors
output-format = "concise"  # Cleaner CI output
```

## Resources

- [ty Documentation](https://docs.astral.sh/ty/)
- [ty Configuration Reference](https://docs.astral.sh/ty/reference/configuration/)
- [ty Rules Reference](https://docs.astral.sh/ty/reference/rules/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)

