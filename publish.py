#!/usr/bin/env python3
"""
Publicador de Stories no Instagram via Graph API (usa curl).
Suporta IMAGEM (jpg/png) e VIDEO (mp4) — Suprema Pizza posta os dois.

Uso:
  python3 publish.py next                  # mostra a grade (nao posta)
  python3 publish.py dry                    # mostra o que postaria AGORA (nao posta)
  python3 publish.py test <url>             # publica 1 story manual (validacao)
  python3 publish.py run                    # publica os stories devidos AGORA (cron)

Token: env IG_TOKEN (preferido) ou ./.token  (nunca commitar)
IG_ID: env IG_ID ou schedule.json
"""
import os, sys, json, time, subprocess
from datetime import datetime, timezone, timedelta

GRAPH = "https://graph.facebook.com/v21.0"
HERE = os.path.dirname(os.path.abspath(__file__))
SP_TZ = timezone(timedelta(hours=-3))  # America/Sao_Paulo (BR nao tem mais horario de verao)
DOW = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

def load_cfg(): return json.load(open(os.path.join(HERE, "schedule.json")))

def get_token():
    t = os.environ.get("IG_TOKEN")
    if t: return t.strip()
    p = os.path.join(HERE, ".token")
    if os.path.exists(p): return open(p).read().strip()
    raise SystemExit("Sem token: defina IG_TOKEN ou crie .token")

def _run(args):
    r = subprocess.run(["curl", "-s", "--max-time", "120"] + args, capture_output=True, text=True)
    try: d = json.loads(r.stdout)
    except Exception: raise RuntimeError(f"resposta nao-JSON: {r.stdout[:300]} | {r.stderr[:150]}")
    if isinstance(d, dict) and d.get("error"):
        e = d["error"]; raise RuntimeError(f"API erro: {e.get('message')} (code {e.get('code')})")
    return d

def _get(url): return _run([url])
def _post(url, data):
    args = [url]
    for k, v in data.items(): args += ["--data-urlencode", f"{k}={v}"]
    return _run(args)

def kind_of(url_or_file):
    ext = url_or_file.lower().rsplit(".", 1)[-1]
    return "image" if ext in ("jpg", "jpeg", "png") else "video"

def publish_story(ig_id, token, url, kind=None):
    kind = kind or kind_of(url)
    params = {"media_type": "STORIES", "access_token": token}
    params["image_url" if kind == "image" else "video_url"] = url
    c = _post(f"{GRAPH}/{ig_id}/media", params)
    cid = c["id"]
    # poll do container ate FINISHED (imagem costuma ficar pronta na hora; video leva alguns s)
    for _ in range(48):
        st = _get(f"{GRAPH}/{cid}?fields=status_code&access_token={token}")
        sc = st.get("status_code")
        if sc == "FINISHED": break
        if sc == "ERROR": raise RuntimeError(f"container ERROR: {st}")
        time.sleep(5)
    else:
        raise TimeoutError("container nao ficou pronto")
    return _post(f"{GRAPH}/{ig_id}/media_publish", {"creation_id": cid, "access_token": token}).get("id")

def url_for(cfg, it): return it.get("url") or f"{cfg['base_url']}/{it['file']}"
def _sp(): return os.path.join(HERE, "posted-log.json")
def _load(): return json.load(open(_sp())) if os.path.exists(_sp()) else {}
def _save(s): json.dump(s, open(_sp(), "w"), indent=2, ensure_ascii=False)
def _stp(): return os.path.join(HERE, "status.json")
def _stload(): return json.load(open(_stp())) if os.path.exists(_stp()) else {}
def _stsave(s): json.dump(s, open(_stp(), "w"), indent=2, ensure_ascii=False)

BEFORE_MIN = 5    # tolerancia antes do horario
AFTER_MIN = 45    # catch-up: posta ate 45min DEPOIS do horario (absorve atraso/skip do cron do GitHub)
def _due_now(cfg):
    now = datetime.now(SP_TZ); today = DOW[now.weekday()]
    out = []
    for it in cfg["schedule"]:
        if it["dow"] != today: continue
        hh, mm = map(int, it["time"].split(":"))
        sched = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        delta = (now - sched).total_seconds()/60   # >0 = depois do horario
        if -BEFORE_MIN <= delta <= AFTER_MIN:
            out.append(it)
    return now, today, out

def cmd_next(cfg):
    now = datetime.now(SP_TZ); print(f"Agora (SP): {now:%a %H:%M}\nGrade ({len(cfg['schedule'])} stories/semana):")
    for it in cfg["schedule"]:
        print(f"  {it['dow']} {it['time']}  [{kind_of(it.get('file',it.get('url','')))[:3]}]  {it['file']}")

def cmd_dry(cfg):
    now, today, due = _due_now(cfg)
    print(f"Agora (SP): {now:%a %H:%M} | hoje={today}")
    if not due: print(f"DRY: nada devido (janela -{BEFORE_MIN}min/+{AFTER_MIN}min)."); return
    for it in due:
        print(f"DRY: postaria [{kind_of(url_for(cfg,it))}] {it['file']}  ->  {url_for(cfg,it)}")

def cmd_run(cfg):
    token = get_token(); ig_id = os.environ.get("IG_ID") or cfg["ig_id"]
    now, today, due = _due_now(cfg); key_day = now.strftime("%Y-%m-%d")
    state = _load(); done = set(state.get(key_day, [])); posted = []; errs = []
    status = _stload(); day_st = status.get(key_day, {}); changed = False
    for it in due:
        key = f"{it['time']}-{it['file']}"
        if key in done: continue
        try:
            pid = publish_story(ig_id, token, url_for(cfg, it))
            print(f"OK {it['file']} -> {pid}"); done.add(key); posted.append(it['file'])
            day_st[key] = {"state": "posted", "id": pid, "at": now.strftime("%H:%M")}; changed = True
        except Exception as e:
            print(f"ERRO {it['file']}: {e}", file=sys.stderr)
            day_st[key] = {"state": "error", "msg": str(e)[:200], "at": now.strftime("%H:%M")}; changed = True
            errs.append(f"{it['file']}: {str(e)[:120]}")
    if posted: state[key_day] = sorted(done); _save(state)
    if changed: status[key_day] = day_st; _stsave(status)
    if not posted and not errs: print("nada novo postado nesta janela.")
    if errs:
        # falha ALTA: marca a Action vermelha + dispara alerta de email (no workflow)
        print("::error::Suprema stories FALHARAM: " + " | ".join(errs))
        sys.exit(1)

def cmd_test(cfg, url):
    token = get_token(); ig_id = os.environ.get("IG_ID") or cfg["ig_id"]
    print(f"Publicando teste em IG {ig_id}:\n  {url}")
    print(f"OK! story id = {publish_story(ig_id, token, url)}")

if __name__ == "__main__":
    cfg = load_cfg(); cmd = sys.argv[1] if len(sys.argv) > 1 else "next"
    if cmd == "test": cmd_test(cfg, sys.argv[2])
    elif cmd == "run": cmd_run(cfg)
    elif cmd == "dry": cmd_dry(cfg)
    else: cmd_next(cfg)
