# ADAAD Repository Inventory Report

## 1) Clean tree view (depth 5), grouped by subsystem

### runtime/

```text
runtime/
├── agents/
│   ├── __init__.py
│   └── economy.py
├── analysis/
│   ├── __init__.py
│   ├── adversarial_scenario_harness.py
│   ├── impact_predictor.py
│   └── redteam_harness.py
├── api/
│   ├── __init__.py
│   ├── agents.py
│   ├── app_layer.py
│   ├── legacy_modes.py
│   ├── mutation.py
│   ├── mutation_runtime.py
│   ├── orchestration.py
│   └── runtime_services.py
├── autonomy/
│   ├── __init__.py
│   ├── adaptive_budget.py
│   ├── agent_bandit_selector.py
│   ├── ai_mutation_proposer.py
│   ├── bandit_selector.py
│   ├── epoch_memory_store.py
│   ├── epoch_telemetry.py
│   ├── explore_exploit_controller.py
│   ├── fitness_landscape.py
│   ├── learning_signal_extractor.py
│   ├── loop.py
│   ├── mutation_scaffold.py
│   ├── non_stationarity_detector.py
│   ├── penalty_adaptor.py
│   ├── proposal_diff_renderer.py
│   ├── reward_learning.py
│   ├── roadmap_amendment_engine.py
│   ├── roles.py
│   ├── scoreboard.py
│   └── weight_adaptor.py
├── boot/
│   ├── __init__.py
│   ├── artifact_verifier.py
│   └── preflight.py
├── capability/
│   ├── __init__.py
│   ├── capability_node.py
│   ├── capability_registry.py
│   ├── capability_target_discovery.py
│   └── contracts.py
├── economic/
│   ├── __init__.py
│   ├── ingestion.py
│   └── schema.py
├── evolution/
│   ├── budget/
│   │   ├── __init__.py
│   │   ├── arbitrator.py
│   │   ├── competition_ledger.py
│   │   ├── cross_node_arbitrator.py
│   │   ├── darwinian_pipeline.py
│   │   └── pool.py
│   ├── config/
│   │   └── fitness_weights.json
│   ├── evidence/
│   │   ├── __init__.py
│   │   └── schemas.py
│   ├── lineage/
│   │   ├── __init__.py
│   │   ├── compatibility_matrix.py
│   │   ├── lineage_engine.py
│   │   ├── lineage_node.py
│   │   └── niche_registry.py
│   ├── state/
│   │   └── .gitkeep
│   ├── __init__.py
│   ├── adversarial_fitness.py
│   ├── agm_event.py
│   ├── baseline.py
│   ├── change_classifier.py
│   ├── checkpoint.py
│   ├── checkpoint_chain.py
│   ├── checkpoint_events.py
│   ├── checkpoint_registry.py
│   ├── checkpoint_verifier.py
│   ├── constitutional_evolution_loop.py
│   ├── cycle_telemetry.py
│   ├── economic_fitness.py
│   ├── entropy_detector.py
│   ├── entropy_discipline.py
│   ├── entropy_fast_gate.py
│   ├── entropy_forecast.py
│   ├── entropy_metadata.py
│   ├── entropy_policy.py
│   ├── epoch.py
│   ├── event_signing.py
│   ├── evidence_bundle.py
│   ├── evolution_kernel.py
│   ├── evolution_loop.py
│   ├── fast_path_scorer.py
│   ├── fitness.py
│   ├── fitness_orchestrator.py
│   ├── fitness_regression.py
│   ├── fitness_signal_adapter.py
│   ├── fitness_v2.py
│   ├── fitness_weight_tuner.py
│   ├── goal_graph.json
│   ├── goal_graph.py
│   ├── governor.py
│   ├── impact.py
│   ├── ledger_pruner.py
│   ├── lineage_dag.py
│   ├── lineage_v2.py
│   ├── metrics_schema.py
│   ├── mutation_budget.py
│   ├── mutation_budget_manager.py
│   ├── mutation_credit_ledger.py
│   ├── mutation_fitness_evaluator.py
│   ├── mutation_operator_framework.py
│   ├── mutation_route_optimizer.py
│   ├── population_manager.py
│   ├── promotion_events.py
│   ├── promotion_manifest.py
│   ├── promotion_policy.py
│   ├── promotion_state_machine.py
│   ├── proposal_engine.py
│   ├── replay.py
│   ├── replay_attestation.py
│   ├── replay_mode.py
│   ├── replay_proof.py
│   ├── replay_service.py
│   ├── replay_verifier.py
│   ├── roi_attribution.py
│   ├── runtime.py
│   ├── scoring.py
│   ├── scoring_algorithm.py
│   ├── scoring_ledger.py
│   ├── scoring_validator.py
│   ├── semantic_diff.py
│   ├── simulation_runner.py
│   └── telemetry_audit.py
├── governance/
│   ├── federation/
│   │   ├── tests/
│   │   │   ├── test_coherence_validator.py
│   │   │   ├── test_federation_coordination.py
│   │   │   ├── test_federation_hmac_key_validation.py
│   │   │   └── test_federation_transport_protocol_security.py
│   │   ├── __init__.py
│   │   ├── coherence_validator.py
│   │   ├── consensus.py
│   │   ├── coordination.py
│   │   ├── evolution_federation_bridge.py
│   │   ├── federated_evidence_matrix.py
│   │   ├── key_registry.py
│   │   ├── manifest.py
│   │   ├── mutation_broker.py
│   │   ├── node_supervisor.py
│   │   ├── peer_discovery.py
│   │   ├── proposal_transport_adapter.py
│   │   ├── protocol.py
│   │   └── transport.py
│   ├── foundation/
│   │   ├── __init__.py
│   │   ├── canonical.py
│   │   ├── clock.py
│   │   ├── determinism.py
│   │   ├── hashing.py
│   │   └── safe_access.py
│   ├── simulation/
│   │   ├── __init__.py
│   │   ├── constraint_interpreter.py
│   │   ├── dsl_grammar.py
│   │   ├── epoch_simulator.py
│   │   └── profile_exporter.py
│   ├── validators/
│   │   ├── __init__.py
│   │   ├── promotion_contract.py
│   │   └── resource_bounds.py
│   ├── __init__.py
│   ├── admission_audit_ledger.py
│   ├── admission_band_enforcer.py
│   ├── admission_tracker.py
│   ├── amendment.py
│   ├── amendment_pipeline.py
│   ├── branch_manager.py
│   ├── canon_law.py
│   ├── canon_law_v1.yaml
│   ├── certifier_scan_ledger.py
│   ├── constitution.yaml
│   ├── constitutional_amendment.py
│   ├── coverage_reporter.py
│   ├── debt_ledger.py
│   ├── decision_contract.py
│   ├── decision_pipeline.py
│   ├── deterministic_envelope.py
│   ├── deterministic_filesystem.py
│   ├── event_taxonomy.py
│   ├── exception_tokens.py
│   ├── founders_law.json
│   ├── founders_law_v2.py
│   ├── gate.py
│   ├── gate_certifier.py
│   ├── gate_decision_ledger.py
│   ├── gate_v2.py
│   ├── health_aggregator.py
│   ├── health_pressure_adaptor.py
│   ├── health_service.py
│   ├── human_approval_gate.py
│   ├── instability_calculator.py
│   ├── law_evolution_certificate.py
│   ├── mutation_admission.py
│   ├── mutation_ledger.py
│   ├── mutation_risk_scorer.py
│   ├── parallel_gate.py
│   ├── phase_transition_gate.py
│   ├── policy_adapter.py
│   ├── policy_artifact.py
│   ├── policy_lifecycle.py
│   ├── policy_validator.py
│   ├── pr_lifecycle_event_contract.py
│   ├── pressure_audit_ledger.py
│   ├── promotion_gate.py
│   ├── resource_accounting.py
│   ├── response_schema_validator.py
│   ├── review_pressure.py
│   ├── review_quality.py
│   ├── reviewer_reputation.py
│   ├── reviewer_reputation_ledger.py
│   ├── risk_thresholds.yaml
│   ├── schema_validator.py
│   ├── threat_monitor.py
│   └── threat_scan_ledger.py
├── intake/
│   ├── __init__.py
│   ├── intake_schema.py
│   ├── repo_scanner.py
│   ├── scan_rules.py
│   ├── stage_branch_creator.py
│   └── zip_intake.py
├── integrations/
│   ├── __init__.py
│   ├── aponi_sync.py
│   ├── github_app_token.py
│   └── github_webhook_handler.py
├── integrity/
│   ├── __init__.py
│   └── repo_ledger_sync.py
├── intelligence/
│   ├── __init__.py
│   ├── critique.py
│   ├── critique_signal.py
│   ├── file_telemetry_sink.py
│   ├── llm_provider.py
│   ├── planning.py
│   ├── proposal.py
│   ├── proposal_adapter.py
│   ├── routed_decision_telemetry.py
│   ├── router.py
│   ├── strategy.py
│   └── strategy_analytics.py
├── manifest/
│   ├── __init__.py
│   ├── generator.py
│   └── validator.py
├── market/
│   ├── adapters/
│   │   ├── __init__.py
│   │   └── live_adapters.py
│   ├── __init__.py
│   ├── federated_signal_broker.py
│   ├── feed_registry.py
│   ├── market_fitness_integrator.py
│   └── market_signal_adapter.py
├── mcp/
│   ├── __init__.py
│   ├── candidate_ranker.py
│   ├── evolution_pipeline_tools.py
│   ├── linting_bridge.py
│   ├── mutation_analyzer.py
│   ├── proposal_queue.jsonl.tail.json
│   ├── proposal_queue.py
│   ├── proposal_validator.py
│   ├── rejection_explainer.py
│   ├── server.py
│   └── tools_registry.py
├── memory/
│   ├── __init__.py
│   ├── context_filter_chain.py
│   ├── context_replay_interface.py
│   ├── craft_pattern_extractor.py
│   ├── reward_signal_bridge.py
│   ├── soulbound_key.py
│   └── soulbound_ledger.py
├── mutation/
│   ├── ast_substrate/
│   │   ├── __init__.py
│   │   ├── ast_diff_patch.py
│   │   ├── patch_applicator.py
│   │   ├── sandbox_tournament.py
│   │   └── static_scanner.py
│   ├── code_intel/
│   │   ├── __init__.py
│   │   ├── code_intel_model.py
│   │   ├── function_graph.py
│   │   ├── hotspot_map.py
│   │   └── mutation_history.py
│   └── __init__.py
├── platform/
│   ├── __init__.py
│   ├── android_monitor.py
│   └── storage_manager.py
├── recovery/
│   ├── __init__.py
│   ├── ledger_guardian.py
│   └── tier_manager.py
├── sandbox/
│   ├── container_profiles/
│   │   ├── default_network.json
│   │   ├── default_resources.json
│   │   ├── default_seccomp.json
│   │   ├── market_burst.json
│   │   └── market_constrained.json
│   ├── __init__.py
│   ├── container_health.py
│   ├── container_orchestrator.py
│   ├── environment_snapshot.py
│   ├── ephemeral_clone.py
│   ├── evidence.py
│   ├── executor.py
│   ├── fs_rules.py
│   ├── isolation.py
│   ├── manifest.py
│   ├── market_driven_profiler.py
│   ├── namespace.py
│   ├── network_rules.py
│   ├── policy.py
│   ├── preflight.py
│   ├── replay.py
│   ├── resources.py
│   ├── sandbox_policy.py
│   └── syscall_filter.py
├── state/
│   ├── __init__.py
│   ├── epoch_memory.jsonl
│   ├── ledger_store.py
│   ├── migration.py
│   ├── mutation_job_queue.py
│   ├── mutation_job_transitions.py
│   └── registry_store.py
├── tools/
│   ├── code_mutation_guard.py
│   ├── execution_contract.py
│   ├── mutation_fs.py
│   ├── mutation_guard.py
│   ├── mutation_tx.py
│   └── rollback_certificate.py
├── __init__.py
├── capabilities.py
├── capability_graph.py
├── constants.py
├── constitution.py
├── director.py
├── element_registry.py
├── fitness.py
├── fitness_pipeline.py
├── fitness_v2.py
├── founders_law.py
├── governance_surface.py
├── import_guard.py
├── invariants.py
├── legitimacy.py
├── memory_adapter.py
├── metrics.py
├── metrics_analysis.py
├── mutation_lifecycle.py
├── preflight.py
├── README.md
├── report_version.py
├── test_sandbox.py
├── timeutils.py
└── warm_pool.py
```

