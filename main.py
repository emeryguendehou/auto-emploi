import asyncio
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import config
import utils
import scraper
import matcher
import generator
import notion_db
import data_loader

logger = utils.setup_logging("main")


class AlternanceSearch:
    def __init__(self):
        self.stats = {
            "scraped": 0,
            "dedup_added": 0,
            "dedup_updated": 0,
            "llm_processed": 0,
            "prioritaires": 0,
            "a_etudier": 0,
            "ignores": 0,
            "generated": 0,
            "notion_added": 0,
        }
        self.errors: List[str] = []

    async def run_scrape(self, zones=None, sources=None):
        """Phase 1: Scrape jobs from all sources and save to global file.

        Args:
            zones: liste de labels/alias pour un override ponctuel (ex.
                ["canada"]). None -> zones activées dans SCRAPE_ZONES_ENABLED.
            sources: liste de sources pour un override ponctuel
                (ex. ["indeed"]). None -> config.SCRAPER_SOURCES.
        """
        logger.info("=" * 50)
        logger.info("PHASE 1: SCRAPING")
        logger.info("=" * 50)

        all_jobs = []
        keywords = config.KEYWORDS
        locations = config.active_search_locations(zones)

        if not locations:
            msg = ("Aucune zone de scrape active "
                   f"(zones={zones or list(config.SCRAPE_ZONES_ENABLED)}). "
                   "Activez-en une (dashboard → Zones de scrape) ou passez --zones.")
            logger.warning(msg)
            self.errors.append(msg)
            return self.stats

        logger.info(f"Zones actives : {', '.join(l['label'] for l in locations)}")
        if sources:
            logger.info(f"Sources (override) : {', '.join(sources)}")

        for keyword in keywords:
            for i, loc in enumerate(locations):
                label = loc.get("label", "?")
                logger.info(f"[{i+1}/{len(locations)}] {keyword} @ {label}")

                try:
                    jobs = await scraper.scrape_all(keyword, loc, sources_override=sources)
                    all_jobs.extend(jobs)
                    logger.info(f"  → {len(jobs)} jobs from {label}")

                    if jobs:
                        dedup_stats = data_loader.add_jobs_to_global(jobs)
                        logger.info(f"  → +{dedup_stats['added']} added to global file")
                        total = data_loader.get_job_count()
                        logger.info(f"  → Global total: {total} jobs")

                except Exception as e:
                    logger.error(f"  → Failed: {e}")
                    self.errors.append(f"Scraping {keyword} @{label}: {e}")

                time.sleep(3)
            
            time.sleep(5)  # Delay between keywords

        self.stats["scraped"] = len(all_jobs)
        logger.info(f"Total scraped (this run): {len(all_jobs)} jobs")

        total = data_loader.get_job_count()
        logger.info(f"Global file: {total} unique jobs (all time)")

        return self.stats

    async def run_process(self, limit: int = 0):
        """Phase 2: Process jobs with LLM and add to Notion.

        Args:
            limit: nombre max d'offres à scorer ce run (0 = pas de limite).
                   Utile pour tester/étaler le scoring sans épuiser les quotas.
        """
        logger.info("=" * 50)
        logger.info("PHASE 2: LLM PROCESSING")
        logger.info("=" * 50)

        jobs_to_process = data_loader.get_unprocessed_jobs()

        if not jobs_to_process:
            logger.info("No new jobs to process")
            return self.stats

        if limit and limit > 0:
            total_dispo = len(jobs_to_process)
            jobs_to_process = jobs_to_process[:limit]
            logger.info(f"Limite active : {len(jobs_to_process)}/{total_dispo} offres ce run")

        logger.info(f"Jobs to process: {len(jobs_to_process)}")

        matched = await matcher.match_jobs(jobs_to_process)

        self.stats["prioritaires"] = len(matched["prioritaires"])
        self.stats["a_etudier"] = len(matched["a_etudier"])
        self.stats["ignores"] = len(matched["ignores"])

        logger.info(f"LLM processed: {self.stats['prioritaires'] + self.stats['a_etudier'] + self.stats['ignores']}")

        jobs_for_notion = data_loader.get_jobs_for_notion()
        logger.info(f"Jobs ready for Notion: {len(jobs_for_notion)}")

        for i, job in enumerate(jobs_for_notion):
            logger.info(f"[{i+1}/{len(jobs_for_notion)}] {job.get('entreprise', '?')} (score: {job.get('score', 0)})")

            try:
                page_id = await notion_db.add_job_to_notion(job)

                if page_id:
                    data_loader.update_job_notion(job.get("job_id", ""), page_id)
                    self.stats["notion_added"] += 1
                    logger.info(f"  → Added to Notion")
            except Exception as e:
                logger.error(f"  → Failed: {e}")

            time.sleep(1)

        return self.stats

    async def run_notion(self):
        """Phase: Add jobs to Notion only (no LLM)."""
        logger.info("=" * 50)
        logger.info("PHASE: NOTION ONLY")
        logger.info("=" * 50)

        jobs_for_notion = data_loader.get_jobs_for_notion()
        logger.info(f"Jobs ready for Notion: {len(jobs_for_notion)}")

        for i, job in enumerate(jobs_for_notion):
            logger.info(f"[{i+1}/{len(jobs_for_notion)}] {job.get('entreprise', '?')} (score: {job.get('score', 0)})")

            try:
                page_id = await notion_db.add_job_to_notion(job)

                if page_id:
                    data_loader.update_job_notion(job.get("job_id", ""), page_id)
                    self.stats["notion_added"] += 1
                    logger.info(f"  → Added to Notion")
            except Exception as e:
                logger.error(f"  → Failed: {e}")

            time.sleep(1)

        return self.stats

    async def run_generate(self, limit: int = 0):
        """Phase: génère CV ciblé (PDF via cvgen) + lettre pour les meilleures offres.

        Args:
            limit: nombre max d'offres à générer ce run (0 = pas de limite).
        """
        logger.info("=" * 50)
        logger.info("PHASE: GENERATION CV/LM")
        logger.info("=" * 50)

        jobs = data_loader.get_jobs_for_generation()
        if not jobs:
            logger.info("Aucune offre à générer (score >= SCORE_GENERATE, non déjà générée)")
            return self.stats

        if limit and limit > 0:
            total_dispo = len(jobs)
            # Meilleures offres d'abord quand on limite le lot.
            jobs.sort(key=lambda j: (j.get("score_global") or j.get("score") or 0), reverse=True)
            jobs = jobs[:limit]
            logger.info(f"Limite active : {len(jobs)}/{total_dispo} offres ce run")

        logger.info(f"Offres à générer: {len(jobs)}")

        for i, job in enumerate(jobs):
            logger.info(f"[{i+1}/{len(jobs)}] {job.get('entreprise', '?')} (score: {job.get('score', 0)})")
            try:
                result = await generator.generate_for_job(job)
                if result and result.get("cv"):
                    data_loader.mark_job_generated(
                        job.get("job_id", ""),
                        cv_path=result.get("cv", ""),
                        lm_path=result.get("lm", ""),
                        out_dir=result.get("dir", ""),
                    )
                    self.stats["generated"] += 1
                    logger.info(f"  -> CV/LM générés: {result.get('dir')}")

                    page_id = job.get("notion_page_id")
                    if page_id:
                        await notion_db.set_cv_genere(page_id, True)
                else:
                    logger.warning(f"  -> Génération échouée pour {job.get('entreprise', '?')}")
            except Exception as e:
                logger.error(f"  -> Failed: {e}")

            time.sleep(2)

        return self.stats

    def run_filter(self):
        """Phase: Apply exclusion list to all jobs in JSON."""
        logger.info("=" * 50)
        logger.info("PHASE: FILTER (Exclusion List)")
        logger.info("=" * 50)

        data = data_loader.load_jobs_global()
        jobs = data.get("jobs", {})
        
        excluded_count = 0
        updated_count = 0
        
        for job_id, job in jobs.items():
            excluded, reason = matcher.check_exclusion_list(job)
            if excluded and job.get("score", 0) != 0:
                data_loader.update_job_score(
                    job_id,
                    0,
                    f"Exclu: {reason}",
                    f"Exclu automatiquement - terme interdit détecté: {reason}",
                    []
                )
                excluded_count += 1
                logger.info(f"[EXCLUDED] {job.get('titre', '')[:40]} → '{reason}'")
            elif excluded:
                excluded_count += 1
                logger.info(f"[EXCLUDED] {job.get('titre', '')[:40]} → '{reason}' (already score=0)")
        
        logger.info(f"Total jobs checked: {len(jobs)}")
        logger.info(f"Jobs excluded: {excluded_count}")
        
        return self.stats

    async def run(self, phase: str = "all", limit: int = 0, zones=None, sources=None):
        """Main runner with phase control.

        Args:
            phase: "all", "scrape", "process", or "notion"
            limit: nombre max d'offres à scorer (0 = pas de limite), phase process
            zones: override ponctuel des zones de scrape (labels/alias)
            sources: override ponctuel des sources (linkedin/indeed/wttj)
        """
        logger.info("=" * 50)
        logger.info(f"AUTO ALTERNANCE - Phase: {phase.upper()}")
        logger.info("=" * 50)

        if phase in ["all", "scrape"]:
            await self.run_scrape(zones=zones, sources=sources)

        if phase in ["all", "filter"]:
            self.run_filter()

        if phase in ["all", "process", "keep"]:
            await self.run_process(limit=limit)

        if phase in ["all", "notion", "keep"]:
            await self.run_notion()

        # Génération CV/LM : phase explicite uniquement (évite une rafale de
        # générations au premier run sur tout l'historique des prioritaires).
        if phase == "generate":
            await self.run_generate(limit=limit)

        self._log_summary()
        return self.stats

    def _log_summary(self):
        logger.info("=" * 50)
        logger.info("SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Jobs scraped:        {self.stats['scraped']}")
        logger.info(f"Jobs dedup added:   {self.stats['dedup_added']}")
        logger.info(f"Jobs dedup upd:   {self.stats['dedup_updated']}")
        logger.info(f"LLM processed:    {self.stats['llm_processed']}")
        logger.info(f"Prioritaires:    {self.stats['prioritaires']}")
        logger.info(f"À étudier:       {self.stats['a_etudier']}")
        logger.info(f"Ignorés:        {self.stats['ignores']}")
        logger.info(f"Notion added:   {self.stats['notion_added']}")
        logger.info(f"CV/LM générés:  {self.stats['generated']}")

        if self.errors:
            logger.warning(f"Errors: {len(self.errors)}")
            for err in self.errors[:3]:
                logger.warning(f"  - {err}")


