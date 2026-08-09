"""
Waynis AI — Turso (libsql) cloud persistence.

Ruajtja PËRGJITHMONË e tregtive/balancës në një databazë falas në internet.
Përdor vetëm urllib (asnjë varësi ekstra) dhe API-në HTTP të Turso-s
(/v2/pipeline). Nëse Turso nuk është i arritshëm, boti vazhdon lokalisht
(offline) dhe ri-sinkronizon në goditjen tjetër të suksesshme.
"""
import json
import os
import urllib.request


def _creds():
    url = (os.environ.get("TURSO_URL") or "").strip()
    token = (os.environ.get("TURSO_TOKEN") or "").strip()
    if not url or not token:
        try:
            base = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(base, "turso.json"), "r", encoding="utf-8") as f:
                d = json.load(f)
            url = url or str(d.get("url", "")).strip()
            token = token or str(d.get("token", "")).strip()
        except Exception:
            pass
    return url, token


def enabled():
    u, t = _creds()
    return bool(u and t)


def _request(sql, args, want_rows):
    u, t = _creds()
    host = u.split("://", 1)[-1].rstrip("/")
    payload = {
        "requests": [{"type": "execute",
                      "stmt": {"sql": sql,
                               "args": [_cell(a) for a in (args or [])]}}],
        "mode": "rows" if want_rows else "write",
    }
    req = urllib.request.Request(
        "https://" + host + "/v2/pipeline",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + t, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def _val(cell):
    """Turso kthen qeliza si {'type':..,'value':..} ose vlera të thjeshta."""
    if isinstance(cell, dict):
        return cell.get("value")
    return cell


def _cell(v):
    """Kthen një vlerë Python në qelizën e etiketuar që kërkon API i Turso-s
    (p.sh. "text" → {'type':'text','value':...}). Pa këtë, API kthen 400."""
    if v is None:
        return {"type": "null"}
    if isinstance(v, bool):
        return {"type": "integer", "value": "1" if v else "0"}
    if isinstance(v, int):
        # Turso (libsql HTTP) i kodon int64-t si vargje ("5", jo 5) — pa këtë
        # kthen 400 "expected a borrowed string"
        return {"type": "integer", "value": str(v)}
    if isinstance(v, float):
        return {"type": "float", "value": v}
    if isinstance(v, (bytes, bytearray)):
        return {"type": "blob", "value": v.decode("utf-8", "replace")}
    return {"type": "text", "value": str(v)}


def query(sql, args=None):
    """Kthen lista rreshtash (tupla) ose [] nëse dështon/pa kredenciale."""
    if not enabled():
        return []
    try:
        out = _request(sql, args, True)
    except Exception:
        return []
    rows = []
    for res in out.get("results", []):
        if res.get("type") != "ok":
            continue
        rr = res.get("response", {}).get("result", {})
        for row in rr.get("rows", []):
            # Turso kthen rreshta si lista qelizash; në disa versione
            # si {'row': [...]} — i përballojmë të dyja
            if isinstance(row, dict) and "row" in row:
                row = row["row"]
            rows.append(tuple(_val(c) for c in row))
    return rows


def exec_sql(sql, args=None):
    """Ekzekuton një INSERT/UPDATE/DELETE/DDL. True nëse shkoi mirë."""
    if not enabled():
        return False
    try:
        _request(sql, args, False)
        return True
    except Exception:
        return False


def batch_exec(items):
    """Ekzekuton shumë deklarata në NJË kërkesë HTTP (pipeline)."""
    if not enabled() or not items:
        return False
    u, t = _creds()
    host = u.split("://", 1)[-1].rstrip("/")
    reqs = [{"type": "execute",
             "stmt": {"sql": s, "args": [_cell(x) for x in (a or [])]}}
            for s, a in items]
    payload = {"requests": reqs, "mode": "write"}
    try:
        req = urllib.request.Request(
            "https://" + host + "/v2/pipeline",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": "Bearer " + t,
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return True
    except Exception:
        return False