### app/

```text
app/
├── agents/
│   ├── agent_template/
│   │   ├── certificate.json
│   │   ├── dna.json
│   │   └── meta.json
│   ├── lineage/
│   │   └── .gitkeep
│   ├── sample_agent/
│   │   ├── __init__.py
│   │   ├── certificate.json
│   │   ├── dna.json
│   │   └── meta.json
│   ├── test_subject/
│   │   ├── __init__.py
│   │   ├── certificate.json
│   │   ├── dna.json
│   │   └── meta.json
│   ├── __init__.py
│   ├── architect_governor.py
│   ├── architect_graph_v1.py
│   ├── base_agent.py
│   ├── claude_proposal_agent.py
│   ├── discovery.py
│   ├── invariants.py
│   ├── mutation_engine.py
│   ├── mutation_request.py
│   ├── mutation_strategies.py
│   └── README.md
├── api/
│   ├── nexus/
│   │   ├── __init__.py
│   │   └── mutate.py
│   └── __init__.py
├── orchestration/
│   ├── __init__.py
│   ├── contracts.py
│   └── mutation_orchestration_service.py
├── __init__.py
├── architect_agent.py
├── beast_mode_loop.py
├── boot_preflight.py
├── cli_args.py
├── dream_mode.py
├── main.py
├── mutation_cycle.py
├── mutation_executor.py
├── README.md
├── replay_verification.py
├── root.py
└── simulation_utils.py
```

