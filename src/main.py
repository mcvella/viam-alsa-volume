import asyncio
from viam.module.module import Module
try:
    from models.alsa_volume import AlsaVolume
except ModuleNotFoundError:
    # when running as local module with run.sh
    from .models.alsa_volume import AlsaVolume


if __name__ == '__main__':
    asyncio.run(Module.run_from_registry())