async def main():
    parser = argparse.ArgumentParser(description="Auto Alternance Search")
    parser.add_argument(
        "--phase",
        choices=["all", "scrape", "process", "notion", "filter", "keep", "generate"],
        default="all",
        help="Phase to run: all (scrape→filter→process→notion), keep (process→notion), "
             "generate (CV/LM des offres score>=SCORE_GENERATE), scrape, filter, process, notion"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Nombre max d'offres à traiter lors des phases process et generate "
             "(0 = pas de limite). Ex: --phase process --limit 20, "
             "--phase generate --limit 3"
    )
    parser.add_argument(
        "--zones",
        type=str,
        default="",
        help="Override ponctuel des zones de scrape (séparées par des virgules) : "
             "france, canada, international. Ex: --phase scrape --zones canada. "
             "Vide = zones activées dans le dashboard (SCRAPE_ZONES_ENABLED)."
    )
    parser.add_argument(
        "--sources",
        type=str,
        default="",
        help="Override ponctuel des sources de scrape (virgules) : "
             "linkedin, indeed, wttj. Ex: --phase scrape --zones canada --sources indeed. "
             "Vide = config.SCRAPER_SOURCES."
    )
    args = parser.parse_args()

    zones = [z for z in args.zones.split(",") if z.strip()] or None
    sources = [s for s in args.sources.split(",") if s.strip()] or None

    search = AlternanceSearch()
    await search.run(phase=args.phase, limit=args.limit, zones=zones, sources=sources)


if __name__ == "__main__":
    asyncio.run(main())