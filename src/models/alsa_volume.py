from typing import (Any, ClassVar, Dict, Final, List, Mapping, Optional,
                    Sequence, Tuple)
import asyncio
import subprocess
import re

from typing_extensions import Self
from viam.components.sensor import *
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import Geometry, ResourceName
from viam.resource.base import ResourceBase
from viam.resource.easy_resource import EasyResource
from viam.resource.types import Model, ModelFamily
from viam.utils import SensorReading, ValueTypes


class AlsaVolume(Sensor, EasyResource):
    # To enable debug-level logging, either run viam-server with the --debug option,
    # or configure your resource/machine to display debug logs.
    MODEL: ClassVar[Model] = Model(ModelFamily("mcvella", "alsa-volume"), "alsa-volume")

    @classmethod
    def new(
        cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ) -> Self:
        """This method creates a new instance of this Sensor component.
        The default implementation sets the name from the `config` parameter and then calls `reconfigure`.

        Args:
            config (ComponentConfig): The configuration for this resource
            dependencies (Mapping[ResourceName, ResourceBase]): The dependencies (both required and optional)

        Returns:
            Self: The resource
        """
        return super().new(config, dependencies)

    @classmethod
    def validate_config(
        cls, config: ComponentConfig
    ) -> Tuple[Sequence[str], Sequence[str]]:
        """This method allows you to validate the configuration object received from the machine,
        as well as to return any required dependencies or optional dependencies based on that `config`.

        Args:
            config (ComponentConfig): The configuration for this resource

        Returns:
            Tuple[Sequence[str], Sequence[str]]: A tuple where the
                first element is a list of required dependencies and the
                second element is a list of optional dependencies
        """
        return [], []

    def reconfigure(
        self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ):
        """This method allows you to dynamically update your service when it receives a new `config` object.

        Args:
            config (ComponentConfig): The new configuration
            dependencies (Mapping[ResourceName, ResourceBase]): Any dependencies (both required and optional)
        """
        return super().reconfigure(config, dependencies)

    async def _get_audio_devices(self) -> List[Dict[str, str]]:
        """Get list of audio devices using aplay -l command."""
        try:
            result = await asyncio.create_subprocess_exec(
                'aplay', '-l',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                self.logger.error(f"aplay -l failed: {stderr.decode()}")
                return []
            
            devices = []
            lines = stdout.decode().split('\n')
            
            for line in lines:
                # Parse lines like "card 0: PCH [HDA Intel PCH], device 0: ALC892 Analog [ALC892 Analog]"
                match = re.match(r'card (\d+): ([^,]+), device (\d+): ([^\[]+)\[([^\]]+)\]', line)
                if match:
                    card_num, card_name, device_num, device_name, device_desc = match.groups()
                    devices.append({
                        'card': card_num,
                        'card_name': card_name.strip(),
                        'device': device_num,
                        'device_name': device_name.strip(),
                        'device_desc': device_desc.strip()
                    })
            
            return devices
        except Exception as e:
            self.logger.error(f"Error getting audio devices: {e}")
            return []

    async def _get_device_volume(self, card_num: str) -> Dict[str, Any]:
        """Get volume information for a specific card using amixer -c command."""
        try:
            result = await asyncio.create_subprocess_exec(
                'amixer', '-c', card_num, 'get', 'Master',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                self.logger.warning(f"amixer -c {card_num} get Master failed: {stderr.decode()}")
                return {'volume': 'N/A', 'muted': 'N/A'}
            
            output = stdout.decode()
            
            # Parse volume percentage
            volume_match = re.search(r'\[(\d+)%\]', output)
            volume = volume_match.group(1) if volume_match else 'N/A'
            
            # Parse mute status
            muted_match = re.search(r'\[(on|off)\]', output)
            muted = muted_match.group(1) if muted_match else 'N/A'
            
            return {
                'volume': volume,
                'muted': muted
            }
        except Exception as e:
            self.logger.error(f"Error getting volume for card {card_num}: {e}")
            return {'volume': 'N/A', 'muted': 'N/A'}

    async def get_readings(
        self,
        *,
        extra: Optional[Mapping[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Mapping[str, SensorReading]:
        """Get readings for all audio devices and their volume levels."""
        try:
            devices = await self._get_audio_devices()
            readings = {}
            
            for device in devices:
                card_num = device['card']
                volume_info = await self._get_device_volume(card_num)
                
                device_key = f"card_{card_num}_device_{device['device']}"
                readings[device_key] = SensorReading(
                    value={
                        'card': card_num,
                        'card_name': device['card_name'],
                        'device': device['device'],
                        'device_name': device['device_name'],
                        'device_desc': device['device_desc'],
                        'volume_percent': volume_info['volume'],
                        'muted': volume_info['muted']
                    }
                )
            
            if not readings:
                readings['no_devices'] = SensorReading(
                    value={'message': 'No audio devices found'}
                )
            
            return readings
            
        except Exception as e:
            self.logger.error(f"Error in get_readings: {e}")
            return {
                'error': SensorReading(
                    value={'error': str(e)}
                )
            }

    async def do_command(
        self,
        command: Mapping[str, ValueTypes],
        *,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Mapping[str, ValueTypes]:
        """Handle commands for the ALSA volume sensor.
        
        Supported commands:
        - set_volume: Set volume for a specific card
          Parameters:
            - command: "set_volume"
            - volume: number between 0-100
            - card: card number
        - mute: Mute a specific card
          Parameters:
            - command: "mute"
            - card: card number
        - unmute: Unmute a specific card
          Parameters:
            - command: "unmute"
            - card: card number
        - toggle_mute: Toggle mute state for a specific card
          Parameters:
            - command: "toggle_mute"
            - card: card number
        """
        try:
            cmd_type = command.get("command")
            
            if cmd_type == "set_volume":
                return await self._set_volume(command)
            elif cmd_type == "mute":
                return await self._set_mute_state(command, "mute")
            elif cmd_type == "unmute":
                return await self._set_mute_state(command, "unmute")
            elif cmd_type == "toggle_mute":
                return await self._set_mute_state(command, "toggle")
            else:
                return {
                    "error": f"Unknown command: {cmd_type}. Supported commands: set_volume, mute, unmute, toggle_mute"
                }
                
        except Exception as e:
            self.logger.error(f"Error in do_command: {e}")
            return {"error": str(e)}

    async def _set_volume(self, command: Mapping[str, ValueTypes]) -> Mapping[str, ValueTypes]:
        """Set volume for a specific card using amixer command."""
        try:
            # Extract parameters
            volume = command.get("volume")
            card = command.get("card")
            
            # Validate parameters
            if volume is None:
                return {"error": "volume parameter is required"}
            if card is None:
                return {"error": "card parameter is required"}
            
            # Convert to appropriate types
            try:
                volume_int = int(volume)
                card_str = str(card)
            except (ValueError, TypeError):
                return {"error": "volume must be a number and card must be a valid card number"}
            
            # Validate volume range
            if not 0 <= volume_int <= 100:
                return {"error": "volume must be between 0 and 100"}
            
            # Execute amixer command
            result = await asyncio.create_subprocess_exec(
                'amixer', '-c', card_str, 'set', 'PCM', f'{volume_int}%',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                error_msg = stderr.decode().strip()
                self.logger.error(f"amixer command failed: {error_msg}")
                return {
                    "error": f"Failed to set volume: {error_msg}",
                    "card": card_str,
                    "volume": volume_int
                }
            
            output = stdout.decode().strip()
            self.logger.info(f"Successfully set volume to {volume_int}% for card {card_str}")
            
            return {
                "success": True,
                "card": card_str,
                "volume": volume_int,
                "output": output
            }
            
        except Exception as e:
            self.logger.error(f"Error setting volume: {e}")
            return {"error": str(e)}

    async def _set_mute_state(self, command: Mapping[str, ValueTypes], mute_action: str) -> Mapping[str, ValueTypes]:
        """Set mute state for a specific card using amixer command."""
        try:
            # Extract parameters
            card = command.get("card")
            
            # Validate parameters
            if card is None:
                return {"error": "card parameter is required"}
            
            # Convert to appropriate type
            try:
                card_str = str(card)
            except (ValueError, TypeError):
                return {"error": "card must be a valid card number"}
            
            # Execute amixer command
            result = await asyncio.create_subprocess_exec(
                'amixer', '-c', card_str, 'set', 'PCM', mute_action,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                error_msg = stderr.decode().strip()
                self.logger.error(f"amixer mute command failed: {error_msg}")
                return {
                    "error": f"Failed to {mute_action}: {error_msg}",
                    "card": card_str,
                    "action": mute_action
                }
            
            output = stdout.decode().strip()
            self.logger.info(f"Successfully {mute_action}d card {card_str}")
            
            return {
                "success": True,
                "card": card_str,
                "action": mute_action,
                "output": output
            }
            
        except Exception as e:
            self.logger.error(f"Error setting mute state: {e}")
            return {"error": str(e)}

    async def get_geometries(
        self, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None
    ) -> List[Geometry]:
        self.logger.error("`get_geometries` is not implemented")
        raise NotImplementedError()