### adaad/

```text
adaad/
├── agents/
│   ├── agent_template/
│   │   ├── certificate.json
│   │   ├── dna.json
│   │   └── meta.json
│   ├── lineage/
│   │   └── .gitkeep
│   ├── sample_agent/
│   │   ├── __init__.py
│   │   ├── certificate.json
│   │   ├── dna.json
│   │   └── meta.json
│   ├── test_subject/
│   │   ├── __init__.py
│   │   ├── certificate.json
│   │   ├── dna.json
│   │   └── meta.json
│   ├── __init__.py
│   ├── agent_template.py
│   ├── architect_governor.py
│   ├── architect_graph_v1.py
│   ├── base_agent.py
│   ├── claude_proposal_agent.py
│   ├── discovery.py
│   ├── invariants.py
│   ├── mutation_engine.py
│   ├── mutation_request.py
│   ├── mutation_strategies.py
│   └── path_guard.py
├── core/
│   ├── __init__.py
│   ├── agent_contract.py
│   ├── cryovant.py
│   ├── cryovant_identity.py
│   ├── health.py
│   ├── logging_config.py
│   ├── manifest.py
│   ├── root.py
│   └── tool_contract.py
├── orchestrator/
│   ├── __init__.py
│   ├── bootstrap.py
│   ├── dispatcher.py
│   └── registry.py
├── tools/
│   ├── __init__.py
│   └── tool_template.py
└── __init__.py
```

### security/

```text
security/
├── keys/
│   └── .gitkeep
├── ledger/
│   ├── .gitkeep
│   ├── __init__.py
│   ├── append.py
│   ├── cryovant_journal.genesis.jsonl
│   ├── governance_events.jsonl
│   ├── journal.py
│   ├── lineage_v2.py
│   └── scoring.jsonl.tail.json
├── promotion_manifests/
│   ├── .gitkeep
│   ├── __init__.py
│   └── writer.py
├── __init__.py
├── canonical.py
├── challenge.py
├── challenge_store.py
├── cryovant.py
├── gatekeeper_protocol.py
├── key_rotation_attestation.py
├── README.md
└── replay_proof_keyring.json
```

### scripts/

```text
scripts/
├── amend_constitution.py
├── benchmark_corpus.json
├── build_release.sh
├── check_dependency_baseline.py
├── check_licenses.py
├── check_release_contents.py
├── check_spdx_headers.py
├── check_workflow_python_version.py
├── classify_pr_tier.py
├── enforce_forensic_retention.py
├── evaluate_shadow_governance.py
├── lint_active_docs_dependency_refs.py
├── migrate_archived_runtime_pipeline.py
├── orchestrate_release_candidates.py
├── pr_rule_checklist.py
├── run_dashboard.sh
├── run_release_benchmarks.py
├── run_simulation_runner.py
├── run_tier0_preflight.py
├── sign_artifact.sh
├── sign_policy_artifact.sh
├── sync_docs_on_merge.py
├── tier0_remediation.py
├── validate_adaad_agent_state.py
├── validate_architecture_snapshot.py
├── validate_benchmark_deltas.py
├── validate_docs_integrity.py
├── validate_governance_schemas.py
├── validate_key_rotation_attestation.py
├── validate_license_compliance.py
├── validate_manifest_inventory.py
├── validate_phase_sequence_consistency.py
├── validate_pr3h_acceptance.py
├── validate_readme_alignment.py
├── validate_release_evidence.py
├── validate_release_hardening_claims.py
├── validate_simplification_targets.py
├── validate_test_marker_inventory.py
├── verify_core.py
├── verify_core.sh
├── verify_critical_artifacts.py
├── verify_mutation_ledger.py
└── verify_policy_artifact.sh
```

