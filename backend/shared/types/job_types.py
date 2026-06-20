"""Data contracts for job lifecycle and workflow execution tracking.

JobRecord is persisted to Supabase and represents the external job state
visible to the API layer. WorkflowError and NodeExecution are in-memory
audit records stored in AnalysisState during workflow execution.

Dependency rule: imports only from shared/types/enums and stdlib/pydantic.
"""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from config.constants import REPORT_SCHEMA_VERSION
from shared.types.enums import JobStatus, NodeExecutionStatus


class WorkflowError(BaseModel):
    """An error event recorded during workflow execution.

    Accumulated in AnalysisState.errors throughout the workflow. Non-fatal
    errors allow the workflow to continue; fatal errors terminate it.
    """

    error_id: str = Field(
        ...,
        description=(
            "Scoped unique identifier within the AnalysisState error list. "
            "Format: 'ERR-NNN' where NNN is zero-padded to three digits."
        ),
    )
    node_name: str = Field(..., description="Name of the LangGraph node where this error occurred.")
    error_type: str = Field(
        ..., description="Python exception class name (e.g. 'CloneTimeoutError')."
    )
    message: str = Field(..., description="Error message string.")
    timestamp: datetime = Field(..., description="UTC timestamp when the error occurred.")
    is_fatal: bool = Field(
        ...,
        description=(
            "True when this error caused the workflow to terminate. "
            "False when the workflow continued despite this error."
        ),
    )

    @field_validator("error_id", mode="before")
    @classmethod
    def validate_error_id_format(cls, value: str) -> str:
        """Enforce the ERR-NNN scoped identifier format."""
        if not re.match(r"^ERR-\d{3}$", str(value)):
            raise ValueError(
                f"error_id '{value}' does not match required format 'ERR-NNN' (e.g. 'ERR-001')."
            )
        return value


class NodeExecution(BaseModel):
    """Audit record for a single LangGraph node execution within a workflow run."""

    node_name: str = Field(..., description="Identifier of the LangGraph node.")
    started_at: datetime = Field(..., description="UTC timestamp when the node began execution.")
    completed_at: datetime | None = Field(
        default=None,
        description=(
            "UTC timestamp when the node finished execution. "
            "None while the node is still running."
        ),
    )
    status: NodeExecutionStatus = Field(
        ..., description="Execution result of this node."
    )
    output_field_written: str | None = Field(
        default=None,
        description=(
            "Name of the AnalysisState field this node wrote to on success. "
            "None for nodes that did not produce a named output field "
            "(e.g. PersistenceNode writes to Supabase, not to state)."
        ),
    )

    @model_validator(mode="after")
    def validate_completed_at_set_when_terminal(self) -> "NodeExecution":
        """Enforce that completed_at is set for terminal node statuses."""
        terminal_statuses = {
            NodeExecutionStatus.COMPLETE,
            NodeExecutionStatus.FAILED,
            NodeExecutionStatus.SKIPPED,
        }
        if self.status in terminal_statuses and self.completed_at is None:
            raise ValueError(
                f"NodeExecution for '{self.node_name}' has terminal status "
                f"'{self.status.value}' but completed_at is not set."
            )
        return self

    @model_validator(mode="after")
    def validate_completed_after_started(self) -> "NodeExecution":
        """Enforce chronological ordering of timestamps."""
        if self.completed_at is not None:
            started = self.started_at
            completed = self.completed_at

            started_aware = (
                started if started.tzinfo else started.replace(tzinfo=__import__("datetime").timezone.utc)
            )
            completed_aware = (
                completed if completed.tzinfo else completed.replace(tzinfo=__import__("datetime").timezone.utc)
            )
            if completed_aware < started_aware:
                raise ValueError(
                    f"NodeExecution for '{self.node_name}': completed_at "
                    f"({self.completed_at.isoformat()}) is before started_at "
                    f"({self.started_at.isoformat()})."
                )
        return self


