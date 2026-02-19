import pytest

from ops.ecris.drivers.dummy import ConstantDataSource


@pytest.mark.asyncio
async def test_constant_data_source():
    data_source = ConstantDataSource(initial_read_value=10)
    read_key = ConstantDataSource.DataKeys.READ_VALUE
    set_key = ConstantDataSource.DataKeys.SET_VALUE
    read_value = await data_source.read_data(data_key=read_key)
    set_value = await data_source.read_data(data_key=set_key)
    assert read_value == 10
    assert set_value == 0