### tools/

```text
tools/
├── formal/
│   └── amendment_state_model.py
├── .gitkeep
├── __init__.py
├── adaad_audit.py
├── asset_generator.py
├── enhanced_cli.py
├── epoch_analytics.py
├── error_dictionary.py
├── fitness_weight_tuner_job.py
├── fix_import_boundaries.py
├── governance_scenarios.json
├── interactive_onboarding.py
├── lint_determinism.py
├── lint_import_paths.py
├── monitor_entropy_health.py
├── profile_entropy_baseline.py
├── run_adversarial_scenario_harness.py
├── run_redteam_harness.py
├── simulate_governance_harness.py
├── validate_governance_runbook_refs.py
├── verify_filesystem_migration.py
├── verify_replay_attestation_bundle.py
└── verify_replay_bundle.py
```

### ui/

```text
ui/
├── aponi/
│   ├── mock/
│   │   └── .keep
│   ├── evidence_viewer.js
│   ├── fast_path_panel.js
│   ├── index.html
│   ├── parallel_gate_panel.js
│   ├── proposal_editor.js
│   ├── replay_inspector.js
│   └── simulation_panel.js
├── enhanced/
│   └── enhanced_dashboard.html
├── features/
│   ├── __init__.py
│   ├── evidence_panel.py
│   ├── federation_panel.py
│   ├── replay_panel.py
│   └── timeline.py
├── __init__.py
├── aponi_dashboard.py
└── README.md
```

### android/

```text
android/
├── .github/
│   └── workflows/
│       └── android-release.yml
├── app/
│   ├── src/
│   │   └── main/
│   │       ├── java/
│   │       │   └── com/
│   │       ├── res/
│   │       │   ├── values/
│   │       │   └── xml/
│   │       └── AndroidManifest.xml
│   ├── build.gradle
│   └── proguard-rules.pro
├── fastlane/
│   └── metadata/
│       └── android/
│           └── en-US/
│               ├── changelogs/
│               ├── full_description.txt
│               ├── short_description.txt
│               └── title.txt
├── fdroid/
│   └── com.innovativeai.adaad.yml
├── keystore/
│   └── README.md
├── play-store-assets/
│   └── SUBMISSION_RUNBOOK.md
├── .gitignore
├── build.gradle
├── obtainium.json
└── settings.gradle
```

### tests/

