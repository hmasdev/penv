import logging
import os
import pytest
import shutil
import subprocess
from typing import Generator, Optional, Tuple
from types import SimpleNamespace
from penv import EmbeddableEnvBuilder, main


TEMP_DIR: str = 'temp_dir'
logger: logging.Logger = logging.getLogger(__name__)


@pytest.fixture(scope='function')
def dir_removed_after_test(dir_path: str = TEMP_DIR) -> Generator[str, None, None]:
    try:
        yield dir_path
    finally:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)


@pytest.fixture(scope='function')
def mock_embed_python_zip(
    python_version: str = '3.8.5',
    platform_arch: str = 'amd64',
) -> Generator[Tuple[str, str, str], None, None]:
    try:
        # preparation
        dir_path: str = f'python-{python_version}-embed-{platform_arch}'
        zip_path: str = f'{dir_path}.zip'
        short_version: str = ''.join(python_version.split(".")[:-1])
        # create
        os.makedirs(dir_path)
        with open(os.path.join(dir_path, f'python{short_version}._pth'), 'w') as f:
            f.write('#import site\n')
        with open(os.path.join(dir_path, 'activate.bat'), 'w') as f:
            f.write('set VIRTUAL_ENV=C:\\Tools\\env\\\n')
            f.write('set PATH=%VIRTUAL_ENV%\\;%PATH%\n')
        with open(os.path.join(dir_path, 'activate.ps1'), 'w') as f:
            f.write('echo activate\n')
        with open(os.path.join(dir_path, 'activate'), 'w') as f:
            f.write('VIRTUAL_ENV=C:\\Tools\\env\\\n')
        shutil.make_archive(dir_path, 'zip', dir_path)
        # yield
        yield python_version, platform_arch, dir_path
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)


@pytest.mark.parametrize(
    'clear, upgrade, with_pip, prompt, python_version, platform_arch, cache_dir',
    [
        (True, True, True, 'prompt', '3.8', 'amd64', 'cache_dir'),
        (False, False, False, 'prompt', '3.8', 'win32', None),
        (True, False, True, 'prompt', '3.8', 'amd64', 'cache_dir'),
    ]
)
def test_embeddable_env_builder(
    clear: bool,
    upgrade: bool,
    with_pip: bool,
    prompt: str,
    python_version: str,
    platform_arch: str,
    cache_dir: Optional[str],
):
    builder = EmbeddableEnvBuilder(
        clear=clear,
        upgrade=upgrade,
        with_pip=with_pip,
        prompt=prompt,
        python_version=python_version,
        platform_arch=platform_arch,
        cache_dir=cache_dir,
    )
    assert builder.clear == clear
    assert builder.upgrade == upgrade
    assert builder.with_pip == with_pip
    assert builder.prompt == prompt
    assert builder.python_version == python_version
    assert builder.platform_arch == platform_arch
    assert builder.cache_dir == cache_dir

    # assert default values
    assert not builder.symlinks
    assert not builder.system_site_packages


@pytest.mark.parametrize(
    'cache_dir',
    [
        '.',
        None,
    ]
)
def test_embeddable_env_builder_setup_python(
    dir_removed_after_test: str,
    mock_embed_python_zip: Tuple[str, str, str],
    cache_dir: Optional[str],
    mocker
):
    # preparation
    builder = EmbeddableEnvBuilder(
        clear=True,
        upgrade=True,
        with_pip=True,
        prompt='prompt',
        python_version=mock_embed_python_zip[0],
        platform_arch=mock_embed_python_zip[1],
        cache_dir=cache_dir,
    )
    context = SimpleNamespace()
    context.env_dir = dir_removed_after_test
    short_version: str = ''.join(mock_embed_python_zip[0].split(".")[:-1])
    # mock
    mocker.patch('penv.subprocess.run')
    # execute
    builder.setup_python(context)
    # assert
    assert os.path.exists(context.env_dir)
    assert os.path.exists(os.path.join(context.env_dir, 'Include'))
    assert os.path.exists(os.path.join(context.env_dir, 'Lib', 'site-packages'))
    assert os.path.exists(os.path.join(context.env_dir, 'Scripts'))
    with open(os.path.join(context.env_dir, f'python{short_version}._pth')) as f:
        contents = f.read()
        assert '#import site' not in contents
        assert 'import site' in contents
        assert '.\\Lib\\site-packages' in contents


def test_embeddable_env_builder_setup_pip(
    dir_removed_after_test: str,
    mock_embed_python_zip: Tuple[str, str, str],
    mocker
):
    # preparation
    builder = EmbeddableEnvBuilder(
        clear=True,
        upgrade=True,
        with_pip=True,
        prompt='prompt',
        python_version=mock_embed_python_zip[0],
        platform_arch=mock_embed_python_zip[1],
        cache_dir=None,
    )
    context = SimpleNamespace()
    context.env_dir = dir_removed_after_test
    # mock
    mock_run = mocker.MagicMock()
    mocker.patch('penv.subprocess.run', side_effect=mock_run)
    builder._call_new_python = mocker.MagicMock()  # type: ignore
    # execute
    builder._setup_pip(context)
    # assert
    assert mock_run.call_args_list[0] == (
        ([
            'curl',
            '-fsL',
            'https://bootstrap.pypa.io/get-pip.py',
            '-o',
            os.path.join(dir_removed_after_test, 'get-pip.py'),
        ],),
        {'check': True},
    )
    assert builder._call_new_python.call_args_list[0] == (  # type: ignore
        (context, os.path.join(dir_removed_after_test, 'get-pip.py')),
        {'stderr': subprocess.STDOUT}
    )


def test_embeddable_env_builder_post_setup(mock_embed_python_zip: Tuple[str, str, str]):
    # preparation
    builder = EmbeddableEnvBuilder(
        clear=True,
        upgrade=True,
        with_pip=True,
        prompt='prompt',
        python_version=mock_embed_python_zip[0],
        platform_arch=mock_embed_python_zip[1],
        cache_dir=None,
    )
    context = SimpleNamespace()
    context.bin_path = mock_embed_python_zip[2]
    assert os.path.exists(os.path.join(mock_embed_python_zip[2], 'activate.bat'))
    assert os.path.exists(os.path.join(mock_embed_python_zip[2], 'activate.ps1'))
    assert os.path.exists(os.path.join(mock_embed_python_zip[2], 'activate'))
    # execute
    builder.post_setup(context)
    # assert
    assert os.path.exists(os.path.join(mock_embed_python_zip[2], 'activate.bat'))
    # assert not os.path.exists(os.path.join(mock_embed_python_zip[2], 'activate.ps1'))
    assert os.path.exists(os.path.join(mock_embed_python_zip[2], 'activate'))
    with open(os.path.join(mock_embed_python_zip[2], 'activate.bat')) as f:
        contents = f.read()
        assert 'set VIRTUAL_ENV=%~dp0;%~dp0\\Scripts' in contents
        assert 'set PATH=%VIRTUAL_ENV%\\;%PATH%' not in contents
        assert 'set PATH=%VIRTUAL_ENV%;%PATH%' in contents
    with open(os.path.join(mock_embed_python_zip[2], 'activate')) as f:
        contents = f.read()
        assert 'VIRTUAL_ENV=$(dirname \"$(realpath \'$0\')\")/.penv/:$(dirname \"$(realpath \'$0\')\")/.penv/Scripts' in contents  # noqa


@pytest.mark.integrate
def test_main(dir_removed_after_test: str):
    args = [
        dir_removed_after_test,
        '--python-version', '3.8.5',
        '--platform-arch', 'amd64',
    ]
    main(args)
