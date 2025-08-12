# ALSA Volume Sensor Module

A Viam sensor module for monitoring and controlling ALSA (Advanced Linux Sound Architecture) audio devices on Linux systems. This module provides real-time volume monitoring and control capabilities for audio cards and devices.

## Model mcvella:alsa-volume:alsa-volume

The ALSA Volume Sensor allows you to:
- Monitor volume levels of all ALSA audio devices
- Set volume levels for specific audio cards
- Mute/unmute audio devices
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
| `muted` | string | Mute status ("on" for muted, "off" for unmuted) |

#### Example GetReadings Response

```json
{
  "card_0_device_0": {
    "value": {
      "card": "0",
      "card_name": "PCH",
      "device": "0", 
      "device_name": "ALC892 Analog",
      "device_desc": "ALC892 Analog",
      "volume_percent": "75",
      "muted": "off"
    }
  },
  "card_1_device_0": {
    "value": {
      "card": "1",
      "card_name": "USB Audio",
      "device": "0",
      "device_name": "USB Audio",
      "device_desc": "USB Audio",
      "volume_percent": "50",
      "muted": "on"
    }
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
  "output": "amixer output..."
}
```

### Error Handling

All commands return error responses when they fail:

```json
{
  "error": "Failed to set volume: Invalid card number",
  "card": "99",
  "volume": 70
}
```

Common error scenarios:
- Invalid card number
- Volume outside 0-100 range
- Missing required parameters
- ALSA command execution failures

### System Requirements

- Linux system with ALSA support
- `aplay` command available (part of alsa-utils)
- `amixer` command available (part of alsa-utils)
- Python 3.7+ 