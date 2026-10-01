"""Valida o inicializador pelo cmd.exe, inclusive em caminhos com espaços."""
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def test_batch_has_windows_line_endings_and_no_bom(self):
        content = (ROOT / "Abrir agenda.bat").read_bytes()
        self.assertFalse(content.startswith(b"\xef\xbb\xbf"))
        self.assertIn(b"\r\n", content)
        self.assertNotIn(b"\n", content.replace(b"\r\n", b""))

    def run_launcher(self, environment=None, arguments=()):
        with TemporaryDirectory(prefix="agenda launcher ") as folder:
            temporary = Path(folder)
            project = temporary / "Projeto com espacos"
            project.mkdir()
            launcher = project / "Abrir agenda.bat"
            launcher.write_bytes((ROOT / launcher.name).read_bytes())
            # Substitui apenas o aplicativo no ambiente temporário: nunca abre
            # navegador, servidor ou banco de uso durante este teste.
            (project / "app.py").write_text(
                "from pathlib import Path\n"
                "import sys\n"
                "assert Path.cwd() == Path(__file__).resolve().parent\n"
                "print('AGENDA_LAUNCHER_OK')\n"
                "print(repr(sys.argv[1:]))\n", encoding="utf-8"
            )
            command = subprocess.list2cmdline([str(launcher), *arguments])
            command_line = f'"{os.environ.get("COMSPEC", "cmd.exe")}" /d /s /c "{command}"'
            result = subprocess.run(
                command_line,
                cwd=temporary, env=environment, input=b"\r\n", capture_output=True, timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            self.assertIn(b"AGENDA_LAUNCHER_OK", result.stdout)
            self.assertEqual(result.stderr, b"")
            return result

    @unittest.skipUnless(os.name == "nt", "Inicializador específico do Windows")
    def test_cmd_launches_python_from_another_directory(self):
        self.run_launcher()

    @unittest.skipUnless(os.name == "nt", "Inicializador específico do Windows")
    def test_python_directory_with_doubled_path_separators(self):
        environment = dict(os.environ)
        environment["PATH"] = str(Path(sys.executable).parent).replace("\\", "\\\\") + ";" + os.environ["SystemRoot"] + "\\System32"
        self.run_launcher(environment=environment)

    @unittest.skipUnless(os.name == "nt", "Inicializador específico do Windows")
    def test_installed_python_is_found_without_python_on_path(self):
        local = Path(os.environ["LOCALAPPDATA"])
        installations = list((local / "Python").glob("pythoncore-*/python.exe")) + list((local / "Programs" / "Python").glob("Python*/python.exe"))
        if not installations:
            self.skipTest("Requer uma instalação padrão de Python no perfil do Windows")
        environment = dict(os.environ)
        environment["PATH"] = os.environ["SystemRoot"] + "\\System32"
        self.run_launcher(environment=environment)

    @unittest.skipUnless(os.name == "nt", "Inicializador específico do Windows")
    def test_arguments_are_forwarded_to_app(self):
        result = self.run_launcher(arguments=("--no-browser", "--database", "banco temporario.sqlite3"))
        self.assertIn(b"['--no-browser', '--database', 'banco temporario.sqlite3']", result.stdout)


if __name__ == "__main__":
    unittest.main()
