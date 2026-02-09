# Captured Prusa Connect API Interactions

NOTE: This is mostly notes that I made as I went through API calls

## Overview

Captured API traffic from `connect.prusa3d.com` using Chrome DevTools

**Session ID**: `0b0481aa-b88b-40c2-95b1-66382628dfce` **Capture Time**:
2026-02-02

## Authentication

Authentication is handled via the `auth.access_token` cookie, which contains a
JWT.

**Cookie Name:** `auth.access_token` **Token Type:** Bearer (implied by usage,
passed as cookie)

### JWT Payload Analysis

Decoded payload findings:

- **Issuer/App (`app`)**: `connect`
- **Type (`type`)**: `access`
- **Connect ID (`connect_id`)**: `157235`
- **Subject (`sub`)**: `1530681`

## Captured Endpoints

### 1. Printer Queue

**Method:** `GET` **URL:** `/app/printers/{printer_uuid}/queue` **Query
Params:** `limit=1`, `offset=0`

**Response Structure:**

```json
{
  "planned_jobs": [],
  "pager": {
    "limit": 1,
    "offset": 0,
    "total": 0,
    "from": 1770090594
  }
}
```

**Method:** `POST` (Queue Job) **URL:** `/app/printers/{printer_uuid}/queue`
**Headers:**

- `Content-Type: application/json`

**Request Body Structure:**

```json
{
  "set_ready": true,
  "position": 0,
  "path": "/usb/filename.bgcode"
}
```

### 2. Invitations

**Method:** `GET` **URL:** `/app/invitations`

**Response Structure:**

```json
{
  "invitations": [],
  "refused": []
}
```

### 3. Jobs History

**Method:** `GET` **URL:** `/app/printers/{printer_uuid}/jobs` **Query Params:**
`limit`, `offset`, `state`

**Response Structure:** ...

### 3a. Job Details (Object Enumeration)

**Method:** `GET` **URL:** `/app/printers/{printer_uuid}/jobs/{job_id}`

**Response Structure (Printing/Finished Job with Cancellable Objects):**

```jsonc
{
  "id": 319,
  "state": "FIN_OK",
  "cancelable": {
    "objects": [
      {
        "id": 0,
        "name": "Object Name",
        "polygon": [[126.7, 87.5], "..."],
        "canceled": false
      }
    ]
  },
  "file": {
    "name": "filename.bgcode",
    "meta": {
      "objects_info": {
        "objects": [
          { "name": "Object Name", "polygon": ["..."] }
        ]
      }
    }
  }
}
```

*Note: The `id` in `cancelable.objects` corresponds to the `object_id` required
for the `CANCEL_OBJECT` command. This field may only be present for jobs where
object cancellation is applicable (e.g., active prints).*

**Method:** `GET` **URL:** `/app/printers/{printer_uuid}/jobs` **Query Params:**
`limit`, `offset`, `state` (e.g., `FIN_OK`, `FIN_ERROR`, `FIN_STOPPED`,
`UNKNOWN`)

**Response Structure:**

```json
{
  "jobs": [
    {
      "id": 1690023,
      "state": "FIN_OK",
      "progress": 100,
      "time_printing": 7562,
      "time_remaining": null,
      "mode": "MK4S",
      "source": "connect",
      "ts_started": 1769805961,
      "ts_ended": 1769813523,
      "files": [
        {
          "name": "corner-bracket_x2.bgcode",
          "path": "/usb/corner-bracket_x2.bgcode",
          "display_name": "corner-bracket_x2",
          "size": 42589,
          "m_time": 1769792040,
          "preview_url": "..."
        }
      ],
      "data": {
        "material": "PETG",
        "weight": 12.34,
        "cost": 0.5,
        "tool": 0,
        "layer_height": 0.2
      }
    }
  ],
  "pager": {
    "limit": 3,
    "offset": 0,
    "total": 5,
    "from": 1769805961,
    "to": 1770090594
  }
}
```

### 4. Printer Events

