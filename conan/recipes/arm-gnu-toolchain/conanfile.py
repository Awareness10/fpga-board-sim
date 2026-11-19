"""Arm GNU Toolchain (arm-none-eabi-gcc), the official prebuilt binaries from Arm.

ConanCenter has no bare-metal Arm compiler, so this recipe downloads Arm's release for
the machine you build on (Windows, macOS or Linux) and puts its bin/ on the PATH of
anything that tool_requires it. Vitis 2023.2 ships GCC 12 for the same target, so code
built here also builds there.

    conan export conan/recipes/arm-gnu-toolchain       (boardsim setup does this)
"""
import os

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.files import copy, get

URL = "https://developer.arm.com/-/media/Files/downloads/gnu/{v}/binrel/arm-gnu-toolchain-{v}-{host}-arm-none-eabi.{ext}"

# (os, arch) of the build machine -> (Arm's host name, archive type, sha256 from Arm's .sha256asc)
RELEASES = {
    "14.2.rel1": {
        ("Linux", "x86_64"): ("x86_64", "tar.xz", "62a63b981fe391a9cbad7ef51b17e49aeaa3e7b0d029b36ca1e9c3b2a9b78823"),
        ("Linux", "armv8"): ("aarch64", "tar.xz", "87330bab085dd8749d4ed0ad633674b9dc48b237b61069e3b481abd364d0a684"),
        ("Macos", "armv8"): ("darwin-arm64", "tar.xz", "c7c78ffab9bebfce91d99d3c24da6bf4b81c01e16cf551eb2ff9f25b9e0a3818"),
        ("Macos", "x86_64"): ("darwin-x86_64", "tar.xz", "2d9e717dd4f7751d18936ae1365d25916534105ebcb7583039eff1092b824505"),
        ("Windows", "x86_64"): ("mingw-w64-x86_64", "zip", "f074615953f76036e9a51b87f6577fdb4ed8e77d3322a6f68214e92e7859888f"),
    },
}


class ArmGnuToolchain(ConanFile):
    name = "arm-gnu-toolchain"
    version = "14.2.rel1"
    description = "Arm GNU Toolchain for bare-metal Arm (arm-none-eabi), prebuilt by Arm"
    license = "GPL-3.0-or-later WITH GCC-exception-3.1"
    homepage = "https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads"
    package_type = "application"
    settings = "os", "arch"

    def _release(self):
        return RELEASES[self.version].get((str(self.settings.os), str(self.settings.arch)))

    def validate(self):
        if self._release() is None:
            raise ConanInvalidConfiguration(
                f"No Arm GNU Toolchain {self.version} build for {self.settings.os}/{self.settings.arch}. "
                "Install arm-none-eabi-gcc yourself and use the cortexa9-baremetal-gcc-system profile.")

    def build(self):
        host, ext, sha256 = self._release()
        get(self, URL.format(v=self.version, host=host, ext=ext), sha256=sha256, strip_root=True)

    def package(self):
        # Everything but the manuals (bin/, lib/gcc multilibs, arm-none-eabi/ newlib, libexec/).
        copy(self, "*", self.build_folder, self.package_folder,
             excludes=["share/doc/*", "share/info/*", "share/man/*", "conaninfo.txt", "conanbuildinfo*"])

    def package_info(self):
        self.cpp_info.includedirs = []
        self.cpp_info.libdirs = []
        self.cpp_info.bindirs = ["bin"]
        self.buildenv_info.prepend_path("PATH", os.path.join(self.package_folder, "bin"))
