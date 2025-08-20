# ALSA Volume Sensor Module

A Viam sensor module for monitoring and controlling ALSA (Advanced Linux Sound Architecture) audio devices on Linux systems. This module provides real-time volume monitoring and control capabilities for audio cards and devices.

## Model viam-soleng:alsa-volume:alsa-volume

The ALSA Volume Sensor allows you to:
- Monitor volume levels of all ALSA audio devices
- Set volume levels for specific audio cards
- Mute/unmute audio devices
- Play test tones to verify audio functionality
- Get detailed information about audio hardware

### Configuration

This sensor requires no configuration attributes as it automatically detects all available ALSA audio devices.

```json
{}
```

#### Attributes

This model has no configurable attributes as it automatically discovers audio devices.

### GetReadings

The sensor provides readings for all detected ALSA audio devices. Each device reading includes:

| Field | Type | Description |
|-------|------|-------------|
| `card` | string | ALSA card number |
| `card_name` | string | Name of the audio card |
| `device` | string | Device number within the card |
| `device_name` | string | Name of the device |
| `device_desc` | string | Device description |
| `volume_percent` | string | Current volume percentage (0-100) |
| `muted` | boolean | Mute status (true = muted, false = unmuted) |
| `control` | string | ALSA control name used for volume control |

#### Example GetReadings Response

```json
{
  "card_0_device_0": {
    "card": "0",
    "card_name": "PCH",
    "device": "0", 
    "device_name": "ALC892 Analog",
    "device_desc": "ALC892 Analog",
    "volume_percent": "75",
    "muted": false,
    "control": "Master"
  },
  "card_1_device_0": {
    "card": "1",
    "card_name": "UACDemoV10 [UACDemoV1.0]",
    "device": "0",
    "device_name": "USB Audio",
    "device_desc": "USB Audio",
    "volume_percent": "30",
    "muted": false,
    "control": "PCM"
  }
}
```

### DoCommand

The sensor supports several commands for controlling audio devices:

#### 1. Set Volume

Set the volume level for a specific audio card.

```json
{
  "command": "set_volume",
  "volume": 70,
  "card": 0
}
```

**Parameters:**
- `command`: Must be "set_volume"
- `volume`: Integer between 0-100 representing volume percentage
- `card`: Integer representing the ALSA card number

**Response:**
```json
{
  "success": true,
  "card": "0",
  "volume": 70,
  "control": "Master",
  "output": "amixer output..."
}
```

#### 2. Mute

Mute a specific audio card.

```json
{
  "command": "mute",
  "card": 0
}
```

**Parameters:**
- `command`: Must be "mute"
- `card`: Integer representing the ALSA card number

**Response:**
```json
{
  "success": true,
  "card": "0",
  "action": "mute",
  "control": "Master",
  "output": "amixer output..."
}
```

#### 3. Unmute

Unmute a specific audio card.

```json
{
  "command": "unmute",
  "card": 0
}
```

**Parameters:**
- `command`: Must be "unmute"
- `card`: Integer representing the ALSA card number

**Response:**
```json
{
  "success": true,
  "card": "0",
  "action": "unmute",
  "control": "Master",
  "output": "amixer output..."
}
```

#### 4. Toggle Mute

Toggle the mute state of a specific audio card.

```json
{
  "command": "toggle_mute",
  "card": 0
}
```

**Parameters:**
- `command`: Must be "toggle_mute"
- `card`: Integer representing the ALSA card number

**Response:**
```json
{
  "success": true,
  "card": "0",
  "action": "toggle",
  "control": "Master",
  "output": "amixer output..."
}
```

#### 5. Play Test Tone

Play a test tone on a specific audio card to verify audio functionality.

```json
{
  "command": "play_test",
  "card": 1,
  "device": 0,
  "channels": 2
}
```

**Parameters:**
- `command`: Must be "play_test"
- `card`: Integer representing the ALSA card number
- `device`: Integer representing the device number (optional, defaults to 0)
- `channels`: Integer representing the number of channels (optional, defaults to 2, range 1-8)

**Response:**
```json
{
  "success": true,
  "card": "1",
  "device": "0",
  "channels": 2,
  "output": "speaker-test output..."
}
```

### Error Handling

All commands return error responses when they fail:

```json
{
  "error": "Failed to set volume: Invalid card number",
  "card": "99",
  "volume": 70,
  "control": "Master"
}
```

Common error scenarios:
- Invalid card number
- Volume outside 0-100 range
- Missing required parameters
- ALSA command execution failures
- No working volume controls found

### System Requirements

- Linux system with ALSA support
- `aplay` command available (part of alsa-utils)
- `amixer` command available (part of alsa-utils)
- `speaker-test` command available (part of alsa-utils)
- Python 3.7+

### Installation

1. Install ALSA utilities:
   ```bash
   sudo apt-get install alsa-utils
   ```

2. Install the Viam module:
   ```bash
   pip install -e .
   ```

### Usage Examples

#### Monitor all audio devices:
```python
# Get readings from the sensor
readings = await sensor.get_readings()
for device_key, reading in readings.items():
    print(f"Device {device_key}: {reading['volume_percent']}% volume, muted: {reading['muted']}")
```

#### Set volume for card 0:
```python
# Set volume to 80%
await sensor.do_command({
    "command": "set_volume",
    "volume": 80,
    "card": 0
})
```

#### Mute card 1:
```python
# Mute audio card 1
await sensor.do_command({
    "command": "mute",
    "card": 1
})
```

#### Play test tone:
```python
# Play test tone on card 1
await sensor.do_command({
    "command": "play_test",
    "card": 1,
    "channels": 2
})
```

### Features

- **Automatic Device Discovery**: Automatically finds all ALSA audio devices
- **Smart Control Detection**: Intelligently discovers and uses appropriate volume controls
- **USB Audio Support**: Optimized for USB audio devices with enhanced control discovery
- **Robust Error Handling**: Comprehensive error reporting and fallback mechanisms
- **Boolean Mute Status**: Intuitive true/false mute status (true = muted, false = unmuted)
- **Test Tone Playback**: Built-in audio testing functionality

### Troubleshooting

1. **No devices found**: Ensure ALSA is properly configured and audio devices are connected
2. **Permission errors**: Run viam-server with appropriate permissions to access audio devices
3. **Command failures**: Check that `aplay`, `amixer`, and `speaker-test` commands are available in the system PATH
4. **Volume not changing**: Verify the correct card number and that the device supports volume control
5. **No working controls**: Check debug logs to see available controls and parsing attempts
6. **USB device issues**: USB audio devices may use different control names; the sensor will automatically discover them 