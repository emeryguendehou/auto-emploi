import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).parent.parent))

from . import config_editor as editor
from .config_editor import read_quotas
import scraper

app = FastAPI(title="Auto Alternance Dashboard")

BASE_DIR = Path(__file__).parent.parent
STATIC_DIR = BASE_DIR / "dashboard" / "static"
MAX_LOG_LINES = 200

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── Subprocess runner with SSE queue ──
log_queue: asyncio.Queue = asyncio.Queue()

run_state: dict = {
    "phase": None,
    "started_at": None,
    "status": "idle",
    "logs": [],
}


async def _run_phase(phase: str):
    global run_state, log_queue
    run_state["phase"] = phase
    run_state["started_at"] = datetime.now().strftime("%H:%M:%S")
    run_state["logs"] = []
    run_state["status"] = "running"

    await log_queue.put({"type": "clear", "data": {}})
    await log_queue.put({"type": "status", "data": {"status": "running", "phase": phase, "started_at": run_state["started_at"]}})

    try:
        cmd = [sys.executable, "-u", "main.py", "--phase", phase]
        loop = asyncio.get_event_loop()

        process = await loop.run_in_executor(
            None, lambda: subprocess.Popen(
                cmd, cwd=str(BASE_DIR),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
                encoding="utf-8", errors="replace",
            )
        )
        run_state["process"] = process

        while True:
            line = await loop.run_in_executor(None, process.stdout.readline)
            if not line:
                break
            stripped = line.rstrip()
            run_state["logs"].append(stripped)
            if len(run_state["logs"]) > MAX_LOG_LINES:
                run_state["logs"] = run_state["logs"][-MAX_LOG_LINES:]
            await log_queue.put({"type": "log", "data": stripped})

        await loop.run_in_executor(None, process.wait)
        status = "completed" if process.returncode == 0 else "failed"
    except Exception as e:
        status = "failed"
        await log_queue.put({"type": "log", "data": f"[ERROR] {e}"})

    run_state["status"] = status
    run_state["process"] = None
    await log_queue.put({"type": "status", "data": {"status": status}})


# ── SSE streaming endpoint ──

@app.get("/api/run/stream")
async def run_stream():
    async def event_generator():
        # Envoyer l'état initial (logs existants + statut actuel)
        for line in run_state["logs"]:
            yield f"event: log\ndata: {json.dumps(line, ensure_ascii=False)}\n\n"
        yield f"event: status\ndata: {json.dumps({'status': run_state['status'], 'phase': run_state['phase'], 'started_at': run_state['started_at']}, ensure_ascii=False)}\n\n"
        # Puis écouter la queue en direct
        while True:
            try:
                event = await asyncio.wait_for(log_queue.get(), timeout=5.0)
                yield f"event: {event['type']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── REST API endpoints ──

@app.get("/api/stats")
async def api_stats():
    return JSONResponse(editor.get_job_stats())


@app.get("/api/offers")
async def api_offers():
    """Liste des offres avec leur état (pour la page Offres du dashboard)."""
    import config
    from data_loader import load_jobs_global

    seuil = getattr(config, "SCORE_SEUIL", 60)
    prio = getattr(config, "SCORE_PRIORITAIRE", 80)

    def statut(s):
        if s is None:
            return "À traiter"
        if s == 0:
            return "Éliminée"
        if s >= prio:
            return "Prioritaire"
        if s >= seuil:
            return "À étudier"
        return "Ignorée"

    data = load_jobs_global()
    offers = []
    for job_id, j in data.get("jobs", {}).items():
        s = j.get("score")
        offers.append({
            "id": job_id,
            "cv_genere": bool(j.get("cv_genere")),
            "titre": j.get("titre", ""),
            "entreprise": j.get("entreprise", ""),
            "localisation": j.get("localisation", ""),
            "source": j.get("source", ""),
            "type_contrat": j.get("type_contrat", ""),
            "categorie": j.get("categorie", ""),
            "orientation": j.get("orientation", ""),
            "score": s,
            "score_global": j.get("score_global"),
            "salaire": j.get("salaire", ""),
            "statut": statut(s),
            "lien": j.get("lien", ""),
            "in_notion": bool(j.get("notion_page_id")),
            "postule": bool(j.get("postule")),
            "date_postule": j.get("date_postule", ""),
            "closed": bool(j.get("closed")),
            "date_closed": j.get("date_closed", ""),
            # Détail (pour le panneau) — champs légers, pas la description brute.
            "resume_ia": j.get("resume_ia", ""),
            "raisons_score": j.get("raisons_score", ""),
            "tags": j.get("tags", []) if isinstance(j.get("tags"), list) else [],
            "note_remuneration": j.get("note_remuneration"),
            "note_entreprise": j.get("note_entreprise"),
            "note_flexibilite": j.get("note_flexibilite"),
            "note_evolution": j.get("note_evolution"),
        })

    # Tri : meilleur score global d'abord ; les non-scorées (None) en bas.
    offers.sort(key=lambda o: (
        o["score_global"] if o["score_global"] is not None else -1,
        o["score"] if o["score"] is not None else -1,
    ), reverse=True)

    return JSONResponse({"offers": offers, "total": len(offers)})


