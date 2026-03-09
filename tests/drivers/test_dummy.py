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


@pytest.mark.asyncio
async def test_constant_data_source_write_data():
    data_source = ConstantDataSource(initial_read_value=10)
    set_key = ConstantDataSource.DataKeys.SET_VALUE
    await data_source.write_data(data_key=set_key, value=42)
    set_value = await data_source.read_data(data_key=set_key)
    assert set_value == 42


@pytest.mark.asyncio
async def test_constant_data_source_invalid_keys():
    data_source = ConstantDataSource()

    class FakeKey:
        name = "FAKE_KEY"

    fake_key = FakeKey()

    with pytest.raises(KeyError, match="Read operation for data_key FAKE_KEY not implemented"):
        await data_source.read_data(fake_key)  # type: ignore

    with pytest.raises(KeyError, match="Write operation for data_key"):
        await data_source.write_data(fake_key, 10.0)  # type: ignore

    with pytest.raises(KeyError, match="Write operation for data_key"):
        await data_source.write_data(ConstantDataSource.DataKeys.READ_VALUE, 10.0)
