"""Regras da agenda pessoal. Apenas biblioteca padrão e SQLite."""
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
import re
import sqlite3
import unicodedata


STATUSES = ("nao_contatado", "aguardando", "agendado", "ligar", "finalizado")
TEMPLATES = {
    "first": "Olá, {{nome}}! Tudo bem?\n\nEstou entrando em contato sobre a atualização do seu Cadastro Único.\n\nTemos um horário disponível no dia {{data}} às {{horario}}.\n\nVocê consegue comparecer nesse dia e horário?",
    "alternative": "Sem problemas!\n\nO próximo horário disponível é dia {{data}} às {{horario}}.\n\nEsse horário funciona para você?",
    "confirmation": "Perfeito! Seu atendimento ficou agendado para dia {{data}} às {{horario}}.",
}


class UserError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def text_value(value, label, maximum, required=False):
    if not isinstance(value, str):
        raise UserError(f"{label}: informe um texto válido.")
    value = value.strip()
    if required and not value:
        raise UserError(f"Preencha {label.lower()}.")
    if len(value) > maximum:
        raise UserError(f"{label}: limite de {maximum} caracteres.")
    return value


def normalize_phone(value):
    value = text_value(value, "Telefone", 50, True)
    if re.search(r"[^0-9\s()+.\-]", value):
        raise UserError("Telefone inválido. Informe DDD + número ou +código do país.")
    digits = re.sub(r"[^0-9]", "", value)
    if digits.startswith("00"):
        digits = digits[2:]
    elif not value.startswith("+") and len(digits) in (10, 11):
        digits = "55" + digits
    if not 8 <= len(digits) <= 15 or digits.startswith("0"):
        raise UserError("Telefone inválido. Inclua o DDD; para outro país, use +código do país.")
    return digits


def person_fields(data):
    return (
        text_value(data.get("name", ""), "Nome", 180, True),
        normalize_phone(data.get("phone", "")),
        text_value(data.get("notes", ""), "Observação", 3000),
    )