@app.post("/api/offers/postule")
async def api_offers_postule(data: dict, background: BackgroundTasks):
    """Marque/démarque une offre comme postulée, puis synchronise Notion en fond.

    L'écriture locale est immédiate ; la synchro Notion (création/màj de la page
    + attache CV) s'exécute en tâche de fond pour ne pas ralentir l'UI et reste
    best-effort (une erreur Notion n'affecte pas l'état local)."""
    from data_loader import set_job_postule
    from notion_db import sync_candidature
    job_id = data.get("id", "")
    value = bool(data.get("value", True))
    if not set_job_postule(job_id, value):
        return JSONResponse({"ok": False, "error": "offre introuvable"}, status_code=404)
    background.add_task(sync_candidature, job_id, value)
    return JSONResponse({"ok": True, "postule": value})


@app.post("/api/offers/closed")
async def api_offers_closed(data: dict):
    """Marque/démarque une offre comme fermée (poste pourvu / candidatures closes)."""
    from data_loader import set_job_closed
    job_id = data.get("id", "")
    value = bool(data.get("value", True))
    if not set_job_closed(job_id, value):
        return JSONResponse({"ok": False, "error": "offre introuvable"}, status_code=404)
    return JSONResponse({"ok": True, "closed": value})


@app.get("/api/quotas")
async def api_quotas():
    return JSONResponse({
        "quotas": read_quotas(),
        "today_usage": editor.get_today_usage(),
    })


@app.get("/api/keywords")
async def api_keywords():
    return JSONResponse({
        "keywords": editor.read_list("config.py", "KEYWORDS"),
        "wttj_keywords": editor.read_list("scraper.py", "WTTJ_TITLE_KEYWORDS"),
        "exclusion": editor.read_list("config.py", "EXCLUSION_LIST"),
        "title_exclusion": editor.read_list("config.py", "TITLE_EXCLUSION_LIST"),
    })


@app.get("/api/job-types")
async def api_job_types():
    job_types = editor.read_list("config.py", "JOB_TYPES")
    kw = "Développeur"
    preview = {
        "linkedin": scraper.build_linkedin_search_url(kw, job_types=job_types) if job_types else "",
        "wttj": scraper.build_wttj_search_url(kw, job_types=job_types) if job_types else "",
        "indeed": f"keyword: {kw} {'+'.join(job_types)}" if job_types else "",
    }
    return JSONResponse({"job_types": job_types, "preview": preview})


@app.get("/api/scrape-zones")
async def api_scrape_zones():
    """Zones de scrape et leur état d'activation (France / Canada / International)."""
    return JSONResponse({"zones": editor.read_zones()})


@app.post("/api/scrape-zones/save")
async def api_scrape_zones_save(data: dict):
    """Enregistre l'activation des zones. Corps : {"zones": {label: bool, ...}}."""
    try:
        enabled_map = data.get("zones", {})
        if not isinstance(enabled_map, dict):
            return JSONResponse({"ok": False, "error": "format invalide"}, status_code=400)
        editor.write_zones(enabled_map)
        return JSONResponse({"ok": True, "zones": editor.read_zones()})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)


@app.get("/api/prefilter")
async def api_prefilter():
    """Config du pré-filtre déterministe (toggles + listes de termes éditables)."""
    return JSONResponse(editor.read_prefilter())


@app.post("/api/prefilter/save")
async def api_prefilter_save(data: dict):
    try:
        editor.write_prefilter(data)
        return JSONResponse({"ok": True, "prefilter": editor.read_prefilter()})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)


