# Monolithic Test Domain Mapping

This records one-to-one relocation from legacy monoliths into domain-aligned suites.

## `tests/test_phase2_capabilities.py`

| Legacy test | Domain | New path |
|---|---|---|
| `TestExploreExploitController.test_default_mode_is_explore` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestExploreExploitController.test_default_consecutive_exploit_zero` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestExploreExploitController.test_default_explore_ratio_one` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestExploreExploitController.test_plateau_forces_explore` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestExploreExploitController.test_high_score_selects_exploit` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestExploreExploitController.test_low_score_selects_explore` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestExploreExploitController.test_human_override_always_honoured` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestExploreExploitController.test_consecutive_exploit_limit_forces_explore` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestExploreExploitController.test_explore_floor_enforced` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestExploreExploitController.test_commit_exploit_increments_counter` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestExploreExploitController.test_commit_explore_resets_counter` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestExploreExploitController.test_commit_updates_history` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestExploreExploitController.test_set_mode_changes_current_mode` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestExploreExploitController.test_set_mode_emits_transition_log` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestExploreExploitController.test_audit_writer_called_on_transition` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestExploreExploitController.test_audit_writer_failure_does_not_block_selection` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestExploreExploitController.test_state_persists_across_reload` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestExploreExploitController.test_health_snapshot_keys` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestExploreExploitController.test_explore_floor_ok_reflects_actual_ratio` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestExploreExploitController.test_reset_clears_all_state` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestExploreExploitController.test_min_explore_ratio_is_20_percent` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestExploreExploitController.test_max_consecutive_exploit_is_4` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestHumanApprovalGate.test_request_approval_returns_approval_id` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestHumanApprovalGate.test_request_approval_adds_to_pending_queue` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestHumanApprovalGate.test_two_requests_both_pending` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestHumanApprovalGate.test_approved_mutation_passes_is_approved` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestHumanApprovalGate.test_rejected_mutation_fails_is_approved` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestHumanApprovalGate.test_pending_mutation_fails_is_approved` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestHumanApprovalGate.test_unknown_mutation_fails_is_approved` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestHumanApprovalGate.test_decision_removed_from_pending_queue` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestHumanApprovalGate.test_invalid_approval_id_raises` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestHumanApprovalGate.test_decision_digest_is_deterministic` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestHumanApprovalGate.test_decision_digest_differs_on_different_inputs` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestHumanApprovalGate.test_revoked_approval_fails_is_approved` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestHumanApprovalGate.test_revocation_writes_audit_event` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestHumanApprovalGate.test_batch_approve_approves_all` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestHumanApprovalGate.test_batch_approve_returns_decision_objects` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestHumanApprovalGate.test_batch_approve_uses_index_without_full_replay_per_item` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestHumanApprovalGate.test_index_corruption_triggers_rebuild_and_preserves_correctness` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestHumanApprovalGate.test_index_digest_mismatch_triggers_rebuild` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestHumanApprovalGate.test_audit_trail_records_all_events` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestHumanApprovalGate.test_audit_trail_filtered_by_mutation_id` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestHumanApprovalGate.test_audit_writer_called_on_approval` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestHumanApprovalGate.test_audit_writer_failure_does_not_block_decision` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestLineageDAG.test_add_root_node_succeeds` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestLineageDAG.test_add_child_node_succeeds` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestLineageDAG.test_duplicate_node_id_raises` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestLineageDAG.test_missing_parent_raises` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestLineageDAG.test_wrong_generation_raises` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestLineageDAG.test_promoted_without_approval_raises` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestLineageDAG.test_generation_exceeding_max_raises` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestLineageDAG.test_promote_node_sets_flags` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestLineageDAG.test_promote_nonexistent_node_raises` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestLineageDAG.test_get_node_after_promote_reflects_promotion` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestLineageDAG.test_root_chain_is_single_node` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestLineageDAG.test_chain_ordered_oldest_first` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestLineageDAG.test_chain_missing_node_raises` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestLineageDAG.test_branch_comparison_fitness_delta` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestLineageDAG.test_branch_comparison_generation_distance` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestLineageDAG.test_generation_summary_counts` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestLineageDAG.test_generation_summary_top_node` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestLineageDAG.test_integrity_check_passes_on_clean_dag` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestLineageDAG.test_integrity_check_fails_on_tampered_file` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestLineageDAG.test_dag_reloads_from_disk` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestLineageDAG.test_health_snapshot_keys` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestLineageDAG.test_health_snapshot_integrity_ok_true` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestLineageDAG.test_audit_writer_called_on_add_node` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestLineageDAG.test_audit_writer_called_on_promote` | inviolability | `tests/governance/inviolability/test_phase2_lineage_inviolability.py` |
| `TestPhaseTransitionGate.test_default_phase_is_zero` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_default_autonomy_level_is_l0` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_l0_label` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_l4_label` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_evaluate_gate_passes_with_sufficient_evidence` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_evaluate_gate_fails_with_insufficient_evidence` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_evaluate_gate_does_not_commit_transition` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_evaluate_gate_reports_per_criterion_results` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_evaluate_gate_digest_is_deterministic` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_phase_skip_raises` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_invalid_phase_zero_raises` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_invalid_phase_five_raises` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_successful_transition_advances_phase` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_failed_transition_does_not_advance_phase` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_transition_writes_audit_record` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_transition_history_recorded` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_sequential_transitions_each_advance_one_level` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_consecutive_clean_epochs_increments` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_dirty_epoch_resets_counter` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_clean_epoch_contributes_to_gate_criteria` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_demote_phase_reduces_current_phase` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_demote_resets_consecutive_clean_epochs` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_demote_above_current_phase_raises` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_demote_writes_audit_record` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_phase_state_persists_across_reload` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_health_snapshot_keys` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_health_snapshot_autonomy_label_correct` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_audit_writer_called_on_successful_transition` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_audit_writer_not_called_on_failed_transition` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_all_four_phase_criteria_defined` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_phase_criteria_monotonically_increasing_difficulty` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestPhaseTransitionGate.test_phase_4_requires_100_percent_lineage` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestEvolutionLoopIntegration.test_epoch_result_has_evolution_mode_field` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestEvolutionLoopIntegration.test_epoch_result_default_mode_is_explore` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestEvolutionLoopIntegration.test_evolution_loop_accepts_controller_kwarg` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestEvolutionLoopIntegration.test_evolution_loop_uses_provided_controller` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |
| `TestEvolutionLoopIntegration.test_controller_commit_called_after_epoch` | governance signals | `tests/governance/signals/test_phase2_governance_signals.py` |

