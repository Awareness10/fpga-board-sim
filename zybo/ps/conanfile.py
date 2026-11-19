import sys

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout
from conan.tools.env import Environment


class ZyboPs(ConanFile):
    """Bare-metal Cortex-A9 programs for the Zynq-7000 PS, run under QEMU xilinx-zynq-a9.

    conan build zybo/ps -pr:h conan/profiles/cortexa9-baremetal-gcc -pr:b default --build=missing
    """

    name = "zybo-ps"
    version = "0.1"
    settings = "os", "arch", "compiler", "build_type"

    def validate(self):
        if self.settings.os != "baremetal" or not str(self.settings.arch).startswith("armv7"):
            raise ConanInvalidConfiguration("Use an armv7 baremetal host profile (conan/profiles/cortexa9-baremetal-gcc)")

    def layout(self):
        cmake_layout(self)

    def generate(self):
        tc = CMakeToolchain(self)
        # ctest runs programs through qemu.py: use the Python that runs Conan (uv's venv).
        tc.cache_variables["Python3_EXECUTABLE"] = sys.executable.replace("\\", "/")
        tc.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()
        env = Environment()
        env.define("CTEST_OUTPUT_ON_FAILURE", "1")
        with env.vars(self).apply():
            cmake.test()