@app.post("/api/offers/score")
async def api_offers_score(data: dict):
    """Correction manuelle du score d'une offre (Feature B). Recalcule le score
    global via la même fonction que le pipeline. Corps : {id, score, notes?}."""
    import matcher
    from data_loader import load_jobs_global, update_job_score

    job_id = data.get("id", "")
    jobs = load_jobs_global().get("jobs", {})
    job = jobs.get(job_id)
    if not job:
        return JSONResponse({"ok": False, "error": "offre introuvable"}, status_code=404)
    try:
        score = max(0, min(100, int(data.get("score"))))
    except (TypeError, ValueError):
        return JSONResponse({"ok": False, "error": "score invalide (0-100)"}, status_code=400)

    notes = data.get("notes") or {}
    result = {
        "score": score,
        "note_remuneration": int(notes.get("remuneration", job.get("note_remuneration") or 0)),
        "note_entreprise": int(notes.get("entreprise", job.get("note_entreprise") or 0)),
        "note_flexibilite": int(notes.get("flexibilite", job.get("note_flexibilite") or 0)),
        "note_evolution": int(notes.get("evolution", job.get("note_evolution") or 0)),
    }
    global_score = matcher.compute_global_score(result)
    update_job_score(
        job_id, score,
        data.get("resume_ia", job.get("resume_ia", "")),
        data.get("raisons_score", "Score corrigé manuellement via le dashboard."),
        job.get("tags", []),
        job.get("orientation", "Cyber"),
        data.get("categorie", job.get("categorie", "Autre")),
        job.get("salaire", "Non précisé"),
        extra={"score_global": global_score, **{f"note_{k}": v for k, v in {
            "remuneration": result["note_remuneration"], "entreprise": result["note_entreprise"],
            "flexibilite": result["note_flexibilite"], "evolution": result["note_evolution"]}.items()},
            "scored_by": "manual"},
    )
    return JSONResponse({"ok": True, "score": score, "score_global": global_score})


@app.get("/api/prompts")
async def api_prompts():
    return JSONResponse({
        "system_prompt": editor.read_triple_quoted("matcher.py", "SYSTEM_PROMPT"),
        "score_prompt": editor.read_triple_quoted("matcher.py", "SCORE_PROMPT"),
    })


@app.get("/api/criteria")
async def api_criteria():
    return JSONResponse({"content": editor.read_criteria()})


@app.get("/api/run/status")
async def api_run_status():
    return JSONResponse({
        "phase": run_state["phase"],
        "started_at": run_state["started_at"],
        "status": run_state["status"],
        "logs": run_state["logs"],
    })


# ── POST / save endpoints ──

@app.post("/api/keywords/save")
async def api_keywords_save(data: dict):
    try:
        kw = data.get("keywords", [])
        wj = data.get("wttj_keywords", [])
        ex = data.get("exclusion", [])
        tex = data.get("title_exclusion", [])
        editor.write_list("config.py", "KEYWORDS", kw)
        editor.write_list("scraper.py", "WTTJ_TITLE_KEYWORDS", wj, raw_strings=True)
        editor.write_list("config.py", "EXCLUSION_LIST", ex, raw_strings=True)
        editor.write_list("config.py", "TITLE_EXCLUSION_LIST", tex, raw_strings=True)
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)


@app.post("/api/job-types/save")
async def api_job_types_save(data: dict):
    try:
        items = [t.strip().lower() for t in data.get("types", []) if t.strip()]
        valid = {"cdi", "cdd", "stage", "alternance"}
        items = [t for t in items if t in valid]
        if not items:
            items = ["alternance"]
        editor.write_list("config.py", "JOB_TYPES", items)
        kw = "Développeur"
        preview = {
            "linkedin": scraper.build_linkedin_search_url(kw, job_types=items) if items else "",
            "wttj": scraper.build_wttj_search_url(kw, job_types=items) if items else "",
            "indeed": f"keyword: {kw} {'+'.join(items)}" if items else "",
        }
        return JSONResponse({"ok": True, "preview": preview})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)


@app.post("/api/prompts/save")
async def api_prompts_save(data: dict):
    try:
        editor.write_triple_quoted("matcher.py", "SYSTEM_PROMPT", data.get("system_prompt", ""))
        editor.write_triple_quoted("matcher.py", "SCORE_PROMPT", data.get("score_prompt", ""))
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)


@app.post("/api/criteria/save")
async def api_criteria_save(data: dict):
    try:
        editor.write_criteria(data.get("content", ""))
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)


@app.post("/api/quotas/save")
async def api_quotas_save(data: dict):
    try:
        quotas = read_quotas()
        int_fields = ["daily_limit", "tpm_limit", "delay_seconds",
                       "pause_every", "pause_duration"]
        for prov in quotas:
            prov_data = data.get(prov, {})
            for field in int_fields:
                if field in prov_data:
                    val = prov_data[field]
                    if val is not None:
                        quotas[prov][field] = int(val)
        editor.write_quotas(quotas)
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)


@app.post("/api/quotas/reset")
async def api_quotas_reset():
    try:
        editor.reset_quotas_to_default()
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)


# ── Profil maître (profile_master.yaml : source de vérité des CV) ──

