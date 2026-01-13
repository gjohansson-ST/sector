import pytest
from custom_components.sector.client import Retryable, ApiError
from collections import Counter


async def counting_function(
    counter: Counter, exception: Exception, count_before_success: int = 0
):
    counter["count"] += 1
    if counter["count"] == count_before_success:
        return counter["count"]
    raise exception


async def test_should_retry_on_retryable_exception():
    # Prepare
    retry = Retryable(attempts=3, retry_exceptions=(ApiError,), max_delay=0)
    count = Counter()

    # Act & Assert
    with pytest.raises(ApiError):
        await retry.run(
            lambda: counting_function(count, ApiError("Simulated API error"))
        )
    assert count["count"] == 3


async def test_should_not_retry_on_non_retryable_exception():
    # Prepare
    retry = Retryable(attempts=3, retry_exceptions=(ApiError,), max_delay=0)
    count = Counter()

    # Act & Assert
    with pytest.raises(RuntimeError):
        await retry.run(
            lambda: counting_function(count, RuntimeError("Simulated API error"))
        )
    assert count["count"] == 1


async def test_should_retry_until_success():
    # Prepare
    retry = Retryable(attempts=3, retry_exceptions=(ApiError,), max_delay=0)
    count = Counter()

    # Act & Assert
    result = await retry.run(
        lambda: counting_function(
            count, ApiError("Simulated API error"), count_before_success=2
        )
    )
    assert result == 2
