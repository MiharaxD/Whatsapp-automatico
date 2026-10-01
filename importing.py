"""Leitura local de CSV e da primeira aba de XLSX, sem executar fórmulas."""
import csv
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from pathlib import PurePosixPath
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET

from database import UserError, person_fields, search_key

MAX_FILE = 8 * 1024 * 1024
MAX_ROWS = 10000
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def csv_rows(raw):
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            content = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise UserError("Não foi possível ler o CSV. Salve como CSV UTF-8.")
    try:
        dialect = csv.Sniffer().sniff(content[:8192], delimiters=",;\t")
        reader = csv.reader(StringIO(content, newline=""), dialect)
    except csv.Error:
        delimiter = ";" if ";" in content.partition("\n")[0] else ","
        reader = csv.reader(StringIO(content, newline=""), delimiter=delimiter)
    try:
        for row in reader:
            yield row
    except csv.Error as exc:
        raise UserError("CSV inválido. Confira aspas e separadores.") from exc


def xlsx_rows(raw):
    try:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            # Limita a descompressão antes de ler qualquer XML.
            if sum(info.file_size for info in archive.infolist()) > 40 * 1024 * 1024:
                raise UserError("XLSX muito grande após descompressão. Divida a planilha.")
            def xml(path):
                content = archive.read(path)
                if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
                    raise UserError("Esse arquivo contém estruturas XML não suportadas.")
                return ET.fromstring(content)
            shared = []
            if "xl/sharedStrings.xml" in archive.namelist():
                shared = ["".join(item.itertext()) if not item.findall(".//s:t", NS)
                          else "".join(t.text or "" for t in item.findall(".//s:t", NS))
                          for item in xml("xl/sharedStrings.xml").findall("s:si", NS)]
            workbook = xml("xl/workbook.xml")
            sheet = workbook.find("s:sheets/s:sheet", NS)
            if sheet is None:
                raise UserError("A planilha não tem abas.")
            relationship_id = sheet.get(f"{{{REL}}}id")
            target = next((rel.get("Target") for rel in xml("xl/_rels/workbook.xml.rels")
                           if rel.get("Id") == relationship_id and rel.get("TargetMode") != "External"), None)
            if not target:
                raise UserError("Não foi possível localizar a primeira aba.")
            path = posixpath.normpath(target.lstrip("/") if target.startswith("/") else "xl/" + target)
            if not path.startswith("xl/") or ".." in PurePosixPath(path).parts:
                raise UserError("Caminho de aba inválido no XLSX.")
            for row in xml(path).findall("s:sheetData/s:row", NS):
                cells = {}
                for cell in row.findall("s:c", NS):
                    ref = cell.get("r", "")
                    match = re.match(r"^([A-Z]+)\d+$", ref)
                    if not match:
                        raise UserError("Referência de célula inválida no XLSX.")
                    index = 0
                    for char in match[1]:
                        index = index * 26 + ord(char) - 64
                    if index > 256:
                        raise UserError("Use uma planilha de contatos com até 256 colunas.")
                    if cell.find("s:f", NS) is not None:
                        value = ""  # Fórmulas não são executadas; valores de contato devem ser literais.
                    elif cell.get("t") == "inlineStr":
                        value = "".join(t.text or "" for t in cell.findall(".//s:t", NS))
                    else:
                        value = cell.findtext("s:v", "", NS)
                        if cell.get("t") == "s":
                            value = shared[int(value)]
                        elif cell.get("t") in (None, "n") and value:
                            try:
                                number = Decimal(value)
                                if number.is_finite() and number.adjusted() <= 30 and number == number.to_integral_value():
                                    value = str(int(number))
                            except InvalidOperation:
                                pass
                    cells[index - 1] = value
                yield [cells.get(i, "") for i in range(max(cells, default=-1) + 1)]
    except (zipfile.BadZipFile, KeyError, ET.ParseError, IndexError, ValueError, RuntimeError, OSError) as exc:
        raise UserError("XLSX inválido ou protegido. Salve uma planilha .xlsx comum e tente novamente.") from exc


def preview_import(filename, raw, existing):
    if not raw or len(raw) > MAX_FILE:
        raise UserError("Escolha um arquivo CSV/XLSX de até 8 MB.")
    extension = filename.rsplit(".", 1)[-1].lower()
    if extension not in ("csv", "xlsx"):
        raise UserError("Use um arquivo .csv ou .xlsx.")
    iterator = iter(csv_rows(raw) if extension == "csv" else xlsx_rows(raw))
    header = next((row for row in iterator if any(str(value).strip() for value in row)), None)
    if header is None:
        raise UserError("O arquivo está vazio.")
    aliases = {"nome": "name", "name": "name", "telefone": "phone", "phone": "phone",
               "celular": "phone", "whatsapp": "phone", "observacao": "notes", "observacoes": "notes", "notes": "notes"}
    fields = {}
    for index, value in enumerate(header):
        field = aliases.get(search_key(str(value)))
        if field and field not in fields:
            fields[field] = index
    if "name" not in fields or "phone" not in fields:
        raise UserError("A primeira linha precisa ter as colunas Nome e Telefone. Observação é opcional.")
    seen = {(search_key(person["name"]), person["phone"]) for person in existing}
    accepted, errors, duplicate_count, total = [], [], 0, 0
    for line, row in enumerate(iterator, start=2):
        if not any(str(value).strip() for value in row):
            continue
        total += 1
        if total > MAX_ROWS:
            raise UserError("Importe no máximo 10.000 linhas por arquivo.")
        data = {key: str(row[index]) if index < len(row) else "" for key, index in fields.items()}
        try:
            name, phone, notes = person_fields(data)
        except UserError as exc:
            errors.append({"line": line, "message": str(exc)})
            continue
        key = (search_key(name), phone)
        if key in seen:
            duplicate_count += 1
            continue
        seen.add(key)
        accepted.append({"name": name, "phone": phone, "notes": notes})
    return {"rows": accepted, "errors": errors[:100], "error_count": len(errors),
            "duplicates": duplicate_count, "total": total}
