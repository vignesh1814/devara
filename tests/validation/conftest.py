import pytest
from tests.validation.helpers import OPTS


@pytest.fixture(params=OPTS)
def opt(request):
    return request.param