```text
tests/
├── acceptance/
│   └── pr3h/
│       ├── fixtures/
│       │   └── entropy_triage_replay_cases.json
│       └── test_pr3h_acceptance.py
├── architect/
│   └── test_architect_graph_v1.py
├── autonomy/
│   ├── __init__.py
│   ├── test_agent_bandit_selector.py
│   ├── test_evolution_loop_amendment.py
│   ├── test_pr11_a_02_wiring.py
│   ├── test_reward_learning.py
│   └── test_roadmap_amendment_engine.py
├── determinism/
│   ├── test_aponi_governance_determinism.py
│   ├── test_beast_mode_provider_determinism.py
│   ├── test_boot_runtime_profile.py
│   ├── test_concurrent_replay.py
│   ├── test_constitution_policy_determinism.py
│   ├── test_deterministic_envelope_costs.py
│   ├── test_dream_mode_provider_determinism.py
│   ├── test_entropy_anomaly_triage_replay.py
│   ├── test_envelope_concurrency.py
│   ├── test_filesystem_wrapper_migration.py
│   ├── test_lineage_v2_streaming.py
│   ├── test_replay_attestation_determinism.py
│   ├── test_replay_equivalence.py
│   ├── test_replay_runtime_harness.py
│   ├── test_runtime_provider_injection.py
│   └── test_scoring_algorithm_determinism.py
├── endpoints/
│   └── test_aponi_endpoint_contracts.py
├── evolution/
│   ├── test_checkpoint_integration.py
│   ├── test_checkpoint_registry.py
│   ├── test_checkpoint_verifier.py
│   ├── test_constitutional_evolution_loop.py
│   ├── test_entropy_baseline_profiler.py
│   ├── test_entropy_policy.py
│   ├── test_entropy_policy_enforcement.py
│   ├── test_entropy_policy_triage.py
│   ├── test_entropy_telemetry.py
│   ├── test_epoch_result_market_fields.py
│   ├── test_evidence_bundle.py
│   ├── test_evolution_loop_epoch_integration.py
│   ├── test_fitness_engine_v2.py
│   ├── test_fitness_orchestrator.py
│   ├── test_fitness_regression.py
│   ├── test_fitness_weight_tuner.py
│   ├── test_fitness_weights_contract.py
│   ├── test_governance_debt_ledger_wiring.py
│   ├── test_lineage_health_wiring.py
│   ├── test_metrics_schema.py
│   ├── test_monitor_entropy_health.py
│   ├── test_mutation_fitness_evaluator_policy.py
│   ├── test_promotion_evidence_bundle.py
│   ├── test_promotion_manifest_compat.py
│   ├── test_promotion_transitions.py
│   ├── test_proposal_engine_context_signals.py
│   ├── test_proposal_engine_evolution_wiring.py
│   ├── test_proposal_engine_llm.py
│   ├── test_replay_version_validator.py
│   └── test_telemetry_audit.py
├── fixtures/
│   └── governance/
│       └── shadow_replay_ledger.json
├── formal/
│   └── test_amendment_state_model.py
├── full_stack_upgrade/
│   └── test_full_stack_upgrade.py
├── generated/
│   ├── evidence/
│   │   ├── solo_agent_loop/
│   │   │   ├── agents/
│   │   │   │   └── solo_agent/
│   │   │   └── run.log
│   │   └── .gitkeep
│   ├── __init__.py
│   ├── adapters.py
│   ├── emit_metadata.py
│   ├── parsers.py
│   ├── test_generated_artifacts.py
│   └── test_sandbox_runtime.py
├── governance/
│   ├── contracts/
│   │   ├── __init__.py
│   │   ├── test_coverage_reporter_contracts.py
│   │   ├── test_governance_contracts.py
│   │   └── test_governance_simulation_harness.py
│   ├── federation/
│   │   ├── test_federated_amendment.py
│   │   ├── test_federation_key_registry.py
│   │   ├── test_federation_transport_trusted_keys.py
│   │   └── test_node_supervisor.py
│   ├── inviolability/
│   │   ├── test_constitution_policy_inviolability.py
│   │   ├── test_constitutional_inviolability.py
│   │   └── test_phase2_lineage_inviolability.py
│   ├── signals/
│   │   ├── test_aponi_governance_signals.py
│   │   ├── test_constitution_policy_signals.py
│   │   └── test_phase2_governance_signals.py
│   ├── __init__.py
│   ├── test_admission_audit_ledger.py
│   ├── test_admission_band_enforcer.py
│   ├── test_admission_tracker.py
│   ├── test_amendment_engine.py
│   ├── test_aponi_instability_and_policy_simulate.py
│   ├── test_aponi_log_append.py
│   ├── test_canon_law_enforcement.py
│   ├── test_certifier_scan_ledger.py
│   ├── test_certifier_security_scan.py
│   ├── test_constitution_market_signal_integrity.py
│   ├── test_constitution_v040.py
│   ├── test_debt_health_signal.py
│   ├── test_decision_pipeline_contract.py
│   ├── test_enforcement_verdict_audit.py
│   ├── test_epoch_simulator.py
│   ├── test_federation_coordination.py
│   ├── test_federation_protocol_contract.py
│   ├── test_federation_transport_contract.py
│   ├── test_gate_decision_ledger.py
│   ├── test_gate_v2.py
│   ├── test_governance_debt_ledger.py
│   ├── test_governance_debt_service.py
│   ├── test_governance_gate.py
│   ├── test_governance_health_aggregator.py
│   ├── test_governance_health_endpoint.py
│   ├── test_journal_append.py
│   ├── test_journal_integrity.py
│   ├── test_ledger_append.py
│   ├── test_ledger_guardian.py
│   ├── test_mutation_admission.py
│   ├── test_mutation_ledger_verification.py
│   ├── test_mutation_risk_scorer.py
│   ├── test_policy_adapter_runtime.py
│   ├── test_policy_artifact.py
│   ├── test_policy_lifecycle.py
│   ├── test_policy_validator.py
│   ├── test_pr_lifecycle_event_contract.py
│   ├── test_pr_lifecycle_reviewer_outcome.py
│   ├── test_profile_exporter.py
│   ├── test_promote_restriction.py
│   ├── test_promotion_contract.py
│   ├── test_review_pressure.py
│   ├── test_review_quality.py
│   ├── test_reviewer_reputation.py
│   ├── test_reviewer_reputation_ledger.py
│   ├── test_runtime_governance_adapters.py
│   ├── test_schema_validator.py
│   ├── test_simulation_dsl.py
│   ├── test_simulation_isolation.py
│   └── test_threat_scan_ledger.py
├── intake/
│   ├── test_repo_scanner.py
│   ├── test_stage_branch_creator.py
│   └── test_zip_intake.py
├── integration/
│   └── test_simulate_governance_harness_integration.py
├── market/
│   ├── __init__.py
│   ├── test_consecutive_synthetic_epochs.py
│   ├── test_federated_signal_broker.py
│   ├── test_feed_registry.py
│   └── test_market_fitness_integrator.py
├── mcp/
│   ├── __init__.py
│   ├── test_candidate_ranker.py
│   ├── test_linting_bridge.py
│   ├── test_mcp_server.py
│   ├── test_mutation_analyzer.py
│   ├── test_proposal_queue_tail.py
│   ├── test_proposal_validator.py
│   ├── test_rejection_explainer.py
│   └── test_tools_parity.py
├── memory/
│   ├── __init__.py
│   ├── test_context_replay_digest_verify.py
│   ├── test_pr10_01.py
│   ├── test_pr9_01.py
│   ├── test_pr9_02.py
│   ├── test_pr9_03.py
│   ├── test_pr9_03_wiring.py
│   └── test_soulbound_pr901.py
├── platform/
│   ├── conftest.py
│   ├── test_android_monitor.py
│   └── test_storage_manager.py
├── recovery/
│   └── test_tier_manager.py
├── runtime/
│   └── test_tool_execution_contract.py
├── sandbox/
│   ├── conftest.py
│   ├── test_fs_rules.py
│   ├── test_namespace_isolation.py
│   ├── test_sandbox_evidence.py
│   ├── test_sandbox_executor.py
│   ├── test_sandbox_hardening.py
│   ├── test_sandbox_isolation_enforcement.py
│   ├── test_sandbox_manifest_policy.py
│   ├── test_sandbox_policy_enforcement.py
│   ├── test_sandbox_replay.py
│   └── test_syscall_filter.py
├── scripts/
│   └── test_run_tier0_preflight.py
├── security/
│   ├── fixtures/
│   │   └── adversarial_governance_scenarios.json
│   ├── test_adversarial_scenario_harness.py
│   ├── test_challenge_store_concurrency.py
│   └── test_redteam_harness.py
├── server/
│   ├── test_phase41_cryovant_middleware_spa.py
│   └── test_phase42_defect_sweep.py
├── stability/
│   └── test_null_guards.py
├── state/
│   ├── test_ledger_store.py
│   ├── test_migration.py
│   ├── test_mutation_job_queue.py
│   ├── test_registry_store.py
│   └── test_versionedstore.py
├── __init__.py
├── conftest.py
├── test_adaad_core_and_dispatcher.py
├── test_adaad_core_primitives.py
├── test_adaad_v8_integration.py
├── test_admission_enforcement_endpoint.py
├── test_admission_rate_endpoint.py
├── test_admission_status_endpoint.py
├── test_agent_contract.py
├── test_agent_contract_validation.py
├── test_agent_meta.py
├── test_agm_event_determinism.py
├── test_ai_mutation_proposer.py
├── test_analytics_endpoints.py
├── test_aponi_dashboard_e2e.py
├── test_aponi_feature_modules_characterization.py
├── test_aponi_governance_intelligence.py
├── test_aponi_port_resolution.py
├── test_app_main_refactor_characterization.py
├── test_architect_governor_auth.py
├── test_ast_substrate_import.py
├── test_ast_substrate_phase60.py
├── test_audit_cli.py
├── test_autonomy_enhancements.py
├── test_autonomy_loop_intelligence_phase19.py
├── test_autonomy_loop_persistent_router_phase19.py
├── test_autonomy_public_api_phase20.py
├── test_autonomy_telemetry_sink.py
├── test_bandit_selector.py
├── test_base_agent.py
├── test_beast_mode_projection_inputs.py
├── test_beast_promotes_on_threshold.py
├── test_boot_constitution_preflight.py
├── test_boot_env_validation.py
├── test_boot_preflight_artifact_verification.py
├── test_boot_sanity.py
├── test_branch_protection_policy_workflow.py
├── test_capability_dependency.py
├── test_capability_graph_phase59.py
├── test_certifier_scans_endpoint.py
├── test_cf_fixes.py
├── test_change_classifier.py
├── test_checkpoint_chain.py
├── test_checkpoint_chain_new.py
├── test_code_intel_phase58.py
├── test_code_mutation_guard.py
├── test_complexity_delta.py
├── test_constitution_doc_version.py
├── test_constitution_policy.py
├── test_constitution_v0_6_0.py
├── test_container_orchestrator.py
├── test_critique_phase16.py
├── test_critique_signal_phase18.py
├── test_cross_node_budget_arbitrator.py
├── test_cryovant_ancestry.py
├── test_cryovant_dev_signatures.py
├── test_cryovant_env.py
├── test_cryovant_identity.py
├── test_cryovant_strict_env_rejection.py
├── test_cryovant_token_expiry.py
├── test_cryovant_verify_session_env_behavior.py
├── test_darwinian_budget.py
├── test_debt_and_certifier_endpoints.py
├── test_default_provider_strict_replay.py
├── test_dependency_baseline_guard.py
├── test_dna_clone_integrity.py
├── test_dry_run_simulation.py
├── test_dsl_grammar.py
├── test_economic_fitness.py
├── test_endpoint_contract_matrix.py
├── test_entropy_budget.py
├── test_entropy_discipline_replay.py
├── test_entropy_fast_gate.py
├── test_entropy_forecast_and_threat_monitor.py
├── test_entropy_integration.py
├── test_epoch_law_transition.py
├── test_epoch_telemetry.py
├── test_evidence_bundle_federated.py
├── test_evidence_viewer.py
├── test_evolution_audit_grade.py
├── test_evolution_federation_bridge.py
├── test_evolution_governor.py
├── test_evolution_infrastructure.py
├── test_evolution_kernel.py
├── test_evolution_loop.py
├── test_evolution_runtime.py
├── test_fast_path_api_endpoints.py
├── test_fast_path_scorer.py
├── test_federated_evidence_matrix.py
├── test_federation_autonomous.py
├── test_federation_mutation_broker.py
├── test_file_telemetry_sink.py
├── test_fitness_deterministic.py
├── test_fitness_landscape.py
├── test_fitness_pipeline.py
├── test_fix_import_boundaries.py
├── test_forensic_retention_script.py
├── test_founders_law_policy.py
├── test_founders_law_v2.py
├── test_gate_decisions_endpoint.py
├── test_gatekeeper_protocol.py
├── test_goal_graph.py
├── test_governance_foundation.py
├── test_governance_health_pressure_field.py
├── test_governance_health_routing_field.py
├── test_governance_surface.py
├── test_health_payload.py
├── test_health_pressure_adaptor.py
├── test_impact_predictor.py
├── test_import_roots.py
├── test_intelligence_proposal_adapter.py
├── test_intelligence_public_api_phase20.py
├── test_intelligence_router.py
├── test_intelligence_strategy.py
├── test_invariants.py
├── test_key_rotation_attestation.py
├── test_key_rotation_status.py
├── test_law_evolution_certificate.py
├── test_legacy_modes_flag.py
├── test_legitimacy.py
├── test_lineage_ancestry_validation.py
├── test_lineage_continuity.py
├── test_lineage_engine_phase61.py
├── test_lineage_federation_origin.py
├── test_lineage_v2_integrity.py
├── test_lint_determinism.py
├── test_lint_import_paths.py
├── test_llm_provider.py
├── test_manifest_generation.py
├── test_manifest_outputs.py
├── test_market_driven_profiler.py
├── test_market_fitness_bridge.py
├── test_market_fitness_integrator.py
├── test_market_ingestion.py
├── test_metrics_analysis_determinism.py
├── test_metrics_analysis_lineage_factory.py
├── test_metrics_tail_streaming.py
├── test_metrics_write.py
├── test_mutation_credit_ledger.py
├── test_mutation_executor_goal_graph_init.py
├── test_mutation_guard.py
├── test_mutation_ledger_endpoint.py
├── test_mutation_lifecycle.py
├── test_mutation_operator_framework.py
├── test_mutation_rate.py
├── test_mutation_rate_rule.py
├── test_mutation_request_governed_fields.py
├── test_mutation_route_optimizer.py
├── test_mutation_scaffold_v2.py
├── test_mutation_strategies.py
├── test_mutation_strategy_adapter.py
├── test_mutation_transaction.py
├── test_nexus_health_gate_ok.py
├── test_nexus_setup.py
├── test_non_stationarity_detector.py
├── test_orchestration_contracts.py
├── test_orchestrator_dispatcher.py
├── test_orchestrator_replay_mode.py
├── test_parallel_gate.py
├── test_parallel_gate_api.py
├── test_penalty_adaptor.py
├── test_phase21_core_loop_closure.py
├── test_phase22_proposal_hardening.py
├── test_phase23_container_isolation.py
├── test_phase2_capabilities.py
├── test_phase4_semantic_scoring.py
├── test_phase50_federation_consensus.py
├── test_phase52_epoch_memory.py
├── test_phase53_evolution_loop_memory_wiring.py
├── test_phase54_aponi_ux.py
├── test_phase55_aponi_ux_polish.py
├── test_phase56_gate_initial_load_fix.py
├── test_phase57_proposal_engine_autoprovision.py
├── test_planning_module.py
├── test_policy_signing_scripts.py
├── test_population_manager.py
├── test_pr12_gate_ok.py
├── test_preflight_import_smoke.py
├── test_pressure_audit_ledger.py
├── test_pressure_history_endpoint.py
├── test_promotion_events.py
├── test_promotion_policy.py
├── test_promotion_state_machine.py
├── test_proposal_adapter_phase16.py
├── test_proposal_transport_adapter.py
├── test_readme_alignment_guard.py
├── test_real_mutation_cycle.py
├── test_release_orchestration_runner.py
├── test_replay_proof.py
├── test_replay_proof_tamper.py
├── test_replay_version_validator.py
├── test_report_versioning.py
├── test_resource_bounds.py
├── test_review_pressure_endpoint.py
├── test_review_pressure_ledger_wiring.py
├── test_reviewer_reputation_ledger_endpoint.py
├── test_roi_attribution_pipeline.py
├── test_rollback_certificate.py
├── test_routed_decision_telemetry_phase17.py
├── test_router_signal_wire_phase18.py
├── test_router_strategy_wire_phase17.py
├── test_routing_health_endpoint.py
├── test_routing_health_signal.py
├── test_runtime_api_lazy_imports.py
├── test_runtime_import_guard.py
├── test_sandbox_injection_hardening.py
├── test_scoring_hotpath_benchmarks.py
├── test_scoring_ledger.py
├── test_scoring_validator.py
├── test_seeded_determinism_provider.py
├── test_semantic_diff.py
├── test_senior_optimizations.py
├── test_server_audit_endpoints.py
├── test_server_import_smoke.py
├── test_server_operator_endpoints.py
├── test_server_ui_resolution.py
├── test_server_ws_events.py
├── test_shadow_governance_evaluator.py
├── test_simulation_endpoints.py
├── test_simulation_runner.py
├── test_staging_promotion.py
├── test_strategy_analytics.py
├── test_strategy_taxonomy_phase16.py
├── test_sync_docs_on_merge.py
├── test_telemetry_endpoint.py
├── test_test_sandbox.py
├── test_threat_scan_endpoint.py
├── test_tier_override.py
├── test_tool_contract.py
├── test_ux_tools_smoke.py
├── test_validate_adaad_agent_state.py
├── test_validate_agents.py
├── test_validate_manifest_inventory.py
├── test_validate_phase_sequence_consistency.py
├── test_validate_phase_sequence_consistency_regression.py
├── test_validate_release_evidence.py
├── test_validate_release_hardening_claims.py
├── test_warm_pool.py
└── test_weight_adaptor.py
```

