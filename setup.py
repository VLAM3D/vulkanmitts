"""setup for the vulkanmitts project

 Based on this file:
 https://github.com/davisking/dlib/blob/master/setup.py

 Copyright (C) 2015  Ehsan Azar (dashesy@linux.com)
 License: Boost Software License   See LICENSE.txt for the full license.

This file basically just uses CMake to compile the vulkanmitts and then puts the outputs into standard
python packages.

To build the vulkanmitts:
    python setup.py build
To build and install:
    python setup.py install
To package the wheel (after pip installing twine and wheel):
    python setup.py bdist_wheel
To upload the wheel to PyPi
    twine upload dist/*.whl
To repackage the previously built package as wheel (bypassing build):
    python setup.py bdist_wheel --repackage
To install a develop version (egg with symbolic link):
    python setup.py develop
To exclude/include certain options in the cmake config use --yes and --no:
    for example:
    --yes vulkanmitts_NO_GUI_SUPPORT: will set -Dvulkanmitts_NO_GUI_SUPPORT=yes
    --no vulkanmitts_NO_GUI_SUPPORT: will set -Dvulkanmitts_NO_GUI_SUPPORT=no
Additional options:
    --compiler-flags: pass flags onto the compiler, e.g. --compiler-flag "-Os -Wall" passes -Os -Wall onto GCC.
    --debug: makes a debug build
    --cmake: path to specific cmake executable
    --G or -G: name of a build system generator (equivalent of passing -G "name" to cmake)
"""

from __future__ import print_function
import shutil
import stat
import errno

from setuptools.command.bdist_egg import bdist_egg as _bdist_egg
from setuptools.command.develop import develop as _develop
from distutils.command.build_ext import build_ext as _build_ext
from distutils.command.build import build as _build
from distutils.errors import DistutilsSetupError
from distutils.spawn import find_executable
from distutils.sysconfig import get_python_inc, get_python_version, get_config_var
from distutils import log
import os
import sys
from setuptools import Extension, setup
import platform
from subprocess import Popen, PIPE, STDOUT
import signal
from threading import Thread
import time
import re


# change directory to this module path
try:
    this_file = __file__
except NameError:
    this_file = sys.argv[0]
this_file = os.path.abspath(this_file)
if os.path.dirname(this_file):
    os.chdir(os.path.dirname(this_file))
script_dir = os.getcwd()

def _get_options():
    """read arguments and creates options
    """
    _options = []
    _cmake_config = 'Release'
    opt_key = None

    argv = [arg for arg in sys.argv]  # take a copy
    # parse commandline options and consume those we care about
    for opt_idx, arg in enumerate(argv):
        if opt_key:
            sys.argv.remove(arg)
            opt_key = None
            continue

        if not arg.startswith('--'):
            continue

        opt = arg[2:].lower()

        custom_arg = True
        if opt == 'debug':
            _cmake_config = 'Debug'
        elif opt == 'release':
            _cmake_config = 'Release'
        elif opt in ['repackage']:
            _options.append(opt)
        else:
            custom_arg = False
        if custom_arg:
            sys.argv.remove(arg)

    return _options, _cmake_config


options, cmake_config = _get_options()
cmake_path = find_executable("cmake")

try:
    from Queue import Queue, Empty
except ImportError:
    # noinspection PyUnresolvedReferences
    from queue import Queue, Empty  # python 3.x


_ON_POSIX = 'posix' in sys.builtin_module_names


def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)


def _log_buf(buf):
    if not buf:
        return
    if sys.stdout.encoding:
        buf = buf.decode(sys.stdout.encoding)
    buf = buf.rstrip()
    lines = buf.splitlines()
    for line in lines:
        log.info(line)


def run_process(cmds, timeout=None):
    """run a process asynchronously
    :param cmds: list of commands to invoke on a shell e.g. ['make', 'install']
    :param timeout: timeout in seconds (optional)
    """

    # open process as its own session, and with no stdout buffering
    p = Popen(cmds,
              stdout=PIPE, stderr=STDOUT,
              bufsize=1,
              close_fds=_ON_POSIX, preexec_fn=os.setsid if _ON_POSIX else None)

    q = Queue()
    t = Thread(target=enqueue_output, args=(p.stdout, q))
    t.daemon = True  # thread dies with the program
    t.start()

    _time = time.time()
    e = None
    try:
        while t.isAlive():
            try:
                buf = q.get(timeout=.1)
            except Empty:
                buf = b''
            _log_buf(buf)
            elapsed = time.time() - _time
            if timeout and elapsed > timeout:
                break
        # Make sure we print all the output from the process.
        if p.stdout:
            for line in p.stdout:
                _log_buf(line)
            p.wait()
    except (KeyboardInterrupt, SystemExit) as e:
        # if user interrupted
        pass

    # noinspection PyBroadException
    try:
        os.kill(p.pid, signal.SIGINT)
    except (KeyboardInterrupt, SystemExit) as e:
        pass
    except:
        pass

    # noinspection PyBroadException
    try:
        if e:
            os.kill(p.pid, signal.SIGKILL)
        else:
            p.wait()
    except (KeyboardInterrupt, SystemExit) as e:
        # noinspection PyBroadException
        try:
            os.kill(p.pid, signal.SIGKILL)
        except:
            pass
    except:
        pass

    t.join(timeout=0.1)
    if e:
        raise e

    return p.returncode


