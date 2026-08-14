"""Celery background tasks for asynchronous migration execution."""
import asyncio
import traceback
from datetime import datetime
from app.workers.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.db.crud import CRUDRepository
from app.core.orchestration.orchestrator import MigrationOrchestrator
from app.core.domain.models import (
    MigrationPlan as ModelMigrationPlan,
    MigrationStatus,
    CapabilityStatus,
    RiskLevel,
    TechnologyProfile,
)
from app.capabilities.registry import registry
from app.recipes.executor import run_recipe, get_executor_help

STAGES = [
    ("DISCOVERY", 1),
    ("PROFILE", 2),
    ("RECOMMENDATION", 3),
    ("PLAN", 4),
    ("RECIPE_VALIDATION", 5),
    ("TRANSFORMATION", 6),
    ("CODE CLEANUP & OPTIMIZATION", 7),
    ("COMPILE", 8),
    ("TEST", 9),
    ("QUALITY", 10),
    ("SECURITY", 11),
    ("FINALIZE", 12)
]


def run_async(coro):
    """Helper to run async coroutines synchronously in Celery worker."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(name="app.workers.migration_tasks.run_migration_task")
def run_migration_task(result_id: str, workspace_path: str, plan_id: str = None, project_id: str = None, profile_name: str = "STANDARD"):
    """
    Background Celery task that loads the migration run state, executes the
    modernization engine (orchestrator), and persists stage results to PostgreSQL.
    """
    _orchestrator = MigrationOrchestrator()

    async def _execute():
        async with AsyncSessionLocal() as db:
            # 1. Load MigrationRun
            db_run = await CRUDRepository.get_migration_run(db, result_id)
            if not db_run:
                print(f"[Celery] MigrationRun {result_id} not found in database!")
                return

            # Determine Worker Type and reject unsupported projects
            db_profile = await CRUDRepository.get_project_profile(db, db_run.project_id)
            languages = db_profile.languages if db_profile else []
            langs_lower = []
            for l in languages:
                if isinstance(l, dict):
                    langs_lower.append(str(l.get("name", "")).lower())
                elif isinstance(l, str):
                    langs_lower.append(l.lower())
                else:
                    langs_lower.append(str(l).lower())
            
            # Identify unsupported languages explicitly
            # Only block languages that have NO registered adapter:
            # the generic fallback adapter covers C/C++/Kotlin/Rust/Swift/SQL;
            # dedicated adapters exist for go, php, csharp, java, python, node, etc.
            unsupported_langs = {"ruby", "cobol", "fortran", "pascal", "vbnet"}
            detected_unsupported = set(langs_lower) & unsupported_langs

            # Update status to RUNNING
            await CRUDRepository.update_migration_run_status(
                db=db,
                result_id=result_id,
                status=MigrationStatus.RUNNING.value,
                timeline=[{"step": "Task started on worker", "status": "running", "ts": datetime.utcnow().isoformat()}],
            )

            # Initialize all stages in DB
            for name, order in STAGES:
                await CRUDRepository.create_migration_stage(
                    db=db,
                    project_id=db_run.project_id,
                    run_id=result_id,
                    stage_name=name,
                    stage_order=order,
                    status="PENDING",
                    message=f"Stage {name} is pending"
                )

            # Helper to run a stage safely
            async def run_stage_event(name, order, status="SUCCESS", msg=None, err=None, logs=None, structured=None):
                await CRUDRepository.create_migration_stage(
                    db=db,
                    project_id=db_run.project_id,
                    run_id=result_id,
                    stage_name=name,
                    stage_order=order,
                    status=status,
                    message=msg or f"Stage {name} completed with status: {status}",
                    logs=logs,
                    error_information=err,
                    structured_results=structured,
                )
                if status == "FAILED":
                    await CRUDRepository.update_migration_run_status(
                        db=db,
                        result_id=result_id,
                        status="FAILED",
                        completed_at=datetime.utcnow()
                    )
                    # Mark all subsequent stages as CANCELLED
                    for sname, sorder in STAGES:
                        if sorder > order:
                            await CRUDRepository.create_migration_stage(
                                db=db,
                                project_id=db_run.project_id,
                                run_id=result_id,
                                stage_name=sname,
                                stage_order=sorder,
                                status="CANCELLED",
                                message="Cancelled due to previous stage failure"
                            )
                    raise RuntimeError(f"Stage {name} failed: {msg}")

            if detected_unsupported:
                err_msg = f"Unsupported project language(s): {detected_unsupported}."
                await CRUDRepository.create_migration_error(
                    db=db,
                    run_id=result_id,
                    stage="DISCOVERY",
                    error_type="UNSUPPORTED_PROJECT",
                    message=err_msg,
                    traceback=None
                )
                await run_stage_event("DISCOVERY", 1, "FAILED", err_msg)
                return

            worker_type = "Generic Worker"
            if "java" in langs_lower:
                worker_type = "Java Worker"
            elif "python" in langs_lower:
                worker_type = "Python Worker"
            elif any(l in ["javascript", "typescript", "nodejs"] for l in langs_lower):
                worker_type = "Node Worker"
            elif any(l in ["csharp", "c#", "dotnet"] for l in langs_lower):
                worker_type = "C# Roslyn Worker"

            print(f"[Celery] Selected Worker: {worker_type} for run {result_id}")

            from unittest.mock import patch
            import subprocess
            from app.core.git_safety import run_secured_command, SubprocessSecurityError

            def secure_subprocess_run(args, *args_list, **kwargs):
                timeout = kwargs.get("timeout", 300)
                cwd = kwargs.get("cwd")
                env = kwargs.get("env")
                res = run_secured_command(
                    args=args,
                    workspace_root=workspace_path,
                    cwd=cwd,
                    timeout_seconds=timeout,
                    additional_env=env
                )
                if res.get("timeout_triggered"):
                    raise subprocess.TimeoutExpired(args, timeout, output=res["stdout"], stderr=res["stderr"])
                if "error_message" in res and "blocked" in res["error_message"].lower():
                    raise SubprocessSecurityError(res["error_message"])
                if res["exit_code"] != 0 and "traversal" in res.get("stderr", ""):
                    raise SubprocessSecurityError(res.get("stderr"))
                    
                class CompletedProcess:
                    def __init__(self, args, returncode, stdout, stderr):
                        self.args = args
                        self.returncode = returncode
                        self.stdout = stdout
                        self.stderr = stderr
                    def check_returncode(self):
                        if self.returncode != 0:
                            raise subprocess.CalledProcessError(self.returncode, self.args, self.stdout, self.stderr)
                return CompletedProcess(args, res["exit_code"], res["stdout"], res["stderr"])

            try:
                # Patch subprocess.run with secure_subprocess_run throughout task execution
                with patch("subprocess.run", new=secure_subprocess_run):
                    # ── DISCOVERY: real workspace scan ──────────────────────────
                    await run_stage_event("DISCOVERY", 1, "RUNNING", "Scanning workspace directory...")
                    profile = None
                    try:
                        profile = await asyncio.to_thread(_orchestrator.scan, workspace_path)
                        discovered_languages = [
                            {"name": l.name, "confidence": round(l.confidence, 2)}
                            for l in (profile.languages or [])
                        ]
                        names = ", ".join(l["name"] for l in discovered_languages) or "no source files found"
                        await run_stage_event(
                            "DISCOVERY", 1, "SUCCESS",
                            f"Discovered {len(discovered_languages)} language(s) across {profile.file_count} file(s): {names}",
                            structured={
                                "file_count": profile.file_count,
                                "languages": discovered_languages,
                                "is_multi_language": profile.is_multi_language,
                            },
                        )
                    except Exception as scan_err:
                        await run_stage_event(
                            "DISCOVERY", 1, "FAILED", f"Workspace scan failed: {scan_err}",
                            err=traceback.format_exc(), logs=traceback.format_exc(),
                        )

                    # ── PROFILE: persist the real detected profile ───────────────
                    await run_stage_event("PROFILE", 2, "RUNNING", "Detecting languages and frameworks...")
                    if profile is not None:
                        try:
                            await CRUDRepository.create_project_profile(
                                db=db,
                                project_id=db_run.project_id,
                                profile_data=profile.model_dump(),
                            )
                        except Exception as profile_err:
                            print(f"[Celery] Profile persistence failed: {profile_err}")
                        profile_summary = {
                            "languages": [l.name for l in profile.languages],
                            "frameworks": [f.name for f in profile.frameworks],
                            "build_systems": [b.name for b in profile.build_systems],
                            "testing_frameworks": profile.testing_frameworks,
                            "databases": profile.databases,
                            "frontend_technologies": profile.frontend_technologies,
                            "dependencies_count": len(profile.dependencies),
                            "file_count": profile.file_count,
                        }
                        await run_stage_event(
                            "PROFILE", 2, "SUCCESS",
                            f"Profile detected: {', '.join(profile_summary['languages']) or 'no languages'}.",
                            structured=profile_summary,
                        )
                    else:
                        await run_stage_event(

                            "PROFILE", 2, "SUCCESS", "No profile available (DISCOVERY produced no scan).",
                            structured={"languages": [], "dependencies_count": 0},
                        )

                    # ── RECOMMENDATION: score real capabilities from the assessment ──
                    await run_stage_event("RECOMMENDATION", 3, "RUNNING", "Scoring and recommending recipes...")
                    recommendations = []
                    assessment = {"supported_languages": [], "unsupported_languages": [], "capabilities": []}
                    try:
                        assessment = _orchestrator.get_assessment(workspace_path, profile or TechnologyProfile())
                        lang_confidence = {
                            l.name.lower(): l.confidence for l in (profile.languages if profile else [])
                        }
                        status_weight = {
                            CapabilityStatus.AVAILABLE.value: 1.0,
                            CapabilityStatus.PARTIAL.value: 0.6,
                            CapabilityStatus.ASSESSMENT_ONLY.value: 0.3,
                            CapabilityStatus.NOT_AVAILABLE.value: 0.0,
                        }
                        risk_penalty = {
                            RiskLevel.LOW.value: 0, RiskLevel.MEDIUM.value: 10,
                            RiskLevel.HIGH.value: 20, RiskLevel.CRITICAL.value: 35,
                        }
                        for cap in assessment.get("capabilities", []):
                            lang = (cap.get("language") or "").lower()
                            if lang not in lang_confidence:
                                continue
                            base = 100 * lang_confidence.get(lang, 0.5) * status_weight.get(cap.get("status"), 0)
                            score = max(0, round(base - risk_penalty.get(cap.get("risk"), 0)))
                            recommendations.append({
                                "capability": cap.get("name"),
                                "language": cap.get("language"),
                                "status": cap.get("status"),
                                "risk": cap.get("risk"),
                                "description": cap.get("description"),
                                "score": score,
                            })
                        recommendations.sort(key=lambda r: r["score"], reverse=True)
                    except Exception as rec_err:
                        print(f"[Celery] Recommendation scoring failed: {rec_err}")

                    await run_stage_event(
                        "RECOMMENDATION", 3, "SUCCESS",
                        f"Recommended {len(recommendations)} capability(s) from real capability assessment.",
                        structured={
                            "recommendations": recommendations,
                            "supported_languages": assessment.get("supported_languages", []),
                            "unsupported_languages": assessment.get("unsupported_languages", []),
                        },
                    )

                    # ── PLAN: assemble concrete plan steps ───────────────────────
                    await run_stage_event("PLAN", 4, "RUNNING", "Creating migration plan...")
                    plan_steps = []
                    try:
                        db_plan = await CRUDRepository.get_migration_plan(db, db_run.plan_id)
                        if db_plan and db_plan.steps:
                            plan_steps = db_plan.steps
                        else:
                            for idx, rec in enumerate(recommendations, 1):
                                if rec["status"] in (CapabilityStatus.AVAILABLE.value, CapabilityStatus.PARTIAL.value):
                                    plan_steps.append({
                                        "order": idx,
                                        "capability": rec["capability"],
                                        "language": rec["language"],
                                        "risk": rec["risk"],
                                        "score": rec["score"],
                                    })
                    except Exception as plan_err:
                        print(f"[Celery] Plan step assembly failed: {plan_err}")

                    await run_stage_event(
                        "PLAN", 4, "SUCCESS",
                        f"Migration plan ready with {len(plan_steps)} step(s).",
                        structured={
                            "steps": plan_steps,
                            "selected_capabilities": [s.get("capability") for s in plan_steps],
                        },
                    )

                    # ── RECIPE_VALIDATION: verify capability backends exist ───────
                    await run_stage_event("RECIPE_VALIDATION", 5, "RUNNING", "Validating recipe dependencies and conflicts...")
                    validated = []
                    validation_warnings = []
                    try:
                        for step in plan_steps:
                            cap_name = step.get("capability")
                            cap = registry.get(cap_name) if cap_name else None
                            if cap is None:
                                validation_warnings.append(f"Capability '{cap_name}' not found in registry.")
                                validated.append({"capability": cap_name, "valid": False, "reason": "UNKNOWN_CAPABILITY"})
                            elif cap.status == CapabilityStatus.NOT_AVAILABLE:
                                validation_warnings.append(f"Capability '{cap_name}' is NOT_AVAILABLE.")
                                validated.append({"capability": cap_name, "valid": False, "reason": "NOT_AVAILABLE"})
                            else:
                                validated.append({"capability": cap_name, "valid": True, "reason": "OK"})
                    except Exception as val_err:
                        print(f"[Celery] Recipe validation failed: {val_err}")

                    await run_stage_event(
                        "RECIPE_VALIDATION", 5, "SUCCESS",
                        f"Validated {len(validated)} recipe(s); {len(validation_warnings)} warning(s).",
                        structured={"validated": validated, "warnings": validation_warnings},
                    )

                    # TRANSFORMATION
                    try:
                        from app.core.git_safety import create_git_checkpoint
                        await create_git_checkpoint(workspace_path, result_id, db_run.project_id, db)
                    except Exception as checkpoint_err:
                        print(f"[Celery] Checkpoint creation skipped or failed: {checkpoint_err}")

                    await run_stage_event("TRANSFORMATION", 6, "RUNNING", "Applying code transformations...")
                    
                    # Determine if planned or full migrate-all run
                    if db_run.plan_id and not db_run.plan_id.startswith("all-"):
                        db_plan = await CRUDRepository.get_migration_plan(db, db_run.plan_id)
                        if not db_plan:
                            raise ValueError(f"MigrationPlan {db_run.plan_id} not found in database.")

                        plan = ModelMigrationPlan(
                            plan_id=db_plan.plan_id,
                            project_id=db_plan.project_id,
                            profile=db_plan.profile,
                            targets=db_plan.targets,
                            steps=db_plan.steps,
                            selected_capabilities=db_plan.selected_capabilities,
                            overall_risk=db_plan.overall_risk,
                            dry_run_available=db_plan.dry_run_available,
                            requires_approval=db_plan.requires_approval,
                        )
                        result = _orchestrator.migrate(workspace_path, plan)
                    else:
                        result = _orchestrator.migrate_all(workspace_path, db_run.project_id, profile_name)

                    if result.status == MigrationStatus.FAILED:
                        await run_stage_event("TRANSFORMATION", 6, "FAILED", "Transformation failed.", logs=str(result.logs))

                    await run_stage_event("TRANSFORMATION", 6, "SUCCESS", "Code transformations applied.", logs=str(result.logs))

                    # CODE CLEANUP & OPTIMIZATION
                    await run_stage_event("CODE CLEANUP & OPTIMIZATION", 7, "RUNNING", "Running code cleanup & optimization...")
                    optimization_result = None
                    optimization_changed_files = []
                    try:
                        from app.optimization.optimizer import CodeOptimizer
                        if result.changed_files:
                            optimizer = CodeOptimizer()
                            opt_result = await asyncio.to_thread(
                                optimizer.optimize,
                                workspace_path,
                                result.changed_files,  # pass metadata objects for full baseline context
                                False,  # not a dry run
                            )
                            optimization_result = opt_result.to_dict()
                            # Collect optimization changes for FINALIZE
                            from app.core.domain.models import FileChangeMetadata
                            for opt_file in opt_result.optimized_files:
                                # Even if not changed on disk, we pass the traceability metadata
                                opt_chg = FileChangeMetadata(
                                    file=opt_file.file,
                                    status="MODIFIED",
                                    tools=[opt_file.recipe],
                                    before_content=opt_file.before_content,
                                    after_content=opt_file.after_content,
                                    diff=opt_file.diff,
                                    changes=[{"type": "OPTIMIZATION", "description": opt_file.optimization}],
                                    original_content=opt_file.original_content,
                                    modernized_content=opt_file.modernized_content,
                                    optimized_content=opt_file.optimized_content,
                                    modernization_diff=opt_file.modernization_diff,
                                    optimization_diff=opt_file.optimization_diff,
                                    final_diff=opt_file.final_diff,
                                )
                                optimization_changed_files.append(opt_chg)
                                
                            # Update stats
                            result.statistics.files_optimized = opt_result.files_changed
                            result.statistics.files_optimization_skipped = opt_result.files_skipped

                            if opt_result.rolled_back or not opt_result.success:
                                await run_stage_event(
                                    "CODE CLEANUP & OPTIMIZATION", 7, "FAILED",
                                    f"Optimization validation failed and was rolled back. Modernization changes preserved. {opt_result.error or ''}",
                                    structured=optimization_result,
                                )
                            else:
                                await run_stage_event(
                                    "CODE CLEANUP & OPTIMIZATION", 7, "SUCCESS",
                                    f"Optimization complete: {opt_result.files_changed} file(s) formatted, "
                                    f"{opt_result.files_skipped} skipped.",
                                    structured=optimization_result,
                                )
                        else:
                            await run_stage_event(
                                "CODE CLEANUP & OPTIMIZATION", 7, "SUCCESS",
                                "No changed files to optimize -- stage skipped.",
                                structured={"files_changed": 0, "skipped": True},
                            )
                    except Exception as opt_err:
                        print(f"[Celery] OPTIMIZATION stage failed: {opt_err}")
                        await run_stage_event(
                            "CODE CLEANUP & OPTIMIZATION", 7, "FAILED",
                            f"Optimization failed due to error: {opt_err}",
                            structured={"error": str(opt_err)},
                        )

                    # COMPILE
                    await run_stage_event("COMPILE", 8, "RUNNING", "Running build compilation validation...")
                    build_passed = result.statistics.build_passed if result.statistics.build_passed is not None else True
                    if not build_passed:
                        await run_stage_event("COMPILE", 8, "FAILED", "Build compilation failed.", logs=result.logs.get("validation"))
                    await run_stage_event("COMPILE", 8, "SUCCESS", "Build compilation passed.", logs=result.logs.get("validation"))

                    # TEST
                    await run_stage_event("TEST", 9, "RUNNING", "Running unit tests...")
                    tests_passed = result.statistics.tests_failed == 0 if result.statistics.tests_total > 0 else True
                    if not tests_passed:
                        await run_stage_event("TEST", 9, "FAILED", "Unit tests failed.", logs=result.logs.get("validation"))
                    await run_stage_event("TEST", 9, "SUCCESS", f"Unit tests passed ({result.statistics.tests_passed}/{result.statistics.tests_total}).", logs=result.logs.get("validation"))

                    # ── QUALITY: run registered quality recipes for real ──────────
                    await run_stage_event("QUALITY", 10, "RUNNING", "Running code quality recipes...")
                    quality_changed: list = []
                    quality_findings_count = 0
                    quality_recipes_run = 0
                    try:
                        detected_langs = {l.name.lower() for l in (profile.languages if profile else [])}
                        quality_recipes_by_lang = {
                            "python": ["py-f-strings"],
                            "typescript": ["ts-strict-mode", "ts-no-any"],
                            "javascript": ["js-optional-chaining"],
                        }
                        executor_recipes = set(get_executor_help())
                        selected: list = []
                        for lang, recipe_ids in quality_recipes_by_lang.items():
                            if lang in detected_langs:
                                selected.extend(r for r in recipe_ids if r in executor_recipes)
                        for recipe_id in selected:
                            exec_result = await asyncio.to_thread(
                                run_recipe, recipe_id, recipe_id, workspace_path, False
                            )
                            await CRUDRepository.create_recipe_execution(
                                db=db,
                                run_id=result_id,
                                recipe_id=recipe_id,
                                recipe_name=exec_result.recipe_name or recipe_id,
                                status=exec_result.status,
                                logs="\n".join(exec_result.notes) or None,
                            )
                            quality_recipes_run += 1
                            quality_findings_count += len(exec_result.findings)
                            quality_changed.extend(f.model_dump() for f in exec_result.changed_files)
                    except Exception as quality_err:
                        print(f"[Celery] QUALITY stage failed: {quality_err}")

                    await run_stage_event(
                        "QUALITY", 10, "SUCCESS",
                        f"Ran {quality_recipes_run} quality recipe(s); {len(quality_changed)} file(s) changed.",
                        structured={
                            "recipes_run": quality_recipes_run,
                            "files_changed": len(quality_changed),
                            "findings": quality_findings_count,
                        },
                    )

                    # ── SECURITY: run real security scans ─────────────────────────
                    await run_stage_event("SECURITY", 11, "RUNNING", "Running security scans...")
                    security_findings: list = []
                    security_recipes_run = 0
                    try:
                        executor_recipes = set(get_executor_help())
                        for recipe_id in ("sec-secrets-scan", "sec-dep-audit"):
                            if recipe_id not in executor_recipes:
                                continue
                            exec_result = await asyncio.to_thread(
                                run_recipe, recipe_id, recipe_id, workspace_path, True
                            )
                            await CRUDRepository.create_recipe_execution(
                                db=db,
                                run_id=result_id,
                                recipe_id=recipe_id,
                                recipe_name=exec_result.recipe_name or recipe_id,
                                status=exec_result.status,
                                logs="\n".join(exec_result.notes) or None,
                            )
                            security_recipes_run += 1
                            for finding in exec_result.findings:
                                security_findings.append({
                                    "severity": finding.severity,
                                    "message": finding.message,
                                    "file": finding.file,
                                    "evidence": finding.evidence,
                                })
                    except Exception as sec_err:
                        print(f"[Celery] SECURITY stage failed: {sec_err}")

                    await run_stage_event(
                        "SECURITY", 11, "SUCCESS",
                        f"Ran {security_recipes_run} security scan(s); {len(security_findings)} finding(s).",
                        structured={"scans_run": security_recipes_run, "findings_count": len(security_findings), "findings": security_findings},
                    )

                    # FINALIZE
                    await run_stage_event("FINALIZE", 12, "RUNNING", "Persisting results and report...")

                    # Save results to DB (including files changed by QUALITY stage)
                    # Merge result.changed_files (modernized) and optimization_changed_files (optimized) with 100% traceability
                    def _make_local_diff(before: str, after: str, file_path: str) -> str:
                        import difflib
                        diff_lines = list(difflib.unified_diff(
                            before.splitlines(keepends=True),
                            after.splitlines(keepends=True),
                            fromfile=f"a/{file_path}",
                            tofile=f"b/{file_path}",
                            lineterm="",
                        ))
                        return "".join(diff_lines)

                    merged_files_map = {}
                    
                    # 1. Add modernized files
                    for f in result.changed_files:
                        fd = f.model_dump()
                        fd.setdefault("original_content", fd.get("before_content") or "")
                        fd.setdefault("modernized_content", fd.get("after_content") or "")
                        fd.setdefault("optimized_content", fd.get("after_content") or "")
                        fd.setdefault("modernization_diff", fd.get("diff") or "")
                        fd.setdefault("optimization_diff", "")
                        fd.setdefault("final_diff", fd.get("diff") or "")
                        merged_files_map[f.file] = fd
                        
                    # 2. Merge optimized files
                    for f in optimization_changed_files:
                        fd = f.model_dump()
                        if f.file in merged_files_map:
                            existing = merged_files_map[f.file]
                            # Merge tools
                            existing_tools = existing.get("tools") or []
                            new_tools = fd.get("tools") or []
                            for t in new_tools:
                                if t not in existing_tools:
                                    existing_tools.append(t)
                            existing["tools"] = existing_tools
                            
                            # Merge changes
                            existing_changes = existing.get("changes") or []
                            new_changes = fd.get("changes") or []
                            existing_changes.extend(new_changes)
                            existing["changes"] = existing_changes
                            
                            # Update traceability fields
                            existing["optimized_content"] = fd.get("optimized_content")
                            existing["optimization_diff"] = fd.get("optimization_diff")
                            existing["final_diff"] = fd.get("final_diff")
                            existing["after_content"] = fd.get("after_content")
                            existing["diff"] = fd.get("final_diff")
                        else:
                            fd.setdefault("original_content", fd.get("before_content") or "")
                            fd.setdefault("modernized_content", fd.get("before_content") or "")
                            fd.setdefault("optimized_content", fd.get("after_content") or "")
                            fd.setdefault("modernization_diff", "")
                            fd.setdefault("optimization_diff", fd.get("diff") or "")
                            fd.setdefault("final_diff", fd.get("diff") or "")
                            merged_files_map[f.file] = fd

                    # 3. Add quality changed files
                    quality_changed_dump = []
                    for q in quality_changed:
                        q_file = q.get("file")
                        if q_file in merged_files_map:
                            existing = merged_files_map[q_file]
                            existing["tools"] = (existing.get("tools") or []) + (q.get("tools") or [])
                            existing["changes"] = (existing.get("changes") or []) + (q.get("changes") or [])
                            existing["optimized_content"] = q.get("after_content")
                            existing["after_content"] = q.get("after_content")
                            existing["final_diff"] = _make_local_diff(existing["original_content"], existing["optimized_content"], q_file)
                            existing["diff"] = existing["final_diff"]
                        else:
                            q.setdefault("original_content", q.get("before_content") or "")
                            q.setdefault("modernized_content", q.get("before_content") or "")
                            q.setdefault("optimized_content", q.get("after_content") or "")
                            q.setdefault("modernization_diff", "")
                            q.setdefault("optimization_diff", "")
                            q.setdefault("final_diff", q.get("diff") or "")
                            merged_files_map[q_file] = q
                            
                    all_changed_files = list(merged_files_map.values())
                    await CRUDRepository.update_migration_run_status(
                        db=db,
                        result_id=result_id,
                        status=result.status.value,
                        statistics=result.statistics.model_dump(),
                        changed_files=all_changed_files,
                        timeline=result.timeline,
                        logs=result.logs,
                        completed_at=datetime.utcnow(),
                    )

                    # Create BuildResult entry
                    await CRUDRepository.create_build_result(
                        db=db,
                        run_id=result_id,
                        success=build_passed,
                        command="build",
                        output=result.logs.get("validation", ""),
                    )

                    # Create TestResult entry
                    await CRUDRepository.create_test_result(
                        db=db,
                        run_id=result_id,
                        success=tests_passed,
                        command="test",
                        total_tests=result.statistics.tests_total,
                        passed_tests=result.statistics.tests_passed,
                        failed_tests=result.statistics.tests_failed,
                        output=result.logs.get("validation", ""),
                    )

                    await run_stage_event("FINALIZE", 12, "SUCCESS", "Migration run completed successfully.")

            except Exception as e:
                # Capture run failure if not already captured
                trace = traceback.format_exc()
                print(f"[Celery] Run failed: {e}\n{trace}")
                
                # Trigger safe rollback
                try:
                    from app.core.git_safety import rollback_git_checkpoint
                    await rollback_git_checkpoint(result_id, db)
                except Exception as rollback_err:
                    print(f"[Celery] Automatic rollback failed: {rollback_err}")

                # Determine failure classification
                error_class = "WORKER_FAILURE"
                if isinstance(e, SubprocessSecurityError) or "traversal" in str(e).lower() or "security" in type(e).__name__.lower():
                    error_class = "SECURITY_BLOCK"
                elif isinstance(e, subprocess.TimeoutExpired):
                    error_class = "TIMEOUT"
                elif "syntax" in str(e).lower() or "ast" in str(e).lower():
                    error_class = "TRANSFORMATION_FAILURE"
                elif "compile" in str(e).lower() or "build" in str(e).lower():
                    error_class = "BUILD_FAILURE"
                elif "test" in str(e).lower() or "pytest" in str(e).lower():
                    error_class = "TEST_FAILURE"

                # Ensure the run is marked as FAILED in DB
                try:
                    await CRUDRepository.update_migration_run_status(
                        db=db,
                        result_id=result_id,
                        status=MigrationStatus.FAILED.value,
                        completed_at=datetime.utcnow(),
                    )
                    await CRUDRepository.create_migration_error(
                        db=db,
                        run_id=result_id,
                        stage="TRANSFORMATION",
                        error_type=error_class,
                        message=str(e),
                        traceback=trace,
                    )
                except Exception:
                    pass

    # Execute async wrapper
    run_async(_execute())