### config/

```text
config/
└── governance/
    └── static_rules.yaml
```

### schemas/

```text
schemas/
├── aponi_responses/
│   ├── alerts_evaluate.schema.json
│   ├── evolution_timeline.schema.json
│   ├── policy_simulate.schema.json
│   ├── replay_diff.schema.json
│   ├── replay_divergence.schema.json
│   ├── reviewer_calibration.schema.json
│   ├── risk_instability.schema.json
│   ├── risk_summary.schema.json
│   └── system_intelligence.schema.json
├── mcp/
│   ├── analysis_response.v1.json
│   ├── proposal_request.v1.json
│   └── proposal_response.v1.json
├── checkpoint.v1.json
├── checkpoint_chain_event.v1.json
├── checkpoint_event.v1.json
├── entropy_metadata.v1.json
├── entropy_policy.v1.json
├── evidence_bundle.v1.json
├── federation_handshake_envelope.v1.json
├── federation_handshake_request.v1.json
├── federation_handshake_response.v1.json
├── federation_policy_exchange.v1.json
├── federation_replay_proof_bundle.v1.json
├── federation_transport_contract.v1.json
├── federation_vote.v1.json
├── fitness_weights.schema.json
├── governance_health_snapshot.v1.json
├── governance_policy_artifact.v1.json
├── governance_policy_payload.v1.json
├── governance_profile.v1.json
├── governance_simulation_policy.v1.json
├── intake_manifest.v1.json
├── llm_mutation_proposal.v1.json
├── manifest.v1.json
├── market_signal_reading.v1.json
├── memoryschema.json
├── mutation_manifest.v1.json
├── mutation_risk_report.v1.json
├── pr_lifecycle_event.v1.json
├── pr_lifecycle_event_stream.v1.json
├── promotion_policy.v1.json
├── replay_attestation.v1.json
├── routing_health_report.v1.json
├── sandbox_evidence.v1.json
├── sandbox_manifest.v1.json
├── sandbox_policy.v1.json
├── scan_report.v1.json
├── scoring_input.v1.json
├── scoring_result.v1.json
├── soulbound_context_event.v1.json
└── telemetry_decision_record.v1.json
```

