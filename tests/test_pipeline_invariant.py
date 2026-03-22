"""
test_pipeline_invariant.py - V-009 Pipeline Invariant Tests

Tests 1 and 7: The hourglass invariant.

White paper Part III ("The Pipeline"): "Every Grove Autonomaton interaction
traverses the same five-stage pipeline, regardless of surface, device, or
complexity."

TCP/IP paper §III ("The Hourglass"): "the five-stage pipeline is the thin
waist of the cognitive hourglass... the pipeline is deliberately minimal."

V-009 Testing Philosophy: Assert on telemetry traces, not PipelineContext
attributes. The trace is the contract. Glass is presentation.
"""

import pytest
from unittest.mock import patch
from tests.conftest import PIPELINE_STAGES


def _stage_traces(telemetry_sink):
    """Extract only the 5 canonical pipeline stage traces.

    White paper Part III ("Feed-First Telemetry"): "The telemetry serves
    triple duty: learning, observability, and compliance." Handler-level
    error traces are observability. Pipeline stage traces are the contract.
    This filter separates the two.
    """
    return [
        e for e in telemetry_sink
        if e.get("inferred", {}).get("stage") in PIPELINE_STAGES
    ]



class TestPipelineInvariant:
    """
    Test 1: Pipeline Invariant — Five Stages, Every Time

    White paper Part III: "The stages are named for what happens at each
    one: Telemetry, Recognition, Compilation, Approval, Execution."

    TCP/IP paper §III: "every cognitive interaction must pass through
    the same five stages in the same order — and that each stage
    produces a structured trace."
    """

    def test_five_stages_every_time(self, telemetry_sink, mock_llm):
        """
        INPUT:  "hello"
        MOCK:   mock_llm (general_chat handler calls LLM for persona response)
        ASSERT: Exactly 5 pipeline stage traces in canonical order.

        mock_llm is required because the general_chat handler calls call_llm()
        to generate a persona response. Model Independence (Principle 7):
        the test validates the pipeline structure, not the model output.
        """
        from engine.pipeline import run_pipeline

        # Provide a response for general_chat handler
        mock_llm.append("Hello! I'm the reference engine.")

        run_pipeline(raw_input="hello", source="test")

        # Filter to pipeline stage traces only
        stages = _stage_traces(telemetry_sink)

        # Exactly 5 pipeline stages
        assert len(stages) == 5, \
            f"Expected 5 stage traces, got {len(stages)}. " \
            f"Stages found: {[e.get('inferred', {}).get('stage') for e in stages]}"

        # Stages in canonical order
        stage_names = [e.get("inferred", {}).get("stage") for e in stages]
        assert stage_names == ["telemetry", "recognition", "compilation", "approval", "execution"], \
            f"Stages out of order: {stage_names}"

        # Recognition: keyword match → general_chat
        recognition = stages[1]
        assert recognition["intent"] == "general_chat", \
            f"Expected intent 'general_chat', got '{recognition.get('intent')}'"
        assert recognition["tier"] == 1, \
            f"Expected tier 1 (keyword), got {recognition.get('tier')}"
        assert recognition.get("inferred", {}).get("method") == "keyword", \
            f"Expected method 'keyword', got '{recognition.get('inferred', {}).get('method')}'"

        # Approval: green zone, auto-approve
        approval = stages[3]
        assert approval["zone_context"] == "green", \
            f"Expected zone 'green', got '{approval.get('zone_context')}'"
        label = approval.get("inferred", {}).get("label", "")
        assert "auto-approve" in label.lower(), \
            f"Expected 'auto-approve' in label, got '{label}'"

        # Execution: dispatched to general_chat handler
        execution = stages[4]
        assert execution.get("inferred", {}).get("handler") == "general_chat", \
            f"Expected handler 'general_chat', got '{execution.get('inferred', {}).get('handler')}'"


    def test_status_commands_traverse_all_stages(self, telemetry_sink):
        """
        Status queries (skills, queue, dock) must traverse all 5 stages.

        Invariant #1: No jumping from input to execution. These commands
        use status_display handler which doesn't call LLM — no mock needed.
        """
        from engine.pipeline import run_pipeline

        for cmd in ["skills", "queue", "dock"]:
            telemetry_sink.clear()
            run_pipeline(raw_input=cmd, source="test")

            stages = _stage_traces(telemetry_sink)
            assert len(stages) == 5, \
                f"'{cmd}': Expected 5 stage traces, got {len(stages)}"

            stage_names = [e.get("inferred", {}).get("stage") for e in stages]
            assert stage_names == ["telemetry", "recognition", "compilation", "approval", "execution"], \
                f"'{cmd}': Stages out of order: {stage_names}"


class TestCleanStartup:
    """
    Test 7: Clean Startup — No LLM Before Operator Input

    White paper Part IV ("The Pipeline"): "The system's job is to make
    capture effortless — zero initiation cost." The pipeline is for
    operator interactions. Startup is infrastructure.
    """

    def test_no_telemetry_before_operator_input(self, telemetry_sink):
        """
        Initialize the engine. Assert zero telemetry, zero LLM calls,
        zero Jidoka prompts before the first operator input.
        """
        from engine.profile import set_profile
        from engine.cognitive_router import reset_router, get_router
        from engine.dock import get_dock

        llm_calls = []
        jidoka_calls = []

        def track_llm(*args, **kwargs):
            llm_calls.append(1)
            return '{"intent": "unknown", "confidence": 0.0}'

        def track_jidoka(*args, **kwargs):
            jidoka_calls.append(1)
            return "1"

        with patch('engine.llm_client.call_llm', side_effect=track_llm):
            with patch('engine.ux.ask_jidoka', side_effect=track_jidoka):
                set_profile("reference")
                reset_router()
                router = get_router()
                dock = get_dock()
                dock.ingest()

        assert len(telemetry_sink) == 0, \
            f"Expected 0 telemetry entries before operator input, got {len(telemetry_sink)}"
        assert len(llm_calls) == 0, \
            f"Expected 0 LLM calls during startup, got {len(llm_calls)}"
        assert len(jidoka_calls) == 0, \
            f"Expected 0 Jidoka prompts during startup, got {len(jidoka_calls)}"
        assert router is not None and len(router.routes) > 0, \
            "Router should be initialized with routes"


    def test_first_input_triggers_first_telemetry(self, telemetry_sink):
        """
        Before input: zero traces. After input: exactly 5 stage traces.

        Pipeline invariant: one operator input = one pipeline traversal.
        """
        from engine.pipeline import run_pipeline

        assert len(telemetry_sink) == 0, "No traces before first input"

        run_pipeline(raw_input="dock", source="test")

        stages = _stage_traces(telemetry_sink)
        assert len(stages) == 5, \
            f"First input should produce 5 stage traces, got {len(stages)}"

        first_trace = stages[0]
        assert first_trace.get("inferred", {}).get("stage") == "telemetry", \
            f"First trace should be 'telemetry' stage"
