# Workflow Lifecycle Mode Implementation Plan

## Context

The current `AgentLoop.run()` always runs a full ReAct cycle (Think → Act → Observe → Reflect),
consuming 2 LLM calls per iteration even for skills with pre-defined, deterministic workflows.
This is wasteful for production software business scenarios where:

- **Scenario 1 (Fixed Workflow)**: Skill has a complete workflow with all tools configured
  → should execute directly, no LLM overhead
- **Scenario 2 (Build Workflow)**: Skill has a business process description but no fixed workflow
  → should build once, then execute fast on subsequent calls

The goal is a **Workflow Lifecycle Mode** that routes execution based on skill type and workflow availability.

## Architecture

```
AgentLoop.run(task, context)
  │
  ├─ _resolve_skill() → SkillMatcher (no LLM, keyword+embedding)
  │
  ├─ if skill.type=="fixed" && workflows.main exists
  │   └─ ★ Fast Path: SkillEngine.execute() → WorkflowEngine → return
  │       (0 LLM calls for routing, 0-1 for optional post-eval)
  │
  ├─ if skill.type=="flexible" && process_description exists
  │   └─ ★ Build Path: SkillEngine.execute() → DynamicWorkflowBuilder → execute → persist → return
  │       (1 LLM call for build, next call takes Fast Path)
  │
  └─ else → Full ReAct cycle (unchanged)
```

## Files to Modify (8 files)

### 1. `app/agent/models.py` — Add ExecutionMode enum + extend TaskResult

- Add `ExecutionMode(str, Enum)`: FAST_PATH, BUILD_PATH, REACT
- Add `execution_mode: ExecutionMode = ExecutionMode.REACT` to `TaskResult`
- Default REACT ensures backward compatibility

### 2. `app/skill/validator.py` — Relax validation for flexible skills

Current code rejects ALL skills without `workflows.main`. Change to:
- **Fixed skills**: require `workflows.main` (unchanged)
- **Flexible skills**: require `process_description` instead; if `workflows.main` is set, validate its existence

### 3. `app/workflow/engine.py` — Add disk persistence for workflow definitions

- Add `workflows_dir: str` param to `__init__`
- Add `save_definition(definition) -> bool`: writes YAML to disk
- Add `load_definitions_from_disk() -> int`: loads YAML at startup for restart recovery

### 4. `app/skill/engine.py` — Add persist_workflow + wire into solidification

- Add `persist_workflow(workflow_name) -> bool`: delegates to `workflow_engine.save_definition()`
- In `execute()`, after `promote_skill()`, call `persist_workflow()` to save to disk

### 5. `config/settings.yaml` — Add workflow_lifecycle section

```yaml
workflow_lifecycle:
  enable_post_evaluation: false
  fast_path_confidence_threshold: 0.6
  auto_persist_workflows: true
```

### 6. `app/agent/loop.py` — Main orchestration change (largest diff)

**Replace `run()` method**: Add lifecycle routing before the ReAct loop fallback.

**Add 4 new methods**:
- `_resolve_skill(task, context) -> (skill_name, match)`: Uses SkillMatcher only (no LLM)
- `_fast_path(skill_name, skill_def, task, context) -> TaskResult`: Calls SkillEngine.execute() directly
- `_build_path(skill_name, skill_def, task, context) -> TaskResult`: Builds workflow, executes, persists
- `_post_evaluate(task, context, skill_result) -> Dict`: Single LLM call for quality evaluation

### 7. `tests/unit/test_skill_validator.py` — New file

6 test cases for relaxed validation.

### 8. `tests/unit/test_agent_loop.py` — Add lifecycle tests

10 test cases for fast path, build path, fallback, post-eval, degradation handling.

## Data Flow Summary

| Path | LLM Calls | Latency | When Used |
|------|-----------|---------|-----------|
| Fast Path | 0 (or 1 w/ post-eval) | ~250ms | fixed skill + workflow exists |
| Build Path | 1-2 (build + eval) | ~4s | flexible skill, first call |
| ReAct | 2+ per iteration | ~4.5s+ | no skill match |

## Implementation Order

1. `app/agent/models.py` (no deps)
2. `app/skill/validator.py` (no deps)
3. `app/workflow/engine.py` (no deps)
4. `app/skill/engine.py` (depends on 3)
5. `config/settings.yaml` (no deps)
6. `app/agent/loop.py` (depends on 1, 4, 5)
7. `tests/unit/test_skill_validator.py` (depends on 2)
8. `tests/unit/test_agent_loop.py` (depends on 6)

## What Does NOT Change

- `_think()`, `_act()`, `_observe()`, `_reflect()` — preserved for ReAct fallback
- `SkillExecutor._execute_with_degradation()` — reused as-is
- `DynamicWorkflowBuilder.build_workflow()` — reused as-is
- `WorkflowEngine.execute()` — reused as-is
- `SkillRegistry.promote_skill()` — reused as-is
- `SkillMatcher.match()` — reused as-is