**Method:** `GET` **URL:** `/app/printers/{printer_uuid}/events` **Query
Params:** `event` (e.g., `STATE_CHANGED`, `VALUE_CHANGED`), `limit`

**Response Structure:**

```json
{
  "events": [
    {
      "server_time": 1770092716.366299,
      "event": "STATE_CHANGED",
      "source": "UNKNOWN",
      "transfer_id": 1036477693,
      "command": "SET_PRINTER_READY",
      "command_id": 1075307,
      "state": "READY",
      "created": 1770092716.34737
    }
  ],
  "pager": {
    "limit": 5,
    "offset": 0,
    "from": 1770006393,
    "to": 1770092794
  }
}
```

### 5. Team Uploads

**Method:** `GET` **URL:** `/app/users/teams/{team_id}/uploads` **Query
Params:** `state` (e.g., `UPLOADING`)

**Response Structure:**

```json
{
  "uploads": []
}
```

### 6. Download Queue

**Method:** `GET` **URL:** `/app/printers/{printer_uuid}/download-queue`

**Response Structure:**

```json
{
  "planned_jobs": [],
  "pager": {
    "limit": 1,
    "offset": 0,
    "total": 0,
    "from": 1770092795
  }
}
```

### 7. Files

**Method:** `GET` **URL:** `/app/printers/{printer_uuid}/files` **Status:**
Observed `304 Not Modified` **Inferred Structure:** Likely similar to file
objects in `jobs` response or a list of file metadata.

### 8. Cameras List

**Method:** `GET` **URL:** `/app/printers/{printer_uuid}/cameras`

**Response Structure:**

```json
{
  "cameras": [
    {
      "id": 414362,
      "name": "Buddy3D Camera",
      "config": {
        "name": "Buddy3D Camera",
        "path": "private",
        "model": "Buddy3D",
        "resolution": {
          "width": 1920,
          "height": 1080
        },
        "trigger_scheme": "THIRTY_SEC"
      },
      "capabilities": [
        "trigger_scheme"
      ],
      "features": [
        "SocketCom",
        "UploadInterval",
        "TimelapseEn",
        "GetSnapshot",
        "CameraName",
        "FwUpdate"
      ],
      "token": "...",
      "registered": true
    }
  ],
  "pager": {
    "limit": 20,
    "offset": 0,
    "total": 1
  }
}
```

### 9. Camera Snapshot

**Method:** `GET` **URL:** `/app/cameras/{camera_id}/snapshots/last` **Query
Params:** `printer_uuid` **Status:** Observed `304 Not Modified` **Note:**
Likely returns image binary or 304 if unchanged.

### 10. Server Version

**Method:** `GET` **URL:** `/version.json`

**Response Structure:**

```json
{
  "commit": "baef7db3",
  "version": "baef7db3",
  "date": "2026-02-02T11:49:56.846Z"
}
```

### 11. Printer Types

**Method:** `GET` **URL:** `/app/printer-types`

**Response Structure:**

```jsonc
{
  "printer_types": [
    {
      "id": "1.2.5",
      "type": 1,
      "version": 2,
      "subversion": 5,
      "name": "Original Prusa i3 MK2.5",
      "parameters": {
        "extrusion": {"max": 100, "min": -10, "default": 10},
        "print_flow": {"max": 999, "min": 10, "default": 100},
        "temp_nozzle": {"max": 295, "min": 0}
      },
      "fw_device_type_id": "1.2.5",
      "support": {"stable": "0.8.1", "unsupported": "0.7.0"}
    },
    {
      "id": "8.1.0",
      "type": 8,
      "version": 1,
      "subversion": 0,
      "name": "Prusa CORE One L",
      "parameters": { "...": "..." },
      "fw_device_type_id": "8.1.0",
      "support": {"stable": "6.5.2"}
    }
  ]
}
```

### 12. Supported Commands

**Method:** `GET` **URL:** `/app/printers/{printer_uuid}/supported-commands`

**Response Structure:**

