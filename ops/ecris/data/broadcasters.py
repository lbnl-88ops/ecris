from logging import getLogger

_log = getLogger(__name__)

async def log_data(data, value) -> None:
    _log.info(f'{value}={data[value]}')
    