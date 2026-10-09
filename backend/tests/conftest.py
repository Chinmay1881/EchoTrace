import pytest

from echotrace import config


@pytest.fixture(autouse=True)
def normal_sensitivity():
    """Tests run against the 'normal' profile unless they select another one explicitly."""
    old = config.SENSITIVITY
    config.set_sensitivity("normal")
    yield
    config.set_sensitivity(old)
