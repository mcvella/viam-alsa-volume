from typing import (Any, ClassVar, Dict, Final, List, Mapping, Optional,
                    Sequence, Tuple)
import asyncio
import subprocess
import re
import json

from viam.components.sensor import Sensor
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
    ) -> "AlsaVolume":
        """This method creates a new instance of this Sensor component.
        The default implementation sets the name from the `config` parameter and then calls `reconfigure`.

        Args:
            config (ComponentConfig): The configuration for this resource
            dependencies (Mapping[ResourceName, ResourceBase]): The dependencies (both required and optional)

        Returns:
            AlsaVolume: The resource
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

    async def _get_available_controls(self, card_num: str) -> List[str]:
        """Get list of available volume controls for a card."""
        try:
            result = await asyncio.create_subprocess_exec(
                'amixer', '-c', card_num, 'controls',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                self.logger.debug(f"amixer -c {card_num} controls failed: {stderr.decode()}")
                return []
            
            controls = []
            lines = stdout.decode().split('\n')
            for line in lines:
                line = line.strip()
                if line:
                    # Extract the control name from the numid format
                    # Format: "numid=2,iface=MIXER,name='PCM Playback Switch'"
                    name_match = re.search(r"name='([^']+)'", line)
                    if name_match:
                        control_name = name_match.group(1)
                        controls.append(control_name)
                    else:
                        # If no name found, use the whole line
                        controls.append(line)
            
            self.logger.info(f"Found controls for card {card_num}: {controls}")
            return controls
        except Exception as e:
            self.logger.debug(f"Error getting controls for card {card_num}: {e}")
            return []

    async def _get_device_volume(self, card_num: str) -> Dict[str, Any]:
        """Get volume information for a specific card using amixer -c command."""
        # Common volume control names to try
        control_names = ['Master', 'PCM', 'Speaker', 'Headphone', 'Line Out', 'Front', 'Rear', 'USB', 'Playback Volume']
        
        # First try to get available controls
        available_controls = await self._get_available_controls(card_num)
        if available_controls:
            self.logger.debug(f"Available controls for card {card_num}: {available_controls}")
            # Filter to only volume controls - be more permissive for USB devices
            volume_controls = []
            for control in available_controls:
                # Check if it's a volume control by looking for common patterns
                if any(name in control for name in control_names) or 'volume' in control.lower() or 'playback' in control.lower():
                    volume_controls.append(control)
            
            if volume_controls:
                control_names = volume_controls[:5]  # Try first 5 available controls
                self.logger.debug(f"Trying volume controls for card {card_num}: {control_names}")
            else:
                # If no obvious volume controls, try all available controls
                control_names = available_controls[:3]
                self.logger.debug(f"No obvious volume controls found, trying all controls for card {card_num}: {control_names}")
        
        for control_name in control_names:
            try:
                self.logger.info(f"Trying control '{control_name}' on card {card_num}")
                
                # Try different ways to specify the control
                control_variants = [
                    control_name,  # Try the full name first
                    control_name.split()[0],  # Try just the first word (e.g., "PCM" from "PCM Playback Volume")
                ]
                
                for variant in control_variants:
                    try:
                        result = await asyncio.create_subprocess_exec(
                            'amixer', '-c', card_num, 'get', variant,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        stdout, stderr = await result.communicate()
                        
                        if result.returncode == 0:
                            output = stdout.decode()
                            self.logger.info(f"amixer output for control '{variant}' on card {card_num}: {output}")
                            
                            # Parse the new format: "Front Left: Playback 44 [30%] [-20.16dB] [on]"
                            # Look for lines with volume percentage and mute status
                            volume_match = re.search(r'\[(\d+)%\]', output)
                            muted_match = re.search(r'\[(on|off)\]', output)
                            
                            self.logger.info(f"Volume match: {volume_match}, Mute match: {muted_match}")
                            
                            if volume_match and muted_match:
                                volume = volume_match.group(1)
                                muted_status = muted_match.group(1)
                                
                                # In ALSA, 'on' means unmuted (sound plays), 'off' means muted (no sound)
                                # Convert to boolean: true = muted, false = unmuted
                                muted = muted_status == 'off'
                                
                                self.logger.info(f"Found working control '{variant}' for card {card_num}: volume={volume}%, muted={muted} (ALSA status: {muted_status})")
                                
                                return {
                                    'volume': volume,
                                    'muted': muted,
                                    'control': control_name
                                }
                            else:
                                self.logger.debug(f"Could not parse volume/mute from control {variant} on card {card_num}")
                        else:
                            error_msg = stderr.decode().strip()
                            self.logger.debug(f"Control {variant} failed on card {card_num}: {error_msg}")
                            
                    except Exception as e:
                        self.logger.debug(f"Error trying control variant {variant} on card {card_num}: {e}")
                        continue
                        
            except Exception as e:
                self.logger.warning(f"Error trying control {control_name} on card {card_num}: {e}")
                continue
        
        # If no controls work, try to get any available control as fallback
        if available_controls:
            for control in available_controls[:3]:  # Try first 3 available controls
                try:
                    self.logger.info(f"Trying fallback control '{control}' on card {card_num}")
                    
                    # Try different ways to specify the control
                    control_variants = [
                        control,  # Try the full name first
                        control.split()[0],  # Try just the first word
                    ]
                    
                    for variant in control_variants:
                        try:
                            result = await asyncio.create_subprocess_exec(
                                'amixer', '-c', card_num, 'get', variant,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE
                            )
                            stdout, stderr = await result.communicate()
                            
                            if result.returncode == 0:
                                output = stdout.decode()
                                self.logger.info(f"Fallback amixer output for control '{variant}' on card {card_num}: {output}")
                                
                                # Parse the new format: "Front Left: Playback 44 [30%] [-20.16dB] [on]"
                                volume_match = re.search(r'\[(\d+)%\]', output)
                                muted_match = re.search(r'\[(on|off)\]', output)
                                
                                self.logger.info(f"Fallback - Volume match: {volume_match}, Mute match: {muted_match}")
                                
                                if volume_match and muted_match:
                                    volume = volume_match.group(1)
                                    muted_status = muted_match.group(1)
                                    
                                    # In ALSA, 'on' means unmuted (sound plays), 'off' means muted (no sound)
                                    # Convert to boolean: true = muted, false = unmuted
                                    muted = muted_status == 'off'
                                    
                                    self.logger.info(f"Using fallback control '{variant}' for card {card_num}: volume={volume}%, muted={muted} (ALSA status: {muted_status})")
                                    
                                    return {
                                        'volume': volume,
                                        'muted': muted,
                                        'control': control
                                    }
                            
                        except Exception as e:
                            self.logger.debug(f"Error trying fallback control variant {variant} on card {card_num}: {e}")
                            continue
                        
                except Exception as e:
                    self.logger.warning(f"Error trying fallback control {control} on card {card_num}: {e}")
                    continue
        
        # If no controls work, return N/A values
        self.logger.warning(f"No working volume controls found for card {card_num}. Available controls: {available_controls}")
        return {'volume': 'N/A', 'muted': 'N/A', 'control': 'N/A'}

    async def get_readings(
        self,
        *,
        extra: Optional[Mapping[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Mapping[str, Any]:
        """Get readings for all audio devices and their volume levels."""
        try:
            devices = await self._get_audio_devices()
            readings = {}
            
            for device in devices:
                card_num = device['card']
                volume_info = await self._get_device_volume(card_num)
                
                device_key = f"card_{card_num}_device_{device['device']}"
                
                # Create comprehensive device data
                device_data = {
                    'card': card_num,
                    'card_name': device['card_name'],
                    'device': device['device'],
                    'device_name': device['device_name'],
                    'device_desc': device['device_desc'],
                    'volume_percent': volume_info['volume'],
                    'muted': volume_info['muted'],
                    'control': volume_info['control']
                }
                
                readings[device_key] = device_data
            
            if not readings:
                readings['no_devices'] = {'message': 'No audio devices found'}
            
            return readings
            
        except Exception as e:
            self.logger.error(f"Error in get_readings: {e}")
            return {
                'error': {'error': str(e)}
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
        - play_test: Play a test tone on a specific card
          Parameters:
            - command: "play_test"
            - card: card number
            - device: device number (optional, defaults to 0)
            - channels: number of channels (optional, defaults to 2)
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
            elif cmd_type == "play_test":
                return await self._play_test_tone(command)
            else:
                return {
                    "error": f"Unknown command: {cmd_type}. Supported commands: set_volume, mute, unmute, toggle_mute, play_test"
                }
                
        except Exception as e:
            self.logger.error(f"Error in do_command: {e}")
            return {"error": str(e)}

    async def _get_working_control(self, card_num: str) -> str:
        """Get a working volume control for a card."""
        # Common volume control names to try
        control_names = ['Master', 'PCM', 'Speaker', 'Headphone', 'Line Out']
        
        # First try to get available controls
        available_controls = await self._get_available_controls(card_num)
        if available_controls:
            # Filter to only volume controls
            volume_controls = [c for c in available_controls if any(name in c for name in control_names)]
            if volume_controls:
                control_names = volume_controls[:3]  # Try first 3 available controls
        
        for control_name in control_names:
            try:
                result = await asyncio.create_subprocess_exec(
                    'amixer', '-c', card_num, 'get', control_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()
                
                if result.returncode == 0:
                    return control_name
                    
            except Exception as e:
                self.logger.debug(f"Error trying control {control_name} on card {card_num}: {e}")
                continue
        
        # Default to PCM if no controls work
        return 'PCM'

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
            
            # Convert to appropriate types - ensure integers, not floats
            try:
                volume_int = int(float(volume))  # Handle both int and float inputs
                card_int = int(float(card))  # Handle both int and float inputs
            except (ValueError, TypeError):
                return {"error": "volume must be a number and card must be a valid card number"}
            
            # Validate volume range
            if not 0 <= volume_int <= 100:
                return {"error": "volume must be between 0 and 100"}
            
            # Get working control for this card
            control_name = await self._get_working_control(str(card_int))
            
            # Execute amixer command
            result = await asyncio.create_subprocess_exec(
                'amixer', '-c', str(card_int), 'set', control_name, f'{volume_int}%',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                error_msg = stderr.decode().strip()
                self.logger.error(f"amixer command failed: {error_msg}")
                return {
                    "error": f"Failed to set volume: {error_msg}",
                    "card": card_int,
                    "volume": volume_int,
                    "control": control_name
                }
            
            output = stdout.decode().strip()
            self.logger.info(f"Successfully set volume to {volume_int}% for card {card_int} using control {control_name}")
            
            return {
                "success": True,
                "card": card_int,
                "volume": volume_int,
                "control": control_name,
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
            
            # Convert to appropriate type - ensure integer, not float
            try:
                card_int = int(float(card))  # Handle both int and float inputs
            except (ValueError, TypeError):
                return {"error": "card must be a valid card number"}
            
            # Get working control for this card
            control_name = await self._get_working_control(str(card_int))
            
            # Execute amixer command
            result = await asyncio.create_subprocess_exec(
                'amixer', '-c', str(card_int), 'set', control_name, mute_action,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                error_msg = stderr.decode().strip()
                self.logger.error(f"amixer mute command failed: {error_msg}")
                return {
                    "error": f"Failed to {mute_action}: {error_msg}",
                    "card": card_int,
                    "action": mute_action,
                    "control": control_name
                }
            
            output = stdout.decode().strip()
            self.logger.info(f"Successfully {mute_action}d card {card_int} using control {control_name}")
            
            return {
                "success": True,
                "card": card_int,
                "action": mute_action,
                "control": control_name,
                "output": output
            }
            
        except Exception as e:
            self.logger.error(f"Error setting mute state: {e}")
            return {"error": str(e)}

    async def _play_test_tone(self, command: Mapping[str, ValueTypes]) -> Mapping[str, ValueTypes]:
        """Play a test tone using speaker-test command."""
        try:
            # Extract parameters
            card = command.get("card")
            device = command.get("device", 0)  # Default to device 0
            channels = command.get("channels", 2)  # Default to 2 channels
            
            # Validate parameters
            if card is None:
                return {"error": "card parameter is required"}
            
            # Convert to appropriate types - ensure integers, not floats
            try:
                card_int = int(float(card))  # Handle both int and float inputs
                device_int = int(float(device))  # Handle both int and float inputs
                channels_int = int(float(channels))  # Handle both int and float inputs
            except (ValueError, TypeError):
                return {"error": "card, device, and channels must be valid numbers"}
            
            # Validate channels
            if channels_int < 1 or channels_int > 8:
                return {"error": "channels must be between 1 and 8"}
            
            # Execute speaker-test command with integer values
            result = await asyncio.create_subprocess_exec(
                'speaker-test', '-D', f'hw:{card_int},{device_int}', '-c', str(channels_int), '-t', 'wav', '-l', '1',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                error_msg = stderr.decode().strip()
                self.logger.error(f"speaker-test command failed: {error_msg}")
                return {
                    "error": f"Failed to play test tone: {error_msg}",
                    "card": card_int,
                    "device": device_int,
                    "channels": channels_int
                }
            
            output = stdout.decode().strip()
            self.logger.info(f"Successfully played test tone on card {card_int}, device {device_int}, {channels_int} channels")
            
            return {
                "success": True,
                "card": card_int,
                "device": device_int,
                "channels": channels_int,
                "output": output
            }
            
        except Exception as e:
            self.logger.error(f"Error playing test tone: {e}")
            return {"error": str(e)}

    async def get_geometries(
        self, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None
    ) -> List[Geometry]:
        self.logger.error("`get_geometries` is not implemented")
        raise NotImplementedError()

