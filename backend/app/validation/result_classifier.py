from typing import List, Dict
from app.validation.models import ValidationResult, ValidationStatus, ValidationSummary, ProjectMap

def classify_results(baseline_results: List[ValidationResult],
                     modernized_results: List[ValidationResult],
                     optimized_results: List[ValidationResult],
                     project_map: ProjectMap) -> ValidationSummary:
    
    summary = ValidationSummary(workspace_root=project_map.workspace_root)
    summary.total_projects_discovered = len(project_map.projects)
    
    # Organize by (project_id, command)
    baseline_dict = {(r.project, r.command): r for r in baseline_results}
    mod_dict = {(r.project, r.command): r for r in modernized_results}
    opt_dict = {(r.project, r.command): r for r in optimized_results}
    
    all_keys = set(baseline_dict.keys()) | set(mod_dict.keys()) | set(opt_dict.keys())
    
    # If a project has no build commands, we can emit NOT_APPLICABLE
    for proj in project_map.projects:
        if not proj.build_commands and not proj.test_commands:
            summary.results.append(ValidationResult(
                project=proj.project_id,
                project_type=proj.project_type,
                command="None",
                status=ValidationStatus.NOT_APPLICABLE,
                message="No applicable build/test commands found."
            ))
            summary.not_applicable += 1
            
    for key in all_keys:
        summary.commands_resolved += 1
        b_res = baseline_dict.get(key)
        m_res = mod_dict.get(key)
        o_res = opt_dict.get(key)
        
        # Determine the effective result structure to return
        # We start with the latest run (optimized, or modernized, or baseline)
        final_res = o_res if o_res else (m_res if m_res else b_res)
        if not final_res: continue
        
        # Clone to not mutate original
        result = ValidationResult(**final_res.dict())
        
        b_status = b_res.status if b_res else None
        m_status = m_res.status if m_res else None
        o_status = o_res.status if o_res else None
        
        result.baseline_status = b_status
        result.modernized_status = m_status
        result.optimized_status = o_status
        
        # Determine overall category
        if b_status == ValidationStatus.PASS and m_status == ValidationStatus.PASS and (o_status == ValidationStatus.PASS or not o_status):
            result.status = ValidationStatus.PASS
            summary.successful_validations += 1
            
        elif b_status == ValidationStatus.PASS and m_status == ValidationStatus.FAIL:
            result.status = ValidationStatus.MODERNIZATION_REGRESSION
            summary.modernization_regressions += 1
            
        elif b_status == ValidationStatus.FAIL and m_status == ValidationStatus.FAIL:
            # Check signature (for simplicity, we assume same if both are FAIL)
            result.status = ValidationStatus.PRE_EXISTING_FAILURE
            summary.pre_existing_failures += 1
            
        elif m_status == ValidationStatus.PASS and o_status == ValidationStatus.FAIL:
            result.status = ValidationStatus.OPTIMIZATION_REGRESSION
            summary.optimization_regressions += 1
            
        elif b_status == ValidationStatus.ENVIRONMENT_BLOCKED or m_status == ValidationStatus.ENVIRONMENT_BLOCKED:
            result.status = ValidationStatus.ENVIRONMENT_BLOCKED
            summary.environment_blocked += 1
            
        else:
            # Fallback
            result.status = m_status if m_status else b_status
            if result.status == ValidationStatus.PASS: summary.successful_validations += 1
            
        summary.results.append(result)
        
    return summary
