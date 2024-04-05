# `penv`: `venv`-based Python Portable Environment

![GitHub top language](https://img.shields.io/github/languages/top/hmasdev/penv)
![GitHub tag (latest SemVer)](https://img.shields.io/github/v/tag/hmasdev/penv?sort=semver)
![GitHub](https://img.shields.io/github/license/hmasdev/penv)
![GitHub last commit](https://img.shields.io/github/last-commit/hmasdev/penv)

![Scheduled Test](https://github.com/hmasdev/penv/actions/workflows/tests-on-schedule.yaml/badge.svg)

`penv` is a Python package that provides a portable environment for Python projects.
It is based on the built-in `venv` module, which is available in Python 3.9 and later.
`penv` is designed to be a lightweight alternative to more complex tools like `virtualenv` and `conda`.

## Requirements

- Windows
- Python >= 3.9

## Installation

```bash
pip install git+https://github.com/hmasdev/penv
```

## Usage

Almost same as `venv` module.

```bash
python -m penv .penv
```

Here is the help of `penv` command.

```bash
 $ python -m penv --help
usage: penv [-h] [--clear] [--upgrade] [--without-pip] [--prompt PROMPT] [--python-version PYTHON_VERSION] [--platform-arch PLATFORM_ARCH] [--cache-dir CACHE_DIR] [--log-level LOG_LEVEL] ENV_DIR [ENV_DIR ...]

Creates virtual Python environments in one or more target directories.

positional arguments:
  ENV_DIR               A directory to create the environment in.

options:
  -h, --help            show this help message and exit
  --clear               Delete the contents of the environment directory if it already exists, before environment creation.
  --upgrade             Upgrade the environment directory to use this version of Python, assuming Python has been upgraded in-place.
  --without-pip         Skips installing or upgrading pip in the virtual environment (pip is bootstrapped by default)
  --prompt PROMPT       Provides an alternative prompt prefix for this environment.
  --python-version PYTHON_VERSION
                        The version of Python to use
  --platform-arch PLATFORM_ARCH
                        The platform architecture to use
  --cache-dir CACHE_DIR
                        The directory to cache the embeddable python
  --log-level LOG_LEVEL
                        The logging level

Once an environment has been created, you may wish to activate it, e.g. by sourcing an activate script in its bin directory.
```

## Contribution

1. Fork this repository
   - [https://github.com/hmasdev/penv/fork](https://github.com/hmasdev/penv/fork)

2. Clone your forked repository

   ```bash
   git clone https://github.com/{YOUR_GITHUB_ID}/penv
   cd penv
   ```

3. Setup the development environment

   ```bash
   python -m venv .venv
   .venv\\Scripts\\activate.bat
   pip install -e .[dev]
   ```

4. Create a new branch like `feature/add-something`

   ```bash
   git checkout -b {BRANCH_NAME}
   ```

5. Make your changes and add tests

6. Commit your changes

   ```bash
   git add .
   git commit -m "Add something"
   ```

7. Push your changes to your forked repository

   ```bash
   git push -u origin {BRANCH_NAME}
   ```

8. Create a pull request
   - [https://github.com/hmasdev/penv/compare](https://github.com/hmasdev/penv/compare)

## License

[MIT](./LICENSE)

## Author

- [hmasdev](https://github.com/hmasdev)