class JobRecord(BaseModel):
    """Persistent job record stored in Supabase.

    Represents the externally visible job lifecycle state. Created by the
    Job Manager and updated by the Persistence Node on completion or failure.

    Ownership rules:
    - Job Manager creates JobRecord and updates status transitions.
    - Persistence Node sets status to COMPLETE and sets report_id.
    - Persistence Node sets status to FAILED and sets error_message on failure.
    - API Gateway reads JobRecord; never writes to it.
    - Analysis agents must not access JobRecord directly.

    Transition rules (enforced by model_validator):
    - report_id must be None unless status is COMPLETE.
    - error_message must be non-None when status is FAILED.
    - completed_at must be non-None for terminal statuses.
    """

    job_id: UUID = Field(..., description="Primary key. Generated at job creation.")
    repo_url: str = Field(..., description="Repository URL as submitted by the user.")
    repo_name: str = Field(..., description="Repository name extracted from the URL.")
    status: JobStatus = Field(..., description="Current job lifecycle status.")
    created_at: datetime = Field(..., description="UTC timestamp when the job was created.")
    schema_version: str = Field(
        default=REPORT_SCHEMA_VERSION,
        description=f"Contract schema version. MVP value: '{REPORT_SCHEMA_VERSION}'.",
    )
    started_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when workflow execution began. None until status is RUNNING.",
    )
    completed_at: datetime | None = Field(
        default=None,
        description=(
            "UTC timestamp when the job reached a terminal state. "
            "None until status is COMPLETE or FAILED."
        ),
    )
    report_id: UUID | None = Field(
        default=None,
        description=(
            "UUID of the FinalReport produced by this job. "
            "None until status is COMPLETE."
        ),
    )
    error_message: str | None = Field(
        default=None,
        description=(
            "Human-readable error description. "
            "Must be non-None when status is FAILED."
        ),
    )
    error_type: str | None = Field(
        default=None,
        description=(
            "Exception class name for debugging (e.g. 'CloneTimeoutError'). "
            "Non-None when status is FAILED."
        ),
    )

    @field_validator("repo_url", mode="before")
    @classmethod
    def validate_github_url(cls, value: str) -> str:
        """Enforce GitHub HTTPS URL format."""
        url = str(value).strip()
        if not url.startswith("https://github.com/"):
            raise ValueError(
                f"repo_url must be a GitHub HTTPS URL. Got: '{url}'"
            )
        return url

    @field_validator("schema_version", mode="before")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        """Enforce that schema_version matches the current contract version."""
        if str(value) != REPORT_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be '{REPORT_SCHEMA_VERSION}'. Got '{value}'."
            )
        return value

    @model_validator(mode="after")
    def validate_terminal_state_invariants(self) -> "JobRecord":
        """Enforce all invariants that apply when the job reaches a terminal state."""
        if self.status == JobStatus.COMPLETE:
            if self.report_id is None:
                raise ValueError(
                    "report_id must be set when status is COMPLETE."
                )
            if self.completed_at is None:
                raise ValueError(
                    "completed_at must be set when status is COMPLETE."
                )

        if self.status == JobStatus.FAILED:
            if not self.error_message:
                raise ValueError(
                    "error_message must be a non-empty string when status is FAILED."
                )
            if self.completed_at is None:
                raise ValueError(
                    "completed_at must be set when status is FAILED."
                )

        if self.status not in {JobStatus.COMPLETE}:
            if self.report_id is not None:
                raise ValueError(
                    f"report_id must be None when status is '{self.status.value}'. "
                    "report_id is only set on COMPLETE."
                )
        return self

    @model_validator(mode="after")
    def validate_timestamp_ordering(self) -> "JobRecord":
        """Enforce chronological ordering of timestamps."""
        from datetime import timezone

        def to_aware(dt: datetime) -> datetime:
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

        created = to_aware(self.created_at)

        if self.started_at is not None:
            started = to_aware(self.started_at)
            if started < created:
                raise ValueError(
                    f"started_at ({self.started_at.isoformat()}) is before "
                    f"created_at ({self.created_at.isoformat()})."
                )

        if self.completed_at is not None:
            completed = to_aware(self.completed_at)
            if completed < created:
                raise ValueError(
                    f"completed_at ({self.completed_at.isoformat()}) is before "
                    f"created_at ({self.created_at.isoformat()})."
                )
            if self.started_at is not None:
                started = to_aware(self.started_at)
                if completed < started:
                    raise ValueError(
                        f"completed_at ({self.completed_at.isoformat()}) is before "
                        f"started_at ({self.started_at.isoformat()})."
                    )
        return self