def readme(fname):
    """Read text out of a file relative to setup.py.
    """
    return open(os.path.join(script_dir, fname)).read()


def read_version():
    """Read version information
    """
    major = '0'
    minor = '9'
    patch = '0'
    return major + '.' + minor + '.' + patch


def rmtree(name):
    """remove a directory and its subdirectories.
    """
    def remove_read_only(func, path, exc):
        excvalue = exc[1]
        if func in (os.rmdir, os.remove) and excvalue.errno == errno.EACCES:
            os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
            func(path)
        else:
            raise
    shutil.rmtree(name, ignore_errors=False, onerror=remove_read_only)


def copy_file(src, dst):
    """copy a single file and log
    """
    log.info("Copying file %s -> %s." % (src, dst))
    shutil.copy2(src, dst)


def clean_dist():
    """re-create the dist folder
    """
    dist_dir = os.path.join(script_dir, "./dist")
    if os.path.exists(dist_dir):
        log.info('Removing distribution directory %s' % dist_dir)
        rmtree(dist_dir)

    dist_dir = os.path.join(script_dir, "./dist/vulkanmitts")
    try:
        os.makedirs(dist_dir)
    except OSError:
        pass


# always start with a clean slate
clean_dist()

# noinspection PyPep8Naming
class build(_build):
    def run(self):
        repackage = 'repackage' in options
        if not repackage:
            self.build_vulkanmitts()

        dist_glslang_dir = os.path.join(script_dir, "./dist/pyglslang")
        try:
            os.makedirs(dist_glslang_dir)
        except OSError:
            pass

        dist_dir = os.path.join(script_dir, "./dist/vulkanmitts")
        log.info('Populating the distribution directory %s ...' % dist_dir)

        copy_file("./install/bin/pyglslang.py", os.path.join(dist_glslang_dir,'pyglslang.py'))
        copy_file("./install/bin/_pyglslang"+py_module_ext, os.path.join(dist_glslang_dir,'_pyglslang'+py_module_ext))
        copy_file("./install/bin/vulkanmitts.py", os.path.join(dist_dir,'vulkanmitts.py'))
        copy_file("./install/bin/_vulkanmitts"+py_module_ext, os.path.join(dist_dir,'_vulkanmitts'+py_module_ext))

        with open(os.path.join(dist_dir, '__init__.py'), 'w') as f:
            # just so that we can `import vulkanmitts` and not `from vulkanmitts import vulkanmitts`
            f.write('from .vulkanmitts import *\n')
            # add version here
            f.write('__version__ = "{ver}"\n'.format(ver=read_version()))

        with open(os.path.join(dist_glslang_dir, '__init__.py'), 'w') as f:
            # just so that we can `import pyglslang` and not `from pyglslang import pyglslang`
            f.write('from .pyglslang import *\n')
            # add version here
            f.write('__version__ = "{ver}"\n'.format(ver=read_version()))

        return _build.run(self)

    @staticmethod
    def build_vulkanmitts():
        """use cmake to build and install the extension
        """
        if cmake_path is None:
            cmake_install_url = "https://cmake.org/install/"
            message = ("You can install cmake using the instructions at " +
                       cmake_install_url)
            msg_pkgmanager = ("You can install cmake on {0} using "
                              "`sudo {1} install cmake`.")
            if sys.platform == "darwin":
                pkgmanagers = ('brew', 'port')
                for manager in pkgmanagers:
                    if find_executable(manager) is not None:
                        message = msg_pkgmanager.format('OSX', manager)
                        break
            elif sys.platform.startswith('linux'):
                try:
                    import distro
                except ImportError as err:
                    import pip
                    pip_exit = pip.main(['install', '-q', 'distro'])
                    if pip_exit > 0:
                        log.debug("Unable to install `distro` to identify "
                                  "the recommended command. Falling back "
                                  "to default error message.")
                        distro = err
                    else:
                        import distro
                if not isinstance(distro, ImportError):
                    distname = distro.id()
                    if distname in ('debian', 'ubuntu'):
                        message = msg_pkgmanager.format(
                            distname.title(), 'apt-get')
                    elif distname in ('fedora', 'centos', 'redhat'):
                        pkgmanagers = ("dnf", "yum")
                        for manager in pkgmanagers:
                            if find_executable(manager) is not None:
                                message = msg_pkgmanager.format(
                                    distname.title(), manager)
                                break

            raise DistutilsSetupError(
                "Cannot find cmake, ensure it is installed and in the path.\n"
                + message + "\n"
                "You can also specify its path with --cmake parameter.")

        cmake_extra = []
        cmake_gen = []
        if sys.platform.startswith('linux'):
            this_file_dir = os.path.dirname(os.path.realpath(__file__))
            numpy_swig_inc_path = os.path.join(this_file_dir, 'numpy_swig')
            cmake_extra += ['-DNUMPY_SWIG_DIR=' + numpy_swig_inc_path]
            cmake_extra += ['-DCMAKE_BUILD_TYPE=RELEASE']
        elif sys.platform == "win32":
            cmake_gen = ['-G','Visual Studio 14 2015 Win64']
            cmake_extra += ['-DSWIG_DIR=C:/DEV/swigwin-3.0.12']
            cmake_extra += ['-DSWIG_EXECUTABLE=C:/dev/swigwin-3.0.12/swig.exe']
            cmake_extra += ['-DNUMPY_SWIG_DIR=C:/dev/vulkanmitts/numpy_swig/']
            cmake_extra += ['-DVULKAN_SDK=c:/VulkanSDK/1.0.65.0/']
            if sys.version_info >= (3, 0):
                cmake_extra += ['-DPYTHON3=yes']

        platform_arch = platform.architecture()[0]
        log.info("Detected Python architecture: %s" % platform_arch)

        # make sure build artifacts are generated for the version of Python currently running
        inc_dir = get_python_inc()
        lib_dir = get_config_var('LIBDIR')
        if (inc_dir != None):
            cmake_extra += ['-DPYTHON_INCLUDE_DIR=' + inc_dir]
        if (lib_dir != None):
            cmake_extra += ['-DCMAKE_LIBRARY_PATH=' + lib_dir]

        cmake_extra += ['-DCMAKE_INSTALL_PREFIX=../install']

        log.info("Detected platform: %s" % sys.platform)

        build_dir = os.path.join(script_dir, "./build")
        if os.path.exists(build_dir):
            log.info('Removing build directory %s' % build_dir)
            rmtree(build_dir)

        try:
            os.makedirs(build_dir)
        except OSError:
            pass

        # cd build
        os.chdir(build_dir)
        log.info('Configuring cmake ...')
        cmake_cmd = [
            cmake_path,
            "..",
        ] + cmake_gen + cmake_extra
        if run_process(cmake_cmd):
            raise DistutilsSetupError("cmake configuration failed!")

        log.info('Build using cmake ...')

        cmake_cmd = [
            cmake_path,
            "--build", ".",
            "--config", cmake_config,
            "--target", "install",
        ]

        if run_process(cmake_cmd):
            raise DistutilsSetupError("cmake build failed!")

        # cd back where setup awaits
        os.chdir(script_dir)