### governance/

```text
governance/
├── foundation/
│   ├── __init__.py
│   ├── canonical.py
│   ├── clock.py
│   ├── determinism.py
│   └── hashing.py
├── __init__.py
├── CANONICAL_ENGINE_DECLARATION.md
├── constitutional_rule_count.json
├── DEPRECATION_REGISTRY.md
├── federation_trusted_keys.json
├── governance_policy_v1.json
├── mutation_ledger.py
├── policies.rego
├── promotion_gate.py
├── report_version.json
├── rule_applicability.yaml
├── simplification_targets.json
└── tier_map.yaml
```

## 2) Code-only LoC report (excluding docs/data)

Excluded roots: `docs/`, `data/`, `archives/`, `artifacts/`, `reports/`, `.git/`, `releases/`, `brand/`.

- Code files counted: **982**
- Total code-only LoC: **169602**

### LoC by extension

| Extension | LoC |
|---|---:|
| `.py` | 158700 |
| `.yml` | 2883 |
| `.js` | 2636 |
| `.html` | 1997 |
| `.yaml` | 1360 |
| `.kt` | 1207 |
| `.sh` | 372 |
| `.xml` | 213 |
| `.gradle` | 193 |
| `.toml` | 31 |
| `.ini` | 10 |

### LoC by top-level subsystem

