from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from http.client import HTTPConnection
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from http.server import ThreadingHTTPServer
import zipfile

from app import make_handler
from database import Store, TEMPLATES, UserError, normalize_phone
from importing import preview_import


def xlsx_fixture(rows, shared=False, formula=False):
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Contatos" sheetId="1" r:id="rId7"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId7" Target="worksheets/contacts.xml"/></Relationships>')
        values = ["Nome", "Telefone", "Observação", "Joana Souza", "Prefere manhã"]
        if shared:
            archive.writestr("xl/sharedStrings.xml", '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' + "".join(f"<si><t>{value}</t></si>" for value in values) + "</sst>")
        body = '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        for index, row in enumerate(rows, start=1):
            body += f'<row r="{index}">'
            for col, value in enumerate(row):
                ref = f"{chr(65 + col)}{index}"
                if formula and index == 2 and col == 1:
                    body += f'<c r="{ref}"><f>SUM(1,2)</f><v>11999990000</v></c>'
                elif isinstance(value, (int, float)):
                    body += f'<c r="{ref}"><v>{value}</v></c>'
                elif shared and value in values:
                    body += f'<c r="{ref}" t="s"><v>{values.index(value)}</v></c>'
                else:
                    body += f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>'
            body += '</row>'
        body += '</sheetData></worksheet>'
        archive.writestr("xl/worksheets/contacts.xml", body)
    return output.getvalue()


class AgendaTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.path = Path(self.temporary.name) / "test.sqlite3"
        self.store = Store(self.path)
        self.day = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")

    def tearDown(self):
        self.temporary.cleanup()

    def person(self, name="Maria Silva", phone="(11) 99999-0000"):
        return self.store.create_person({"name": name, "phone": phone, "notes": "Contato fictício"})["id"]

    def slots(self):
        return self.store.add_slots({"date": self.day, "times": ["08:00", "08:30", "09:00"]})

    def get(self, person_id):
        return next(person for person in self.store.state()["people"] if person["id"] == person_id)

    def test_full_flow_and_persistence(self):
        self.slots()
        person_id = self.person()
        self.store.person_action(person_id, "suggest")
        person = self.get(person_id)
        self.assertIn("Maria Silva", person["message"])
        self.assertIn("08:00", person["message"])
        self.assertIsNone(person["last_contact"])
        self.assertFalse(any(slot["person_id"] for slot in self.store.state()["slots"]))
        self.store.person_action(person_id, "sent")
        self.assertEqual(self.get(person_id)["status"], "aguardando")
        self.assertIsNotNone(self.get(person_id)["last_contact"])
        self.store.person_action(person_id, "next")
        self.assertIn("08:30", self.get(person_id)["message"])
        self.assertTrue(self.get(person_id)["message"].startswith("Sem problemas!"))
        self.store.person_action(person_id, "confirm")
        persisted = Store(self.path).state()
        person = persisted["people"][0]
        self.assertEqual(person["status"], "agendado")
        self.assertIn("Perfeito!", person["message"])
        self.assertEqual(person["booked"]["person_id"], person_id)

    def test_concurrent_accepts_only_one_reservation(self):
        self.slots()
        people = [self.person("Maria"), self.person("Joana")]
        for person_id in people:
            self.store.person_action(person_id, "suggest")
        def accept(person_id):
            try:
                self.store.person_action(person_id, "confirm")
                return "ok"
            except UserError as exc:
                return exc.status
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(accept, people))
        self.assertCountEqual(results, ["ok", 409])
        self.assertEqual(sum(bool(slot["person_id"]) for slot in self.store.state()["slots"]), 1)
        loser = next(p for p in self.store.state()["people"] if not p["booked"])
        self.store.person_action(loser["id"], "next")
        self.store.person_action(loser["id"], "confirm")
        self.assertIn("08:30", self.get(loser["id"])["message"])

    def test_next_skips_reserved_and_does_not_wrap(self):
        self.slots()
        maria = self.person("Maria")
        joana = self.person("Joana")
        self.store.person_action(maria, "suggest")
        self.store.person_action(joana, "suggest")
        self.store.person_action(joana, "next")
        self.store.person_action(joana, "confirm")
        self.store.person_action(maria, "next")
        self.assertIn("09:00", self.get(maria)["message"])
        with self.assertRaises(UserError):
            self.store.person_action(maria, "next")
        self.assertIn("09:00", self.get(maria)["message"])

    def test_overdue_only_waiting_and_call_queue(self):
        self.slots()
        maria = self.person()
        self.store.person_action(maria, "suggest")
        self.store.person_action(maria, "sent")
        old = (datetime.now().astimezone() - timedelta(days=3)).isoformat()
        with self.store.connection(write=True) as db:
            db.execute("UPDATE people SET last_contact=? WHERE id=?", (old, maria))
        self.assertTrue(self.get(maria)["overdue"])
        self.store.person_action(maria, "flag-call")
        self.assertFalse(self.get(maria)["overdue"])
        self.store.person_action(maria, "no-answer")
        self.assertEqual(self.get(maria)["status"], "ligar")
        self.assertGreater(self.get(maria)["last_contact"], old)
        self.store.person_action(maria, "call-done")
        self.assertEqual(self.get(maria)["status"], "finalizado")

    def test_cancel_finalize_and_delete_reservations(self):
        self.slots()
        maria = self.person()
        self.store.person_action(maria, "suggest")
        self.store.person_action(maria, "confirm")
        reserved = self.get(maria)["booked_slot_id"]
        with self.assertRaises(UserError):
            self.store.delete_slot(reserved)
        self.store.person_action(maria, "finalize")
        self.assertEqual(self.get(maria)["booked_slot_id"], reserved)
        self.store.person_action(maria, "cancel")
        self.assertIsNone(self.get(maria)["booked"])
        self.store.person_action(maria, "suggest")
        self.store.person_action(maria, "confirm")
        self.store.person_action(maria, "delete")
        self.assertFalse(any(slot["person_id"] for slot in self.store.state()["slots"]))

    def test_deleting_suggestion_clears_message(self):
        self.slots()
        maria = self.person()
        self.store.person_action(maria, "suggest")
        self.store.delete_slot(self.get(maria)["suggested_slot_id"])
        self.assertIsNone(self.get(maria)["suggested"])
        self.assertEqual(self.get(maria)["message"], "")

    def test_reject_past_slots_and_confirmations(self):
        with self.assertRaises(UserError):
            self.store.add_slots({"date": "2020-01-01", "times": ["08:00"]})
        self.slots()
        maria = self.person()
        self.store.person_action(maria, "suggest")
        with self.store.connection(write=True) as db:
            db.execute("UPDATE slots SET starts='2020-01-01T08:00:00' WHERE id=?", (self.get(maria)["suggested_slot_id"],))
        with self.assertRaises(UserError):
            self.store.person_action(maria, "confirm")
        self.store.person_action(maria, "next")
        self.assertIn("08:30", self.get(maria)["message"])

    def test_batch_invalid_date_is_atomic_and_duplicates_ignored(self):
        with self.assertRaises(UserError):
            self.store.add_slots({"date": self.day, "times": ["08:00", "25:00"]})
        self.assertEqual(self.store.state()["slots"], [])
        self.slots()
        self.assertEqual(self.slots()["added"], 0)

    def test_edit_cannot_fabricate_reservation_or_contact(self):
        maria = self.person()
        data = {"name": "Maria", "phone": "11999990000", "status": "agendado"}
        with self.assertRaises(UserError):
            self.store.edit_person(maria, data)
        data["status"] = "aguardando"
        with self.assertRaises(UserError):
            self.store.edit_person(maria, data)

    def test_message_templates_and_literal_names(self):
        self.slots()
        maria = self.person("Maria {{data}}")
        self.store.person_action(maria, "suggest")
        self.store.save_settings({"wait_days": 1, **TEMPLATES, "first": "{{nome}}: {{data}} às {{horario}}"})
        self.assertTrue(self.get(maria)["message"].startswith("Maria {{data}}:"))
        self.assertEqual(Store(self.path).state()["settings"]["wait_days"], 1)
        with self.assertRaises(UserError):
            self.store.save_settings({"wait_days": 1, **TEMPLATES, "first": "{{cpf}}"})

    def test_phone_international_format(self):
        self.assertEqual(normalize_phone("(11) 99999-0000"), "5511999990000")
        self.assertEqual(normalize_phone("+1 (212) 555-0123"), "12125550123")
        self.assertEqual(normalize_phone("0055 11 99999-0000"), "5511999990000")
        for value in ("123", "telefone", "١١٩٩٩٩٩٠٠٠٠"):
            with self.assertRaises(UserError):
                normalize_phone(value)

    def test_csv_preview_deduplicates_and_reports_errors(self):
        self.person()
        raw = ("Nome;Telefone;Observação\nMaria Silva;11999990000;Não sobrescrever\n"
               "Joana;11999990000;Compartilha telefone\nJOÁNA;11999990000;Duplicada\n"
               "Sem telefone;;Inválida\nJosé;21988887777;Prefere tarde\n").encode("utf-8-sig")
        result = preview_import("contatos.csv", raw, self.store.state()["people"])
        self.assertEqual(result["duplicates"], 2)
        self.assertEqual(result["error_count"], 1)
        self.assertEqual(result["errors"][0]["line"], 5)
        self.assertEqual(len(result["rows"]), 2)
        self.assertEqual(self.store.import_people(result["rows"])["added"], 2)
        self.assertEqual(self.store.import_people(result["rows"])["added"], 0)
        self.assertEqual(self.get(1)["notes"], "Contato fictício")

    def test_csv_comma_and_windows_encoding(self):
        raw = 'Nome,Telefone,Observação\n"José, da Silva",21999998888,"Um texto, com vírgula"\n'.encode("cp1252")
        result = preview_import("lista.csv", raw, [])
        self.assertEqual(result["rows"][0]["name"], "José, da Silva")
        self.assertEqual(result["rows"][0]["notes"], "Um texto, com vírgula")

    def test_xlsx_shared_inline_and_numeric_phone(self):
        for shared in (False, True):
            rows = [["Nome", "Telefone", "Observação"], ["Joana Souza", 11999990000, "Prefere manhã"]]
            result = preview_import("lista.xlsx", xlsx_fixture(rows, shared), [])
            self.assertEqual(result["rows"][0]["phone"], "5511999990000")
            self.assertEqual(result["rows"][0]["notes"], "Prefere manhã")

    def test_xlsx_does_not_execute_formulas(self):
        result = preview_import("lista.xlsx", xlsx_fixture([["Nome", "Telefone"], ["Joana", 11999990000]], formula=True), [])
        self.assertEqual(result["rows"], [])
        self.assertEqual(result["error_count"], 1)

    def test_invalid_import_does_not_partially_save(self):
        with self.assertRaises(UserError):
            self.store.import_people([{"name": "Joana", "phone": "11999990000"}, {"name": "", "phone": "123"}])
        self.assertEqual(self.store.state()["people"], [])
        for name, raw in (("bad.xlsx", b"not a zip"), ("bad.csv", b"Nome;Outra coluna\nJoana;123")):
            with self.assertRaises(UserError):
                preview_import(name, raw, [])


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        cls.store = Store(Path(cls.temporary.name) / "http.sqlite3")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cls.store))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temporary.cleanup()

    def request(self, method, path, data=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.port, timeout=5)
        connection.request(method, path, json.dumps(data) if data is not None else None, headers or {})
        response = connection.getresponse()
        status, content = response.status, response.read()
        connection.close()
        return status, content

    def test_http_flow_and_local_origin_guard(self):
        status, content = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("Agenda de contatos".encode(), content)
        for path in ("/app.js", "/styles.css", "/favicon.svg", "/modelo.csv", "/api/state"):
            self.assertEqual(self.request("GET", path)[0], 200)
        self.assertEqual(self.request("GET", "/database.py")[0], 404)
        self.assertEqual(self.request("GET", "/api/state", headers={"Host": "evil.example"})[0], 403)
        data = {"name": "Contato fictício HTTP", "phone": "11999990000"}
        headers = {"Content-Type": "application/json", "X-Local-App": "1", "Origin": f"http://127.0.0.1:{self.port}"}
        self.assertEqual(self.request("POST", "/api/people", data)[0], 403)
        self.assertEqual(self.request("POST", "/api/people", data, {**headers, "Origin": "https://evil.example"})[0], 403)
        status, content = self.request("POST", "/api/people", data, headers)
        self.assertEqual(status, 200)
        person_id = json.loads(content)["id"]
        self.assertEqual(self.request("POST", f"/api/people/{person_id}/flag-call", {}, headers)[0], 200)
        self.assertEqual(self.store.state()["people"][0]["status"], "ligar")


if __name__ == "__main__":
    unittest.main()