```json
{
  "commands": [
    {
      "command": "SEND_GCODE",
      "args": [
        "gcode"
      ],
      "template": "M997 {path}"
    },
    {
      "command": "PAUSE_PRINT",
      "template": "M25"
    },
    {
      "command": "CANCEL_OBJECT",
      "args": [
        "id"
      ],
      "template": "M486 P{id}"
    },
    {
      "command": "FLASH",
      "args": [
        "path"
      ],
      "template": "M997 {path}"
    }
  ]
}
```

### 12. Execute Command (Sync)

**Method:** `POST` **URL:** `/app/printers/{printer_uuid}/commands/sync`
**Headers:**

- `Content-Type: application/json`

**Request Body Structure:**

```json
{
  "command": "COMMAND_NAME",
  "kwargs": {
    "arg_name": "arg_value"
  }
}
```

**Captured & Inferred Patterns:**

| Command           | Payload Structure (Inferred from FLASH/Metadata)                    |
| :---------------- | :------------------------------------------------------------------ |
| **FLASH**         | `{"command":"FLASH", "kwargs":{"path":"/usb/MK4~640B.BBF"}}`        |
| **CANCEL_OBJECT** | `{"command":"CANCEL_OBJECT", "kwargs":{"object_id": 0}}` (verified) |
| **PAUSE_PRINT**   | `{"command":"PAUSE_PRINT", "kwargs":{}}` (verified)                 |
| **STOP_PRINT**    | `{"command":"STOP_PRINT", "kwargs":{}}` (verified)                  |

**Response Structure (Verified for STOP_PRINT):**

```json
{
  "command": {
    "id": 1075350,
    "state": "CREATED",
    "command": "STOP_PRINT",
    "received": 1770096073,
    "source": "CONNECT_USER",
    "kwargs": {}
  },
  "event": {
    "event": "FINISHED",
    "command": "STOP_PRINT",
    "state": "PRINTING",
    "created": 1770096074.410354
  }
}
```

| **MOVE** | `{"command":"MOVE", "kwargs":{"feedrate":3000, "x":131, "y":134}}`
(verified) |

**Response Structure (Verified for PAUSE_PRINT):**

```json
{
  "command": {
    "id": 1075348,
    "state": "CREATED",
    "command": "PAUSE_PRINT",
    "received": 1770095844,
    "source": "CONNECT_USER",
    "kwargs": {}
  },
  "event": {
    "event": "FINISHED",
    "command": "PAUSE_PRINT",
    "state": "PRINTING",
    "created": 1770095845.330407
  }
}
```

### 13. Storages

**Method:** `GET` **URL:** `/app/printers/{printer_uuid}/storages`

### 14. Printer Files

**Method:** `GET` **URL:** `/app/printers/{printer_uuid}/files`

### 15. App Config

**Method:** `GET` **URL:** `/app/config`

### 16. Notifications

**Method:** `GET` **URL:** `/app/notifications/unseen`

**Response Structure:**

```json
{
  "unseen": 1
}
```

*Note: `GET /app/notifications` (without `unseen`) likely returns the full list
of notifications.*

### 17. Update Job Reason (PATCH)

**Method:** `PATCH` **URL:** `/app/printers/{printer_uuid}/jobs/{job_id}`
**Description:** Updates the job with a reason for failure/cancellation. Usually
sent after stopping a print.

**Request Body:**

```json
{
  "reason": {
    "tag": [
      "CLOGGED_NOZZLE",
      "NON_ADHERENT_BED",
      "UNDER_EXTRUSION",
      "OVER_EXTRUSION",
      "STRINGING_OR_OOZING",
      "GAPS_IN_THIN_WALLS",
      "OVERHEATING",
      "LAYER_SHIFTING",
      "SPAGHETTI_MONSTER",
      "LAYER_SEPARATION",
      "WARPING",
      "POOR_BRIDGING",
      "OTHER"
    ],
    "other": "optional comment"
  }
}
```

**Notes:** The `tag` field is an array of strings (Enums). The example above
shows all possible values captured. **Response:** Empty (verified by user).

## Observations

- The API uses standard REST patterns.
- Responses are JSON.
- Command execution allows dynamic arguments via `kwargs`.