| Subsystem | LoC |
|---|---:|
| `runtime` | 67100 |
| `tests` | 65038 |
| `ui` | 9360 |
| `scripts` | 4899 |
| `app` | 4154 |
| `<root>` | 4137 |
| `tools` | 3761 |
| `adaad` | 2789 |
| `.github` | 2600 |
| `security` | 2149 |
| `android` | 1896 |
| `governance` | 870 |
| `memory` | 296 |
| `config` | 177 |
| `evolution` | 116 |
| `examples` | 102 |
| `sandbox` | 88 |
| `core` | 44 |
| `ops` | 26 |

## 3) Test density report (tests per runtime module)

Method: count test files in `tests/` that reference each runtime module via import/reference strings.

| Runtime module | Kind | Python files in module | Referencing test files | Test density (tests/module-file) |
|---|---|---:|---:|---:|
| `evolution` | dir | 78 | 123 | 1.58 |
| `governance` | dir | 82 | 120 | 1.46 |
| `autonomy` | dir | 20 | 45 | 2.25 |
| `intelligence` | dir | 12 | 32 | 2.67 |
| `constitution` | file | 1 | 26 | 26.00 |
| `sandbox` | dir | 19 | 17 | 0.89 |
| `metrics` | file | 1 | 16 | 16.00 |
| `market` | dir | 7 | 10 | 1.43 |
| `mutation` | dir | 11 | 9 | 0.82 |
| `mcp` | dir | 10 | 8 | 0.80 |
| `api` | dir | 8 | 7 | 0.88 |
| `memory` | dir | 7 | 7 | 1.00 |
| `tools` | dir | 6 | 7 | 1.17 |
| `boot` | dir | 3 | 5 | 1.67 |
| `manifest` | dir | 3 | 5 | 1.67 |
| `mutation_lifecycle` | file | 1 | 5 | 5.00 |
| `preflight` | file | 1 | 5 | 5.00 |
| `state` | dir | 6 | 5 | 0.83 |
| `test_sandbox` | file | 1 | 5 | 5.00 |
| `analysis` | dir | 4 | 4 | 1.00 |
| `capability` | dir | 5 | 4 | 0.80 |
| `fitness` | file | 1 | 4 | 4.00 |
| `recovery` | dir | 3 | 4 | 1.33 |
| `capability_graph` | file | 1 | 3 | 3.00 |
| `fitness_pipeline` | file | 1 | 3 | 3.00 |
| `intake` | dir | 6 | 3 | 0.50 |
| `timeutils` | file | 1 | 3 | 3.00 |
| `integrations` | dir | 4 | 2 | 0.50 |
| `metrics_analysis` | file | 1 | 2 | 2.00 |
| `platform` | dir | 3 | 2 | 0.67 |
| `constants` | file | 1 | 1 | 1.00 |
| `director` | file | 1 | 1 | 1.00 |
| `economic` | dir | 3 | 1 | 0.33 |
| `founders_law` | file | 1 | 1 | 1.00 |
| `governance_surface` | file | 1 | 1 | 1.00 |
| `import_guard` | file | 1 | 1 | 1.00 |
| `integrity` | dir | 2 | 1 | 0.50 |
| `invariants` | file | 1 | 1 | 1.00 |
| `legitimacy` | file | 1 | 1 | 1.00 |
| `memory_adapter` | file | 1 | 1 | 1.00 |
| `report_version` | file | 1 | 1 | 1.00 |
| `warm_pool` | file | 1 | 1 | 1.00 |
| `__init__` | file | 1 | 0 | 0.00 |
| `agents` | dir | 2 | 0 | 0.00 |
| `capabilities` | file | 1 | 0 | 0.00 |
| `element_registry` | file | 1 | 0 | 0.00 |
| `fitness_v2` | file | 1 | 0 | 0.00 |