## `tests/test_aponi_governance_intelligence.py`

| Legacy test | Domain | New path |
|---|---|---|
| `test_governance_health_model_is_formalized_and_deterministic` | determinism/replay | `tests/determinism/test_aponi_governance_determinism.py` |
| `test_governance_health_applies_warn_and_block_thresholds` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_replay_divergence_counts_recent_replay_events` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_constitution_escalations_supports_canonical_and_legacy_names` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_risk_summary_uses_normalized_event_types_with_legacy_fallbacks` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_normalize_event_type_maps_legacy_and_canonical_fields` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_normalize_event_type_prefers_explicit_event_type` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_semantic_drift_classifier_assigns_expected_categories` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_replay_diff_returns_semantic_drift_with_stable_ordering` | determinism/replay | `tests/determinism/test_aponi_governance_determinism.py` |
| `test_user_console_uses_external_script_for_csp_compatibility` | endpoint contracts | `tests/endpoints/test_aponi_endpoint_contracts.py` |
| `test_dashboard_script_uses_safe_dom_rendering_primitives` | endpoint contracts | `tests/endpoints/test_aponi_endpoint_contracts.py` |
| `test_cancel_control_command_writes_cancellation_entry` | endpoint contracts | `tests/endpoints/test_aponi_endpoint_contracts.py` |
| `test_cancel_control_command_returns_not_found` | endpoint contracts | `tests/endpoints/test_aponi_endpoint_contracts.py` |
| `test_risk_instability_uses_weighted_deterministic_formula` | determinism/replay | `tests/determinism/test_aponi_governance_determinism.py` |
| `test_risk_instability_defaults_to_zero_without_timeline` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_loaders_ignore_schema_version_metadata` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_capability_matrix_uses_canonical_capabilities_key` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_control_command_validation_requires_strict_profile_and_known_capabilities` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_control_command_validation_rejects_unknown_skill_profile` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_control_command_validation_rejects_invalid_mode` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_control_command_validation_rejects_capability_outside_profile` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_control_command_validation_enforces_knowledge_domain_membership` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_control_command_validation_enforces_ability_membership` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_control_command_validation_caps_capability_count` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_control_command_validation_deduplicates_capabilities` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_queue_control_command_appends_deterministic_entry` | determinism/replay | `tests/determinism/test_aponi_governance_determinism.py` |
| `test_verify_control_queue_detects_tamper` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_environment_health_snapshot_reports_required_surfaces` | endpoint contracts | `tests/endpoints/test_aponi_endpoint_contracts.py` |
| `test_environment_health_snapshot_reports_schema_mismatch` | endpoint contracts | `tests/endpoints/test_aponi_endpoint_contracts.py` |
| `test_control_policy_summary_and_templates_are_deterministic` | determinism/replay | `tests/determinism/test_aponi_governance_determinism.py` |
| `test_risk_instability_reports_velocity_and_acceleration` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_policy_simulation_compares_current_and_candidate_policy` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_policy_simulation_rejects_invalid_score_input` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_epoch_chain_anchor_is_emitted_in_replay_diff` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_velocity_spike_anomaly_flag_sets_on_large_velocity` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_alerts_evaluate_emits_expected_severity_buckets` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_alerts_evaluate_returns_empty_when_below_thresholds` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_replay_diff_export_includes_bundle_export_metadata` | endpoint contracts | `tests/endpoints/test_aponi_endpoint_contracts.py` |
| `test_epoch_export_includes_bundle_export_metadata` | endpoint contracts | `tests/endpoints/test_aponi_endpoint_contracts.py` |
| `test_validate_ux_event_requires_type_session_and_feature` | endpoint contracts | `tests/endpoints/test_aponi_endpoint_contracts.py` |
| `test_ux_summary_aggregates_recent_metrics_events` | endpoint contracts | `tests/endpoints/test_aponi_endpoint_contracts.py` |
| `test_normalize_agm_step_supports_legacy_and_canonical_forms` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_validate_event_type_for_agm_step_allows_control_and_step_specific_events` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |
| `test_validate_event_type_for_agm_step_rejects_mismatched_event_type` | governance signals | `tests/governance/signals/test_aponi_governance_signals.py` |

## `tests/test_constitution_policy.py`

| Legacy test | Domain | New path |
|---|---|---|
| `test_load_constitution_policy_parses_rules` | inviolability | `tests/governance/inviolability/test_constitution_policy_inviolability.py` |
| `test_entropy_budget_validator_contract` | determinism/replay | `tests/determinism/test_constitution_policy_determinism.py` |
| `test_entropy_budget_validator_fails_closed_on_invalid_observed_bits` | inviolability | `tests/governance/inviolability/test_constitution_policy_inviolability.py` |
| `test_entropy_budget_validator_blocks_disabled_budget_in_production` | inviolability | `tests/governance/inviolability/test_constitution_policy_inviolability.py` |
| `test_advisory_rule_failures_do_not_block_evaluation` | inviolability | `tests/governance/inviolability/test_constitution_policy_inviolability.py` |
| `test_tier_override_behavior_from_policy` | inviolability | `tests/governance/inviolability/test_constitution_policy_inviolability.py` |
| `test_load_policy_document_parses_yaml_content` | inviolability | `tests/governance/inviolability/test_constitution_policy_inviolability.py` |
| `test_load_policy_document_parses_json_in_yaml_extension` | inviolability | `tests/governance/inviolability/test_constitution_policy_inviolability.py` |
| `test_load_policy_document_maps_malformed_json_or_yaml_to_value_error` | inviolability | `tests/governance/inviolability/test_constitution_policy_inviolability.py` |
| `test_invalid_schema_fail_close` | inviolability | `tests/governance/inviolability/test_constitution_policy_inviolability.py` |
| `test_reload_logs_amendment_hashes` | governance signals | `tests/governance/signals/test_constitution_policy_signals.py` |
| `test_version_mismatch_fails_close` | inviolability | `tests/governance/inviolability/test_constitution_policy_inviolability.py` |
| `test_evaluate_mutation_restores_prior_envelope_state` | determinism/replay | `tests/determinism/test_constitution_policy_determinism.py` |
| `test_entropy_epoch_budget_exceeded_blocks_in_production` | inviolability | `tests/governance/inviolability/test_constitution_policy_inviolability.py` |
| `test_evaluate_mutation_emits_applicability_matrix` | governance signals | `tests/governance/signals/test_constitution_policy_signals.py` |
| `test_resource_bounds_validator_uses_env_overrides_and_telemetry` | inviolability | `tests/governance/inviolability/test_constitution_policy_inviolability.py` |
| `test_resource_bounds_violation_emits_metrics_and_journal` | governance signals | `tests/governance/signals/test_constitution_policy_signals.py` |
| `test_resource_bounds_policy_precedes_env_when_overrides_disabled` | inviolability | `tests/governance/inviolability/test_constitution_policy_inviolability.py` |
| `test_governance_rejection_event_contains_resource_snapshot` | governance signals | `tests/governance/signals/test_constitution_policy_signals.py` |
| `test_replay_determinism_resource_accounting_and_verdict_stable` | determinism/replay | `tests/determinism/test_constitution_policy_determinism.py` |
| `test_resource_bounds_validator_rejects_invalid_env` | inviolability | `tests/governance/inviolability/test_constitution_policy_inviolability.py` |
| `test_evaluation_emits_governance_envelope_digest` | inviolability | `tests/governance/inviolability/test_constitution_policy_inviolability.py` |
| `test_rule_dependency_ordering_places_lineage_before_mutation_rate` | inviolability | `tests/governance/inviolability/test_constitution_policy_inviolability.py` |
| `test_verdicts_include_validator_provenance` | governance signals | `tests/governance/signals/test_constitution_policy_signals.py` |
| `test_coverage_not_configured_is_non_blocking` | inviolability | `tests/governance/inviolability/test_constitution_policy_inviolability.py` |
| `test_validator_provenance_handles_source_unavailable` | inviolability | `tests/governance/inviolability/test_constitution_policy_inviolability.py` |
| `test_governance_drift_blocks_production` | inviolability | `tests/governance/inviolability/test_constitution_policy_inviolability.py` |
| `test_domain_classification_is_deterministic_for_mixed_targets` | determinism/replay | `tests/determinism/test_constitution_policy_determinism.py` |
| `test_effective_limit_uses_strictest_domain_ceiling_for_rate` | inviolability | `tests/governance/inviolability/test_constitution_policy_inviolability.py` |
| `test_evaluate_mutation_emits_domain_ceiling_ledger_event` | governance signals | `tests/governance/signals/test_constitution_policy_signals.py` |
| `test_resource_bounds_logs_warning_when_policy_document_empty` | governance signals | `tests/governance/signals/test_constitution_policy_signals.py` |
| `test_enabled_policy_rules_have_validator_registry_and_version_entries` | inviolability | `tests/governance/inviolability/test_constitution_policy_inviolability.py` |
| `test_governance_envelope_digest_is_stable_over_100_identical_evaluations` | determinism/replay | `tests/determinism/test_constitution_policy_determinism.py` |
| `test_evaluation_envelope_includes_policy_hash` | determinism/replay | `tests/determinism/test_constitution_policy_determinism.py` |
| `test_advisory_validators_do_not_mutate_envelope_state` | determinism/replay | `tests/determinism/test_constitution_policy_determinism.py` |
| `test_cross_environment_digest_stability_with_equivalent_envelope_state` | determinism/replay | `tests/determinism/test_constitution_policy_determinism.py` |
| `test_severity_escalation_framework_supports_warning_and_blocking` | inviolability | `tests/governance/inviolability/test_constitution_policy_inviolability.py` |
| `test_severity_escalation_does_not_allow_deescalation` | inviolability | `tests/governance/inviolability/test_constitution_policy_inviolability.py` |

