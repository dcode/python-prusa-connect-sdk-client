# Unoriginal Prusa Connect Python Client

[![PyPI version](https://badge.fury.io/py/prusa-connect-sdk-client.svg)](https://badge.fury.io/py/prusa-connect-sdk-client)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python Versions](https://img.shields.io/pypi/pyversions/prusa-connect-sdk-client.svg)](https://pypi.org/project/prusa-connect-sdk-client/)

Control your Prusa 3D printers programmatically with Python. This library
provides a frictionless, strongly-typed interface for the Prusa Connect API.

> [!WARNING] **A Note on Unoriginal-ness**
>
> This SDK is not an officially supported or endorsed product of Prusa Research.
> It is developed and maintained by an independent developer and is not
> affiliated with Prusa Research. See [Motivation & Design](#motivation-design)
> for more information.

**Features:**

- **Zero-Config Authentication:** Log in once via CLI, use everywhere in Python.
- **Strong Typing:** Full Pydantic models for printers, jobs, cameras, and
  files.
- **Batteries Included:** Retries, timeouts, and error handling out of the box.
- **CLI Tool:** Managing printers from the terminal.

## Installation

Install the package with the CLI tools (recommended for easiest setup):

```bash
pip install "prusa-connect-sdk-client[cli]"
```

Or install the lightweight library only:

```bash
pip install prusa-connect-sdk-client
```

## Motivation & Design

My motivation to create this library is to provide a frictionless,
strongly-typed interface for the Prusa Connect API. I want to be able to monitor
and control my Prusa 3D printers programmatically with Python. I love building
tools, which has led to me loving my Prusa 3D printers.

It is my goal that this library has the same level of quality engineering and
"feel" as the products Prusa Research produces. That goal drove the decisions on
library layout (e.g. `prusa.connect.client` namespace) and the naming of the
PyPI package itself.

That said, if anyone from Prusa Research wishes to take over development of this
library, I would be happy to hand it over (and keep contributing, if desired).
Alternatively, I can keep this project going as a community-driven project in my
spare time. If you're from Prusa Research and wish to support this work, I'd
gladly accept Prusameters towards a new Core-generation printer. 😉

My Printables Profile: :simple-printables:
[dcode](https://www.printables.com/@dcode_3006269)
