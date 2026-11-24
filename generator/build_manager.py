"""
Build manager and environment detection module for Android APK generation.
Detects Java/JDK, Android SDK, Android Build Tools, and Gradle.
Executes the Gradle build via subprocess with real-time streaming output.
"""

import os
import re
import sys
import shutil
import platform
import subprocess
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .template_manager import get_base_dir, get_runtime_dir


class EnvironmentDetector:
    """Detects and validates local system build dependencies."""

    @classmethod
    def detect_all(cls) -> Dict[str, Dict[str, any]]:
        """
        Runs full environment diagnostics.
        Returns a dictionary with status, path, and details for each component.
        """
        java_info = cls.detect_java()
        sdk_info = cls.detect_android_sdk()
        build_tools_info = cls.detect_build_tools(sdk_info.get("path"))
        gradle_info = cls.detect_gradle()

        # Check Java compatibility: Gradle 9.3.1 / AGP 9.1.1 requires Java 17 to 21
        java_major = java_info.get("major_version")
        java_compatible = java_info.get("compatible", False)
        java_warning = java_info.get("warning")

        if java_info["found"] and java_major is not None:
            if java_major > 21:
                java_compatible = False
                java_warning = (
                    f"Compatible JDK required.\n"
                    f"Detected: Java {java_info.get('version')} (JDK {java_major}) at {java_info.get('path')}.\n"
                    f"Android Gradle Plugin and Gradle 9.3.1 require JDK 17 or JDK 21. "
                    f"JDK {java_major} is not supported. Please install JDK 17 or JDK 21."
                )
            elif java_major < 17:
                java_compatible = False
                java_warning = (
                    f"Compatible JDK required.\n"
                    f"Detected: Java {java_info.get('version')} (JDK {java_major}).\n"
                    f"Android Gradle Plugin and Gradle 9.3.1 require JDK 17 or JDK 21. Please install JDK 17 or JDK 21."
                )

        java_info["compatible"] = java_compatible
        java_info["warning"] = java_warning

        all_ready = (
            java_info["found"]
            and java_compatible
            and sdk_info["found"]
            and build_tools_info["found"]
            and gradle_info["found"]
        )

        return {
            "java": java_info,
            "sdk": sdk_info,
            "build_tools": build_tools_info,
            "gradle": gradle_info,
            "ready": all_ready,
        }

    @classmethod
    def _parse_major_version(cls, version_str: str) -> Optional[int]:
        """Extracts the major integer version from Java version string (e.g. '21.0.2' -> 21, '1.8.0_312' -> 8)."""
        if not version_str:
            return None
        clean = version_str.strip().lstrip("v")
        if clean.startswith("1."):
            parts = clean.split(".")
            if len(parts) > 1 and parts[1].isdigit():
                return int(parts[1])
        match = re.match(r"^(\d+)", clean)
        if match:
            return int(match.group(1))
        return None

    @classmethod
    def detect_java(cls) -> Dict[str, any]:
        """
        Detects installed JDK versions, prioritizing compatible JDK 17 or JDK 21.
        Explicitly excludes incompatible versions like JDK 25 with Gradle 9.3.1.
        """
        raw_candidates: List[Path] = []

        # 1. Check JAVA_HOME
        java_home = os.environ.get("JAVA_HOME")
        if java_home:
            raw_candidates.append(Path(java_home))

        # 2. Check standard Windows locations
        if sys.platform == "win32":
            local_appdata = os.environ.get("LOCALAPPDATA", "")
            program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
            program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
            user_profile = os.environ.get("USERPROFILE", "")

            search_roots = [
                Path(program_files) / "Java",
                Path(program_files) / "Eclipse Adoptium",
                Path(program_files) / "Microsoft",
                Path(program_files) / "Amazon Corretto",
                Path(program_files) / "Android" / "Android Studio" / "jbr",
                Path(program_files) / "Android" / "Android Studio1" / "jbr",
                Path(program_files) / "Zulu",
                Path(program_files) / "BellSoft",
                Path(program_files_x86) / "Java",
                Path(local_appdata) / "Programs" / "Eclipse Adoptium",
                Path(user_profile) / ".jdks",
            ]
            for root in search_roots:
                if root.exists():
                    if (root / "bin" / "java.exe").exists():
                        raw_candidates.append(root)
                    else:
                        try:
                            for sub in root.iterdir():
                                if sub.is_dir() and (sub / "bin" / "java.exe").exists():
                                    raw_candidates.append(sub)
                        except Exception:
                            pass

        # 3. Check Linux/macOS standard locations
        else:
            search_paths = [
                Path("/usr/lib/jvm"),
                Path("/opt/homebrew/opt/openjdk"),
                Path("/Library/Java/JavaVirtualMachines"),
            ]
            for root in search_paths:
                if root.exists():
                    try:
                        for sub in root.iterdir():
                            if sub.is_dir() and (sub / "bin" / "java").exists():
                                raw_candidates.append(sub)
                    except Exception:
                        pass

        # 4. Check PATH
        path_java = shutil.which("java")
        if path_java:
            java_bin_dir = Path(path_java).resolve().parent
            raw_candidates.append(java_bin_dir.parent)

        # Remove duplicate paths preserving order
        seen = set()
        unique_candidates: List[Path] = []
        for c in raw_candidates:
            try:
                resolved = c.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    unique_candidates.append(c)
            except Exception:
                if c not in seen:
                    seen.add(c)
                    unique_candidates.append(c)

        # Inspect and evaluate all candidates
        evaluated = []
        for candidate in unique_candidates:
            java_exe = candidate / ("bin/java.exe" if sys.platform == "win32" else "bin/java")
            if java_exe.exists():
                version = cls._get_java_version(str(java_exe))
                if version:
                    major = cls._parse_major_version(version)
                    evaluated.append({
                        "path": str(candidate),
                        "executable": str(java_exe),
                        "version": version,
                        "major_version": major,
                    })

        # Also evaluate system PATH java if not already in evaluated
        if not any(item["executable"] == path_java for item in evaluated if path_java):
            version = cls._get_java_version("java")
            if version:
                major = cls._parse_major_version(version)
                evaluated.append({
                    "path": "PATH (system)",
                    "executable": "java",
                    "version": version,
                    "major_version": major,
                })

        if not evaluated:
            return {
                "found": False,
                "compatible": False,
                "path": None,
                "executable": None,
                "version": None,
                "major_version": None,
                "message": (
                    "Compatible JDK required.\n"
                    "No Java/JDK installation detected.\n"
                    "Android Gradle Plugin and Gradle 9.3.1 require JDK 17 or JDK 21. "
                    "Please install JDK 17 or JDK 21 and set JAVA_HOME."
                ),
                "warning": (
                    "Compatible JDK required.\n"
                    "No Java/JDK installation detected. Please install JDK 17 or JDK 21."
                ),
            }

        # Candidate selection priority:
        # 1. Compatible JDK 17 (strongly preferred)
        jdk_17 = next((x for x in evaluated if x["major_version"] == 17), None)
        if jdk_17:
            return {
                "found": True,
                "compatible": True,
                "path": jdk_17["path"],
                "executable": jdk_17["executable"],
                "version": jdk_17["version"],
                "major_version": 17,
                "message": f"JDK 17 found (Java {jdk_17['version']}) at {jdk_17['path']}",
                "warning": None,
            }

        # 2. Compatible JDK 21
        jdk_21 = next((x for x in evaluated if x["major_version"] == 21), None)
        if jdk_21:
            return {
                "found": True,
                "compatible": True,
                "path": jdk_21["path"],
                "executable": jdk_21["executable"],
                "version": jdk_21["version"],
                "major_version": 21,
                "message": f"JDK 21 found (Java {jdk_21['version']}) at {jdk_21['path']}",
                "warning": None,
            }

        # 3. Compatible JDK between 17 and 21 (e.g. 18, 19, 20)
        jdk_compat = next((x for x in evaluated if x["major_version"] is not None and 17 <= x["major_version"] <= 21), None)
        if jdk_compat:
            return {
                "found": True,
                "compatible": True,
                "path": jdk_compat["path"],
                "executable": jdk_compat["executable"],
                "version": jdk_compat["version"],
                "major_version": jdk_compat["major_version"],
                "message": f"Java {jdk_compat['version']} found at {jdk_compat['path']}",
                "warning": None,
            }

        # 4. Incompatible JDK (e.g. JDK 25 or JDK < 17)
        first_found = evaluated[0]
        detected_desc = f"Java {first_found['version']} (JDK {first_found['major_version']}) at {first_found['path']}"
        diagnostic_msg = (
            f"Compatible JDK required.\n"
            f"Detected: {detected_desc}.\n"
            f"Gradle 9.3.1 and Android Gradle Plugin require JDK 17 or JDK 21. "
            f"JDK {first_found['major_version']} is not compatible. Please install JDK 17 or JDK 21."
        )

        return {
            "found": True,
            "compatible": False,
            "path": first_found["path"],
            "executable": first_found["executable"],
            "version": first_found["version"],
            "major_version": first_found["major_version"],
            "message": diagnostic_msg,
            "warning": diagnostic_msg,
        }

    @classmethod
    def _get_java_version(cls, executable: str) -> Optional[str]:
        """Runs java -version and parses output string."""
        try:
            res = subprocess.run(
                [executable, "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
            out = res.stderr or res.stdout
            match = re.search(r'version "([^"]+)"', out) or re.search(r"(\d+\.\d+(\.\d+)?)", out)
            if match:
                return match.group(1)
            return "Detected"
        except Exception:
            return None

    @classmethod
    def detect_android_sdk(cls) -> Dict[str, any]:
        """Detects Android SDK location."""
        candidates: List[Path] = []

        # Environment variables
        for env_var in ["ANDROID_HOME", "ANDROID_SDK_ROOT"]:
            val = os.environ.get(env_var)
            if val:
                candidates.append(Path(val))

        # Standard Windows locations
        if sys.platform == "win32":
            local_appdata = os.environ.get("LOCALAPPDATA", "")
            user_profile = os.environ.get("USERPROFILE", "")
            candidates.extend([
                Path(local_appdata) / "Android" / "Sdk",
                Path(user_profile) / "AppData" / "Local" / "Android" / "Sdk",
                Path(r"C:\Android\sdk"),
                Path(r"C:\android-sdk"),
            ])
        else:
            home = Path.home()
            candidates.extend([
                home / "Android" / "Sdk",
                home / "Library" / "Android" / "sdk",
                Path("/opt/android-sdk"),
                Path("/usr/lib/android-sdk"),
            ])

        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                # Check for platforms directory
                platforms_dir = candidate / "platforms"
                if platforms_dir.exists() and any(platforms_dir.iterdir()):
                    return {
                        "found": True,
                        "path": str(candidate),
                        "message": f"Android SDK found: {candidate}",
                    }
                elif (candidate / "build-tools").exists():
                    return {
                        "found": True,
                        "path": str(candidate),
                        "message": f"Android SDK found: {candidate}",
                    }

        return {
            "found": False,
            "path": None,
            "message": "Android SDK not found. Please install Android Studio or configure ANDROID_HOME.",
        }

    @classmethod
    def detect_build_tools(cls, sdk_path: Optional[str]) -> Dict[str, any]:
        """Detects installed Android SDK build-tools."""
        if not sdk_path:
            return {"found": False, "version": None, "message": "Android SDK required"}

        build_tools_dir = Path(sdk_path) / "build-tools"
        if not build_tools_dir.exists():
            return {"found": False, "version": None, "message": "build-tools directory missing in SDK"}

        versions = []
        for item in build_tools_dir.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                versions.append(item.name)

        if versions:
            # Sort version strings descending
            versions.sort(reverse=True)
            latest = versions[0]
            return {
                "found": True,
                "version": latest,
                "all_versions": versions,
                "message": f"Build Tools v{latest} found",
            }

        return {"found": False, "version": None, "message": "No Build Tools installed in SDK"}

    @classmethod
    def get_wrapper_version(cls) -> str:
        """Extracts the Gradle version dynamically from gradle-wrapper.properties."""
        candidates = [
            get_base_dir() / "template" / "android_webview",
            get_runtime_dir() / "template" / "android_webview",
            Path(__file__).resolve().parent.parent / "template" / "android_webview",
        ]
        for cand in candidates:
            props = cand / "gradle" / "wrapper" / "gradle-wrapper.properties"
            if props.exists():
                try:
                    content = props.read_text(encoding="utf-8", errors="ignore")
                    m = re.search(r"gradle-([0-9.]+)-", content)
                    if m:
                        return m.group(1)
                except Exception:
                    pass
        return "9.3.1"

    @classmethod
    def detect_gradle(cls) -> Dict[str, any]:
        """Checks for gradle executable or gradle wrapper."""
        # 1. Check system gradle
        sys_gradle = shutil.which("gradle")
        if sys_gradle:
            return {
                "found": True,
                "type": "system",
                "path": sys_gradle,
                "version": cls.get_wrapper_version(),
                "message": f"System Gradle {cls.get_wrapper_version()} found"
            }

        # 2. Check bundled template Gradle Wrapper
        candidates = [
            get_base_dir() / "template" / "android_webview",
            get_runtime_dir() / "template" / "android_webview",
            Path(__file__).resolve().parent.parent / "template" / "android_webview",
        ]
        for cand in candidates:
            wrapper_jar = cand / "gradle" / "wrapper" / "gradle-wrapper.jar"
            wrapper_script = cand / ("gradlew.bat" if sys.platform == "win32" else "gradlew")
            if wrapper_jar.exists() and wrapper_script.exists():
                return {
                    "found": True,
                    "type": "wrapper",
                    "path": str(wrapper_script),
                    "wrapper_jar": str(wrapper_jar),
                    "version": cls.get_wrapper_version(),
                    "message": "Template Gradle Wrapper ready (gradle-wrapper.jar present)",
                }

        # Check for wrapper jar in candidates
        for cand in candidates:
            wrapper_jar = cand / "gradle" / "wrapper" / "gradle-wrapper.jar"
            if wrapper_jar.exists():
                return {
                    "found": True,
                    "type": "wrapper",
                    "path": "gradlew",
                    "wrapper_jar": str(wrapper_jar),
                    "version": cls.get_wrapper_version(),
                    "message": "Template Gradle Wrapper ready",
                }

        return {
            "found": False,
            "type": "missing",
            "path": None,
            "message": "Gradle Wrapper JAR (gradle-wrapper.jar) missing from template and no system Gradle found",
        }


class BuildManager:
    """Handles execution of the Android Gradle build process."""

    def __init__(self, output_dir: Optional[str] = None):
        if output_dir:
            self.output_dir = Path(output_dir).resolve()
        else:
            self.output_dir = (get_runtime_dir() / "Generated_APKs").resolve()

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_apk(
        self,
        project_dir: Path,
        app_name: str,
        log_callback: Optional[Callable[[str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Tuple[bool, Optional[str], str]:
        """
        Executes Gradle build on the isolated project directory.
        Returns (success: bool, apk_path: Optional[str], error_message: str).
        """
        def log(msg: str):
            if log_callback:
                log_callback(msg)

        log("=" * 60)
        log("EVIDENTIX APK BUILD ENGINE INITIALIZING")
        log(f"Target App: {app_name}")
        log(f"Project Workspace: {project_dir}")
        log("=" * 60)

        # 1. Environment validation
        env_status = EnvironmentDetector.detect_all()
        java_info = env_status["java"]
        sdk_info = env_status["sdk"]
        gradle_info = env_status["gradle"]

        if not java_info["found"]:
            err = (
                "Compatible JDK required.\n"
                "No Java/JDK installation detected. Please install JDK 17 or JDK 21 and set JAVA_HOME."
            )
            log(f"\n[FATAL] {err}")
            return False, None, err

        if not java_info.get("compatible", False):
            err = (
                "Compatible JDK required.\n"
                f"Detected: Java {java_info.get('version')} (JDK {java_info.get('major_version')}) at {java_info.get('path')}.\n"
                "Android Gradle Plugin and Gradle 9.3.1 require JDK 17 or JDK 21. "
                f"JDK {java_info.get('major_version')} is not supported. Please install JDK 17 or JDK 21."
            )
            log(f"\n[FATAL] {err}")
            return False, None, err

        if not sdk_info["found"]:
            err = (
                "Build Error: Android SDK not found. Please install Android Studio or configure ANDROID_HOME."
            )
            log(f"\n[FATAL] {err}")
            return False, None, err

        # Preflight Gradle wrapper integrity check
        wrapper_jar = project_dir / "gradle" / "wrapper" / "gradle-wrapper.jar"
        wrapper_bat = project_dir / "gradlew.bat"
        if not wrapper_jar.exists() and not shutil.which("gradle"):
            err = (
                f"Build Error: Gradle Wrapper JAR is missing at {wrapper_jar}.\n"
                "The build cannot proceed without gradle-wrapper.jar."
            )
            log(f"\n[FATAL] {err}")
            return False, None, err

        # Resolve and verify Java executable via 'java -version'
        java_exec = java_info.get("executable")
        if not java_exec or not Path(java_exec).exists():
            if java_info.get("path") and java_info["path"] != "PATH (system)":
                java_exec = str(Path(java_info["path"]) / ("bin/java.exe" if sys.platform == "win32" else "bin/java"))
            else:
                java_exec = "java"

        verified_ver = EnvironmentDetector._get_java_version(java_exec)
        if not verified_ver:
            err = f"Build Error: Failed to execute and verify Java at '{java_exec}' with -version."
            log(f"\n[FATAL] {err}")
            return False, None, err

        verified_major = EnvironmentDetector._parse_major_version(verified_ver)
        if verified_major is not None and (verified_major > 21 or verified_major < 17):
            err = (
                "Compatible JDK required.\n"
                f"Verified Java executable '{java_exec}' returned version {verified_ver} (JDK {verified_major}).\n"
                "Android Gradle Plugin and Gradle 9.3.1 require JDK 17 or JDK 21. Please install JDK 17 or JDK 21."
            )
            log(f"\n[FATAL] {err}")
            return False, None, err

        # Detect dynamic gradle version
        wrapper_version = EnvironmentDetector.get_wrapper_version()
        wrapper_present = (project_dir / "gradle" / "wrapper" / "gradle-wrapper.jar").exists()

        # Log build environment details before starting build
        log("[ENV] ================= BUILD ENVIRONMENT =================")
        log(f"[ENV] Java Version:     {verified_ver} (JDK {verified_major})")
        log(f"[ENV] Java Path:        {java_info.get('path')}")
        log(f"[ENV] Java Executable:  {java_exec}")
        log(f"[ENV] Android SDK:      FOUND ({sdk_info.get('path')})")
        log(f"[ENV] Gradle Version:   {wrapper_version}")
        log(f"[ENV] Gradle Wrapper:   {'FOUND' if wrapper_present else 'NOT FOUND'}")
        log("[ENV] =====================================================")

        # 2. Configure local.properties in project directory
        self._write_local_properties(project_dir, sdk_info["path"])

        # 3. Determine Gradle command to execute
        gradle_cmd = self._resolve_gradle_command(project_dir)
        log(f"[GRADLE] Using runner: {' '.join(gradle_cmd)}")

        # 4. Prepare subprocess environment (pass compatible JDK only to Gradle subprocess)
        build_env = os.environ.copy()
        if java_info.get("path") and java_info["path"] != "PATH (system)":
            build_env["JAVA_HOME"] = java_info["path"]
            # Prepend selected Java bin to PATH for the subprocess
            java_bin = str(Path(java_info["path"]) / "bin")
            build_env["PATH"] = f"{java_bin}{os.pathsep}{build_env.get('PATH', '')}"

        if sdk_info.get("path"):
            build_env["ANDROID_HOME"] = sdk_info["path"]
            build_env["ANDROID_SDK_ROOT"] = sdk_info["path"]

        # Prevent daemon locks in temporary project and use plain console output for real-time unbuffered streaming
        cmd = gradle_cmd + ["assembleDebug", "--no-daemon", "--stacktrace", "--console=plain"]

        log(f"[BUILD] Launching: {' '.join(cmd)}")
        log("-" * 60)

        try:
            process = subprocess.Popen(
                cmd,
                cwd=str(project_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=build_env,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            # Stream logs line-by-line
            while True:
                if cancel_check and cancel_check():
                    process.terminate()
                    log("\n[CANCELLED] Build was cancelled by user.")
                    return False, None, "Build cancelled by user."

                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    log(line.rstrip())

            return_code = process.wait()
            log("-" * 60)
            log(f"[GRADLE] Exit Code: {return_code}")

            if return_code != 0:
                err_msg = f"Gradle build failed with exit code {return_code}."
                log(f"\n[ERROR] {err_msg}")
                return False, None, err_msg

            # 5. Locate produced APK
            apk_source = self._find_built_apk(project_dir)
            if not apk_source or not apk_source.exists():
                err_msg = "Build completed but APK artifact could not be located in build outputs."
                log(f"\n[ERROR] {err_msg}")
                return False, None, err_msg

            # 6. Copy APK to destination folder with clean sanitized name
            from .package_generator import PackageGenerator
            final_filename = PackageGenerator.sanitize_filename(app_name)
            destination_apk = self.output_dir / final_filename

            shutil.copy2(apk_source, destination_apk)
            log(f"[SUCCESS] APK generated: {destination_apk}")
            log(f"[SIZE] File size: {destination_apk.stat().st_size / (1024 * 1024):.2f} MB")
            log("=" * 60)

            return True, str(destination_apk), ""

        except Exception as e:
            err = f"Subprocess build exception: {str(e)}"
            log(f"\n[EXCEPTION] {err}")
            return False, None, err

    def _write_local_properties(self, project_dir: Path, sdk_path: str):
        """Creates local.properties specifying sdk.dir."""
        local_props = project_dir / "local.properties"
        # Format path with forward slashes or escaped backslashes for gradle
        sanitized_sdk_path = sdk_path.replace("\\", "/")
        content = f"sdk.dir={sanitized_sdk_path}\n"
        local_props.write_text(content, encoding="utf-8")

    def _resolve_gradle_command(self, project_dir: Path) -> List[str]:
        """Resolves whether to use gradlew.bat, ./gradlew, or system gradle."""
        is_windows = sys.platform == "win32"
        wrapper_bat = project_dir / "gradlew.bat"
        wrapper_sh = project_dir / "gradlew"
        wrapper_jar = project_dir / "gradle" / "wrapper" / "gradle-wrapper.jar"
        has_wrapper_jar = wrapper_jar.exists()

        if is_windows and wrapper_bat.exists() and has_wrapper_jar:
            return [str(wrapper_bat)]
        elif not is_windows and wrapper_sh.exists() and has_wrapper_jar:
            try:
                wrapper_sh.chmod(0o755)
            except Exception:
                pass
            return [str(wrapper_sh)]

        # Check system gradle in PATH or /opt/gradle
        sys_gradle = shutil.which("gradle")
        if sys_gradle:
            return [sys_gradle]

        for cand in ["/opt/gradle/gradle-9.3.1/bin/gradle", "/opt/gradle/bin/gradle"]:
            if Path(cand).exists():
                return [cand]

        return [str(wrapper_bat if is_windows else wrapper_sh)]

    def _find_built_apk(self, project_dir: Path) -> Optional[Path]:
        """Searches project directory for generated debug or release APK."""
        search_dirs = [
            project_dir / "app" / "build" / "outputs" / "apk" / "debug",
            project_dir / "app" / "build" / "outputs" / "apk" / "release",
            project_dir / "app" / "build" / "outputs" / "apk",
        ]

        for d in search_dirs:
            if d.exists():
                for f in d.glob("*.apk"):
                    return f

        # Fallback recursive search
        for f in (project_dir / "app" / "build").rglob("*.apk"):
            return f

        return None
