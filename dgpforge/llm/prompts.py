"""Prompt templates for optional LLM-assisted DGP contract workflows."""

from __future__ import annotations


DRAFT_SYSTEM_PROMPT = """Draft a DGPForge YAML contract as structured JSON.
The contract is a proposal only. Do not invent statistical evidence.
All output must be validated before any simulation is run."""


PAPER_EXTRACTION_PROMPT = """Extract a DGPForge simulation contract from a simulation-section excerpt.
Log every filled default and unresolved assumption. Do not claim general paper reproduction."""


REVIEW_SYSTEM_PROMPT = """Review an existing DGPForge contract.
Separate deterministic checks from interpretation. Do not assert estimator validity unless deterministic evidence supports it."""


def draft_prompt(user_prompt: str) -> str:
    return f"{DRAFT_SYSTEM_PROMPT}\n\nUser prompt:\n{user_prompt}"


def paper_prompt(excerpt: str) -> str:
    return f"{PAPER_EXTRACTION_PROMPT}\n\nExcerpt:\n{excerpt}"


def review_prompt(config_text: str) -> str:
    return f"{REVIEW_SYSTEM_PROMPT}\n\nConfig:\n{config_text}"
