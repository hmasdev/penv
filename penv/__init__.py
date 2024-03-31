import logging
import os
import platform
import re
import shutil
import subprocess
import sys
from typing import Optional, Union
from types import SimpleNamespace
from venv import EnvBuilder

__version__ = '0.0.0'

CORE_VENV_DEPS = ('pip', 'setuptools')
logger = logging.getLogger(__name__)


class EmbeddableEnvBuilder(EnvBuilder):

    def __init__(
        self,
        clear: bool = False,
        upgrade: bool = False,
        with_pip: bool = False,
        prompt: Optional[str] = None,
        python_version: str = platform.python_version(),
        platform_arch: str = platform.machine().lower(),
        cache_dir: Optional[str] = None,
    ):
        # validation
        assert platform.system() == "Windows", "Only Windows is supported"
        # set attributes
        self.python_version = python_version
        self.platform_arch = platform_arch
        self.cache_dir = cache_dir
        super().__init__(
            system_site_packages=False,
            clear=clear,
            symlinks=False,
            upgrade=upgrade,
            with_pip=with_pip,
            prompt=prompt,
            upgrade_deps=False,
        )

    def ensure_directories(
        self,
        env_dir: Union[str, bytes, os.PathLike[str], os.PathLike[bytes]],
    ) -> SimpleNamespace:
        """
        Create the directories for the environment.

        Returns a context object which holds paths in the environment,
        for use by subsequent logic.
        """

        def create_if_needed(d):
            if not os.path.exists(d):
                os.makedirs(d)
            elif os.path.islink(d) or os.path.isfile(d):
                raise ValueError('Unable to create directory %r' % d)

        if os.path.exists(env_dir) and self.clear:
            self.clear_directory(env_dir)

        context = SimpleNamespace()
        context.env_dir = env_dir
        context.env_name = os.path.split(env_dir)[1]
        prompt = self.prompt if self.prompt is not None else context.env_name
        context.prompt = f'({prompt!r}) '
        create_if_needed(env_dir)
        # NOTE: venv.EnvBuilder uses 'venv/Scripts' for the bin directory on Windows
        #       but embeddable python uses 'venv/'. We need to use 'venv/' to make sure
        binname = ''
        incpath = 'Include'
        libpath = os.path.join(env_dir, 'Lib', 'site-packages')  # type: ignore
        context.inc_path = path = os.path.join(env_dir, incpath)  # type: ignore
        create_if_needed(path)
        create_if_needed(libpath)
        context.bin_path = binpath = os.path.join(env_dir, binname)  # type: ignore
        context.bin_name = binname
        context.env_exe = os.path.join(binpath, 'python.exe')  # type: ignore
        create_if_needed(binpath)
        # Assign and update the command to use when launching the newly created
        # environment, in case it isn't simply the executable script (e.g. bpo-45337)
        context.env_exec_cmd = context.env_exe
        if sys.platform == 'win32':
            # bpo-45337: Fix up env_exec_cmd to account for file system redirections.
            # Some redirects only apply to CreateFile and not CreateProcess
            real_env_exe = os.path.realpath(context.env_exe)
            if os.path.normcase(real_env_exe) != os.path.normcase(context.env_exe):
                logger.warning('Actual environment location may have moved due to '
                               'redirects, links or junctions.\n'
                               '  Requested location: "%s"\n'
                               '  Actual location:    "%s"',
                               context.env_exe, real_env_exe)
                context.env_exec_cmd = real_env_exe
        return context

    def create_configuration(self, context: SimpleNamespace) -> None:
        return None

    def _call_new_python(self, context, *py_args, **kwargs):
        """Executes the newly created Python using safe-ish options"""
        # gh-98251: We do not want to just use '-I' because that masks
        # legitimate user preferences (such as not writing bytecode). All we
        # really need is to ensure that the path variables do not overrule
        # normal venv handling.
        args = [context.env_exec_cmd, *py_args]
        kwargs['env'] = env = os.environ.copy()
        env['VIRTUAL_ENV'] = context.env_dir
        env.pop('PYTHONHOME', None)
        env.pop('PYTHONPATH', None)
        kwargs['cwd'] = context.env_dir
        kwargs['executable'] = context.env_exec_cmd
        subprocess.check_output(args, **kwargs)

    def setup_python(self, context: SimpleNamespace) -> None:
        # download and extract the embeddable python
        zip_name: str = f'python-{self.python_version}-embed-{self.platform_arch}.zip'
        if self.cache_dir and os.path.exists(os.path.join(self.cache_dir, zip_name)):
            logger.info(
                f"Use cached embeddable python {zip_name} in {self.cache_dir}"
            )
            try:
                shutil.copyfile(
                    os.path.join(self.cache_dir, zip_name),
                    zip_name,
                )
            except shutil.SameFileError:
                logger.warning(
                    f"shutil.copyfile has raised SameFileError: {zip_name}"
                )
                pass
        else:
            url = f'https://www.python.org/ftp/python/{self.python_version}/{zip_name}'
            subprocess.run(['curl', '-fsLO', url], check=True)
            logger.debug(f"Downloaded {url}")
            if self.cache_dir:
                logger.info(f"Caching embeddable python {zip_name} in {self.cache_dir}")
                try:
                    shutil.copyfile(
                        zip_name,
                        os.path.join(self.cache_dir, zip_name),
                    )
                except shutil.SameFileError:
                    logger.warning(f"shutil.copyfile has raised SameFileError: {zip_name}")
                    pass
        # extract the embeddable python
        shutil.unpack_archive(zip_name, context.env_dir)
        os.makedirs(os.path.join(context.env_dir, 'Include'), exist_ok=True)
        os.makedirs(os.path.join(context.env_dir, 'Lib', 'site-packages'), exist_ok=True)
        os.makedirs(os.path.join(context.env_dir, 'Scripts'), exist_ok=True)
        logger.debug(f"Extracted {zip_name} to {context.env_dir}")
        # remove the zip file
        os.remove(zip_name)
        # rewrite the pth file
        short_version = ''.join(self.python_version.split(".")[:-1])
        pth_file = os.path.join(context.env_dir, f'python{short_version}._pth')
        with open(pth_file, 'r') as f:
            contents: str = f.read().replace('#import site', 'import site')
            contents = contents + '\n' + os.path.join('.', 'Lib', 'site-packages') + '\n'
        with open(pth_file, 'w') as f:
            f.write(contents)
        logger.debug(f"Rewrote {pth_file}")

    def _setup_pip(self, context: SimpleNamespace) -> None:
        # use get-pip.py
        # download and extract get-pip
        url: str = 'https://bootstrap.pypa.io/get-pip.py'
        get_pip_path: str = os.path.join(context.env_dir, 'get-pip.py')
        subprocess.run(['curl', '-fsL', url, '-o', get_pip_path], check=True)
        logger.debug(f"Downloaded {url}")
        # run get-pip
        self._call_new_python(context, get_pip_path, stderr=subprocess.STDOUT)  # type: ignore
        # subprocess.run([context.env_exe, get_pip_path], check=True)
        logger.debug("Ran get-pip.py")

        # use current pip
        # import pip
        # pip_dir: str = os.path.dirname(pip.__file__)
        # shutil.copytree(pip_dir, os.path.join(context.env_dir, 'Lib', 'site-packages', 'pip'))

    def post_setup(self, context: SimpleNamespace) -> None:
        contents: str = ''
        # modify activate.bat
        activate_bat_path: str = os.path.join(context.bin_path, 'activate.bat')
        with open(activate_bat_path, 'r') as f:
            contents = f.read()
            pattern = re.compile(r'^set VIRTUAL_ENV=.+$', re.MULTILINE)
            contents = pattern.sub(
                'set VIRTUAL_ENV=%~dp0;%~dp0\\\\Scripts',
                contents,
            )
            contents = contents.replace(
                'set PATH=%VIRTUAL_ENV%\\;%PATH%',
                'set PATH=%VIRTUAL_ENV%;%PATH%',
            )
        with open(activate_bat_path, 'w') as f:
            f.write(contents)
        logger.debug(f"Modified {activate_bat_path}")
        # modify activate.ps1
        # if os.path.exists(os.path.join(context.bin_path, 'activate.ps1')):
        #     os.remove(os.path.join(context.bin_path, 'activate.ps1'))
        # modify activate
        activate_path: str = os.path.join(context.bin_path, 'activate')
        with open(activate_path, 'r') as f:
            contents = f.read()
            pattern = re.compile(r'^VIRTUAL_ENV=.+$', re.MULTILINE)
            contents = pattern.sub(
                'VIRTUAL_ENV=$(dirname \"$(realpath \'$0\')\")/.penv/'
                ':$(dirname \"$(realpath \'$0\')\")/.penv/Scripts',
                contents
            )
        with open(activate_path, 'w') as f:
            f.write(contents)
        logger.debug(f"Modified {activate_path}")