# noinspection PyPep8Naming
class develop(_develop):

    def __init__(self, *args, **kwargs):
        _develop.__init__(self, *args, **kwargs)

    def run(self):
        self.run_command("build")
        return _develop.run(self)


# noinspection PyPep8Naming
class bdist_egg(_bdist_egg):
    def __init__(self, *args, **kwargs):
        _bdist_egg.__init__(self, *args, **kwargs)

    def run(self):
        self.run_command("build")
        return _bdist_egg.run(self)


# noinspection PyPep8Naming
class build_ext(_build_ext):
    def __init__(self, *args, **kwargs):
        _build_ext.__init__(self, *args, **kwargs)

    def run(self):
        # cmake will do the heavy lifting, just pick up the fruits of its labour
        pass

package_data = {}
if sys.platform.startswith('linux'):
    package_data['pyglslang'] = ['_pyglslang.so']
    package_data['vulkanmitts'] = ['_vulkanmitts.so']
    py_module_ext = '.so'
else:
    package_data['pyglslang'] = ['_pyglslang.pyd']
    package_data['vulkanmitts'] = ['_vulkanmitts.pyd']
    py_module_ext = '.pyd'

setup(
    name='vulkanmitts',
    version=read_version(),
    keywords=['Vulkan'],
    description='Khronos Vulkan Pythonic Wrapper',
    long_description=readme('README.md'),
    author='Mathieu Lamarre',
    author_email='mathieu@vlam3d.com',
    url='https://github.com/VLAM3D/vulkanmitts',
    license='MIT',
    packages=['pyglslang','vulkanmitts'],
    package_dir={'': 'dist'},
    package_data=package_data,
    include_package_data=True,
    cmdclass={
        'build': build,
        'build_ext': build_ext,
        'bdist_egg': bdist_egg,
        'develop': develop,
    },
    zip_safe=False,
    ext_modules=[Extension('vulkanmitts', [])],
    ext_package='vulkanmitts',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Science/Research',
        'Intended Audience :: Developers',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX',
        'Operating System :: POSIX :: Linux',
        'Operating System :: Microsoft',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: C++',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Scientific/Engineering',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
        'Topic :: Scientific/Engineering :: Image Recognition',
        'Topic :: Software Development',
    ],
)
