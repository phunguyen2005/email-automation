from jinja2 import StrictUndefined, meta
from jinja2.sandbox import SandboxedEnvironment


ENV = SandboxedEnvironment(undefined=StrictUndefined, autoescape=False)


def render_template(template: str, row: dict, columns: list[str]) -> str:
    if not template.strip():
        raise ValueError("Nội dung hoặc tiêu đề đang trống.")
    parsed = ENV.parse(template)
    unknown = meta.find_undeclared_variables(parsed) - set(columns) - {"row"}
    if unknown:
        raise ValueError("Biến không tồn tại: " + ", ".join(sorted(unknown)))
    missing = [key for key in meta.find_undeclared_variables(parsed) if key != "row" and str(row.get(key, "")).strip() == ""]
    if missing:
        raise ValueError("Biến không có giá trị: " + ", ".join(sorted(missing)))
    return ENV.from_string(template).render(**{**row, "row": row})