def main(args=None):
    compatible = True
    if os.name != 'nt':
        raise Exception("Only Windows is supported")
    if sys.version_info < (3, 5):
        compatible = False
    elif not hasattr(sys, 'base_prefix'):
        compatible = False
    if not compatible:
        raise ValueError('This script is only for use with Python >= 3.5')
    else:
        import argparse

        parser = argparse.ArgumentParser(
            prog=__name__,
            description='Creates virtual Python environments in one or more target directories.',
            epilog=(
                'Once an environment has been created, you may wish to '
                'activate it, e.g. by sourcing an activate script in its bin directory.'
            ),
        )
        parser.add_argument(
            'dirs',
            metavar='ENV_DIR',
            nargs='+',
            help='A directory to create the environment in.',
        )
        parser.add_argument(
            '--clear',
            default=False,
            action='store_true',
            dest='clear',
            help=(
                'Delete the contents of the environment directory if it '
                'already exists, before environment creation.'
            ),
        )
        parser.add_argument(
            '--upgrade',
            default=False,
            action='store_true',
            dest='upgrade',
            help=(
                'Upgrade the environment directory to use this version '
                'of Python, assuming Python has been upgraded in-place.'
            ),
        )
        parser.add_argument(
            '--without-pip',
            dest='with_pip',
            default=True,
            action='store_false',
            help=(
                'Skips installing or upgrading pip in the '
                'virtual environment (pip is bootstrapped by default)'
            ),
        )
        parser.add_argument(
            '--prompt',
            help='Provides an alternative prompt prefix for this environment.',
        )
        parser.add_argument(
            '--python-version',
            default=platform.python_version(),
            dest='python_version',
            help='The version of Python to use',
        )
        parser.add_argument(
            '--platform-arch',
            default=platform.machine().lower(),
            dest='platform_arch',
            help='The platform architecture to use',
        )
        parser.add_argument(
            '--cache-dir',
            default=None,
            dest='cache_dir',
            help='The directory to cache the embeddable python',
        )
        parser.add_argument(
            '--log-level',
            default='INFO',
            dest='log_level',
            help='The logging level',
        )

        options = parser.parse_args(args)
        if options.upgrade and options.clear:
            raise ValueError('you cannot supply --upgrade and --clear together.')
        logging.basicConfig(level=getattr(logging, options.log_level))
        builder = EmbeddableEnvBuilder(
            python_version=options.python_version,
            platform_arch=options.platform_arch,
            cache_dir=options.cache_dir,
            clear=options.clear,
            upgrade=options.upgrade,
            with_pip=options.with_pip,
            prompt=options.prompt,
        )
        for d in options.dirs:
            builder.create(d)


if __name__ == '__main__':
    rc = 1
    try:
        main()
        rc = 0
    except Exception as e:
        print('Error: %s' % e, file=sys.stderr)
    sys.exit(rc)