PROFILE_MASTER_FILE = BASE_DIR / "cvgen" / "profile_master.yaml"


@app.get("/api/profile-master")
async def api_profile_master():
    import yaml
    try:
        data = yaml.safe_load(PROFILE_MASTER_FILE.read_text(encoding="utf-8"))
        return JSONResponse({"profile": data})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/profile-master/save")
async def api_profile_master_save(data: dict):
    import yaml
    profile = data.get("profile")
    if not isinstance(profile, dict):
        return JSONResponse({"ok": False, "error": "profil invalide"}, status_code=400)
    try:
        # Sauvegarde de sécurité avant écrasement (une seule, écrasée à chaque fois).
        backup = PROFILE_MASTER_FILE.with_suffix(".yaml.bak")
        if PROFILE_MASTER_FILE.exists():
            backup.write_text(PROFILE_MASTER_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        text = yaml.safe_dump(profile, allow_unicode=True, sort_keys=False, width=1000)
        PROFILE_MASTER_FILE.write_text(text, encoding="utf-8")
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)


# ── Génération de CV à la demande (une offre, quel que soit son score) ──

@app.post("/api/generate-cv")
async def api_generate_cv(data: dict):
    """Génère le CV ciblé pour UNE offre, à la demande (seuil SCORE_GENERATE
    volontairement contourné : l'utilisateur décide).

    Répond dès que le PDF existe (~30-60 s : sélection déterministe + rendus
    Edge). La note d'analyse d'écarts (LLM) part en tâche de fond ; la lettre
    de motivation reste l'affaire de la phase batch `--phase generate` (son
    modèle de raisonnement peut mettre >10 min, injouable derrière un bouton)."""
    if run_state["status"] == "running":
        return JSONResponse({"ok": False, "error": "Un processus est déjà en cours"}, status_code=400)

    job_id = data.get("id", "")
    from data_loader import load_jobs_global, mark_job_generated
    job = load_jobs_global().get("jobs", {}).get(job_id)
    if not job:
        return JSONResponse({"ok": False, "error": "Offre introuvable"}, status_code=404)

    import config
    import utils
    from cvgen import generate_cv_for_job

    entreprise = utils.safe_filename(job.get("entreprise", "entreprise_unknown"))
    outdir = config.GENERATED_DIR / f"{entreprise}_{datetime.now().strftime('%Y%m%d')}"

    try:
        # thread séparé : les rendus Edge (bloquants) ne gèlent pas le serveur
        html_path, pdf_path, _country = await asyncio.to_thread(
            generate_cv_for_job, job, outdir
        )
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

    cv = pdf_path or html_path
    mark_job_generated(job_id, str(cv), "", str(outdir))

    # Note d'analyse d'écarts : LLM, best-effort, en tâche de fond.
    import threading

    def _notes():
        try:
            from cvgen.gap_analysis import write_gap_notes
            write_gap_notes(job, html_path, outdir)
        except Exception:
            pass

    threading.Thread(target=_notes, daemon=True).start()

    return JSONResponse({"ok": True, "cv": str(cv), "lm": ""})


@app.get("/api/cv/{job_id:path}")
async def api_download_cv(job_id: str):
    """Télécharge le CV PDF généré pour une offre."""
    from data_loader import load_jobs_global
    job = load_jobs_global().get("jobs", {}).get(job_id)
    cv = (job or {}).get("generated_files", {}).get("cv", "")
    if not cv or not Path(cv).exists():
        return JSONResponse({"error": "CV non généré"}, status_code=404)
    return FileResponse(cv, filename=Path(cv).name,
                        media_type="application/pdf")


@app.post("/api/run/{phase}")
async def api_run_start(phase: str):
    if run_state["status"] == "running":
        return JSONResponse({"ok": False, "error": "Un processus est déjà en cours"}, status_code=400)
    asyncio.create_task(_run_phase(phase))
    return JSONResponse({"ok": True, "phase": phase})


@app.post("/api/run/stop")
async def api_run_stop():
    if run_state.get("process") and run_state["status"] == "running":
        run_state["process"].kill()
        run_state["status"] = "stopped"
        run_state["process"] = None
        await log_queue.put({"type": "status", "data": {"status": "stopped"}})
        return JSONResponse({"ok": True})
    return JSONResponse({"ok": False, "error": "Aucun processus en cours"}, status_code=400)


# ── SPA catch-all ──

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith("api/") or full_path.startswith("static/"):
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "Not found"}, status_code=404)
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse({"error": "Frontend not built. Run `cd dashboard/frontend && npm run build`"}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dashboard.app:app", host="127.0.0.1", port=8000, reload=True)