def search_key(value):
    return " ".join("".join(c for c in unicodedata.normalize("NFKD", value.casefold())
                            if not unicodedata.combining(c)).split())


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS slots (
                    id INTEGER PRIMARY KEY,
                    starts TEXT NOT NULL UNIQUE
                );
                CREATE TABLE IF NOT EXISTS people (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'nao_contatado'
                        CHECK(status IN ('nao_contatado','aguardando','agendado','ligar','finalizado')),
                    last_contact TEXT,
                    suggested_slot_id INTEGER REFERENCES slots(id) ON DELETE SET NULL,
                    booked_slot_id INTEGER UNIQUE REFERENCES slots(id),
                    message_kind TEXT NOT NULL DEFAULT 'first'
                );
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)
            for key, value in {"wait_days": "2", **TEMPLATES}.items():
                db.execute("INSERT OR IGNORE INTO settings VALUES (?, ?)", (key, value))

    @contextmanager
    def connection(self, write=False):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def get_person(db, person_id):
        person = db.execute("SELECT * FROM people WHERE id=?", (person_id,)).fetchone()
        if not person:
            raise UserError("Essa pessoa não está mais na lista. Atualize a tela.", 404)
        return person

    def state(self):
        with self.connection() as db:
            settings = dict(db.execute("SELECT key, value FROM settings").fetchall())
            settings["wait_days"] = int(settings["wait_days"])
            slots = [dict(row) for row in db.execute("""
                SELECT s.*, p.id AS person_id, p.name AS person_name
                FROM slots s LEFT JOIN people p ON p.booked_slot_id=s.id ORDER BY s.starts
            """)]
            by_id = {slot["id"]: slot for slot in slots}
            people = []
            for row in db.execute("SELECT * FROM people ORDER BY name COLLATE NOCASE, id"):
                person = dict(row)
                person["suggested"] = by_id.get(person["suggested_slot_id"])
                person["booked"] = by_id.get(person["booked_slot_id"])
                person["overdue"] = (
                    person["status"] == "aguardando" and bool(person["last_contact"])
                    and datetime.fromisoformat(person["last_contact"]) <=
                    datetime.now().astimezone() - timedelta(days=settings["wait_days"])
                )
                slot = person["booked"] or person["suggested"]
                message = settings[person["message_kind"]] if slot else ""
                if slot:
                    when = datetime.fromisoformat(slot["starts"])
                    # Substituição única: nomes não são interpretados como variáveis do modelo.
                    values = {"nome": person["name"], "data": when.strftime("%d/%m"),
                              "horario": when.strftime("%H:%M")}
                    message = re.sub(r"\{\{(nome|data|horario)\}\}",
                                     lambda m: values[m.group(1)], message)
                person["message"] = message
                people.append(person)
            return {"people": people, "slots": slots, "settings": settings}

    def create_person(self, data):
        fields = person_fields(data)
        with self.connection(write=True) as db:
            cursor = db.execute("INSERT INTO people(name, phone, notes) VALUES (?,?,?)", fields)
            return {"id": cursor.lastrowid}

    def edit_person(self, person_id, data):
        fields = person_fields(data)
        status = data.get("status", "nao_contatado")
        if status not in STATUSES:
            raise UserError("Status inválido.")
        with self.connection(write=True) as db:
            person = self.get_person(db, person_id)
            if person["booked_slot_id"] and status not in ("agendado", "finalizado"):
                raise UserError("Cancele o agendamento antes de mudar para esse status.")
            if status == "agendado" and not person["booked_slot_id"]:
                raise UserError("Use Confirmar agendamento para reservar um horário.")
            if status == "aguardando" and not person["last_contact"]:
                raise UserError("Use Mensagem enviada para registrar o primeiro contato.")
            db.execute("UPDATE people SET name=?, phone=?, notes=?, status=? WHERE id=?",
                       (*fields, status, person_id))
        return {"id": person_id}

    def person_action(self, person_id, action):
        with self.connection(write=True) as db:
            person = self.get_person(db, person_id)
            now = datetime.now().isoformat(timespec="seconds")
            contacted = datetime.now().astimezone().isoformat(timespec="seconds")
            if action == "delete":
                db.execute("DELETE FROM people WHERE id=?", (person_id,))
            elif action in ("suggest", "next"):
                if person["booked_slot_id"]:
                    raise UserError("Esta pessoa já tem agendamento. Cancele-o antes de sugerir outro.")
                if person["status"] == "finalizado":
                    raise UserError("Reabra o contato em Editar antes de sugerir um horário.")
                previous = None
                if action == "next":
                    if not person["suggested_slot_id"]:
                        raise UserError("Sugira o primeiro horário antes de procurar o próximo.")
                    previous = db.execute("SELECT starts FROM slots WHERE id=?",
                                          (person["suggested_slot_id"],)).fetchone()
                slot = db.execute("""
                    SELECT s.* FROM slots s
                    WHERE s.starts > ? AND s.starts > ?
                    AND NOT EXISTS (SELECT 1 FROM people p WHERE p.booked_slot_id=s.id)
                    ORDER BY s.starts LIMIT 1
                """, (now, previous["starts"] if previous else "")).fetchone()
                if not slot:
                    raise UserError("Não há outro horário futuro disponível. Adicione horários na Agenda.", 409)
                db.execute("UPDATE people SET suggested_slot_id=?, message_kind=? WHERE id=?",
                           (slot["id"], "alternative" if action == "next" else "first", person_id))
            elif action == "confirm":
                if person["booked_slot_id"]:
                    raise UserError("Esta pessoa já tem um agendamento confirmado.", 409)
                if person["status"] == "finalizado":
                    raise UserError("Reabra o contato em Editar antes de confirmar um horário.")
                slot_id = person["suggested_slot_id"]
                slot = db.execute("SELECT * FROM slots WHERE id=?", (slot_id,)).fetchone()
                if not slot:
                    raise UserError("Sugira um horário antes de confirmar.")
                if slot["starts"] <= now:
                    raise UserError("Esse horário já passou. Sugira um novo horário.", 409)
                if db.execute("SELECT 1 FROM people WHERE booked_slot_id=?", (slot_id,)).fetchone():
                    raise UserError("Esse horário foi reservado por outra pessoa. Clique em Próximo horário.", 409)
                db.execute("""UPDATE people SET booked_slot_id=?, status='agendado',
                              message_kind='confirmation' WHERE id=?""", (slot_id, person_id))
            elif action == "sent":
                if not person["suggested_slot_id"] and not person["booked_slot_id"]:
                    raise UserError("Sugira um horário para preparar a mensagem.")
                status = person["status"] if person["booked_slot_id"] else "aguardando"
                if person["status"] == "finalizado":
                    raise UserError("Este contato está finalizado. Reabra-o em Editar.")
                db.execute("UPDATE people SET last_contact=?, status=? WHERE id=?",
                           (contacted, status, person_id))
            elif action == "flag-call":
                if person["booked_slot_id"]:
                    raise UserError("Esta pessoa já tem agendamento. Cancele-o antes de colocá-la na fila.")
                db.execute("UPDATE people SET status='ligar' WHERE id=?", (person_id,))
            elif action in ("call-done", "no-answer"):
                if person["status"] != "ligar":
                    raise UserError("Esta pessoa não está na fila de ligações.", 409)
                status = "finalizado" if action == "call-done" else "ligar"
                db.execute("UPDATE people SET last_contact=?, status=? WHERE id=?",
                           (contacted, status, person_id))
            elif action == "finalize":
                db.execute("UPDATE people SET status='finalizado' WHERE id=?", (person_id,))
            elif action == "cancel":
                if not person["booked_slot_id"]:
                    raise UserError("Esta pessoa não tem agendamento para cancelar.")
                db.execute("""UPDATE people SET booked_slot_id=NULL, suggested_slot_id=NULL,
                              status='nao_contatado', message_kind='first' WHERE id=?""", (person_id,))
            else:
                raise UserError("Ação desconhecida.", 404)
        return {"id": person_id}

    def add_slots(self, data):
        date = data.get("date", "")
        times = data.get("times", [])
        if not isinstance(date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise UserError("Escolha uma data válida.")
        if not isinstance(times, list) or not times or len(times) > 200:
            raise UserError("Informe de 1 a 200 horários.")
        starts = set()
        for time in times:
            if not isinstance(time, str) or not re.fullmatch(r"\d{2}:\d{2}", time):
                raise UserError("Use horários no formato HH:MM, um por linha.")
            try:
                when = datetime.fromisoformat(f"{date}T{time}:00")
            except ValueError as exc:
                raise UserError("Data ou horário inválido.") from exc
            if when <= datetime.now():
                raise UserError("Cadastre apenas horários futuros.")
            starts.add(when.isoformat(timespec="seconds"))
        with self.connection(write=True) as db:
            before = db.total_changes
            for start in sorted(starts):
                db.execute("INSERT OR IGNORE INTO slots(starts) VALUES (?)", (start,))
            return {"added": db.total_changes - before, "duplicates": len(times) - (db.total_changes - before)}

    def delete_slot(self, slot_id):
        with self.connection(write=True) as db:
            if db.execute("SELECT 1 FROM people WHERE booked_slot_id=?", (slot_id,)).fetchone():
                raise UserError("Esse horário está reservado. Cancele o agendamento primeiro.", 409)
            if not db.execute("SELECT 1 FROM slots WHERE id=?", (slot_id,)).fetchone():
                raise UserError("Horário não encontrado.", 404)
            # Excluir uma sugestão também limpa a mensagem associada.
            db.execute("UPDATE people SET message_kind='first' WHERE suggested_slot_id=?", (slot_id,))
            db.execute("DELETE FROM slots WHERE id=?", (slot_id,))
        return {}

    def save_settings(self, data):
        days = data.get("wait_days")
        if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 30:
            raise UserError("Escolha um prazo de 1 a 30 dias.")
        settings = {"wait_days": str(days)}
        for key in TEMPLATES:
            value = text_value(data.get(key, ""), "Modelo de mensagem", 4000, True)
            unknown = re.findall(r"\{\{([^{}]+)\}\}", value)
            if any(token not in ("nome", "data", "horario") for token in unknown):
                raise UserError("Use apenas as variáveis {{nome}}, {{data}} e {{horario}}.")
            settings[key] = value
        with self.connection(write=True) as db:
            db.executemany("UPDATE settings SET value=? WHERE key=?",
                           [(value, key) for key, value in settings.items()])
        return {}

    def import_people(self, rows):
        if not isinstance(rows, list) or len(rows) > 10000:
            raise UserError("Importe no máximo 10.000 pessoas por arquivo.")
        validated = [person_fields(row) for row in rows if isinstance(row, dict)]
        if len(validated) != len(rows):
            raise UserError("Lista de importação inválida.")
        added = 0
        with self.connection(write=True) as db:
            seen = {(search_key(p["name"]), p["phone"]) for p in db.execute("SELECT name, phone FROM people")}
            for name, phone, notes in validated:
                key = (search_key(name), phone)
                if key in seen:
                    continue
                db.execute("INSERT INTO people(name, phone, notes) VALUES (?,?,?)", (name, phone, notes))
                seen.add(key)
                added += 1
        return {"added": added, "duplicates": len(rows) - added}
